import { requireAdmin } from "@/lib/admin-auth";
import { hydrateDeliveries, iso, serializeMember, utcDayKey } from "@/lib/admin-data";
import type { RecommendationDay } from "@/lib/admin-types";
import { db } from "@/lib/db";
import {
  ALLOWED_PLANS,
  ALLOWED_ROLES,
  ALLOWED_STATUSES,
  isAdminRole,
  isAllowed,
} from "@/lib/entitlements";

type Ctx = { params: Promise<{ id: string }> };

const HISTORY_DAYS = 14;
const DELIVERY_LIMIT = 30;

/**
 * One subscriber in full: preferences, every logged email with its contents,
 * and what the curator picked for them day by day.
 *
 * The delivery log only exists from when it was introduced, so the
 * recommendation history is what covers earlier days — it records what was
 * *picked*, not whether the email carrying it was delivered.
 */
export async function GET(_req: Request, { params }: Ctx) {
  const gate = await requireAdmin();
  if (!gate.ok) return gate.response;

  const { id } = await params;
  const user = await db.user.findUnique({ where: { id } });
  if (!user) {
    return Response.json({ error: "Member not found" }, { status: 404 });
  }

  const since = new Date(Date.now() - HISTORY_DAYS * 24 * 60 * 60 * 1000);

  const [deliveryRows, recs] = await Promise.all([
    db.emailDelivery.findMany({
      where: { user_id: id },
      orderBy: { sent_at: "desc" },
      take: DELIVERY_LIMIT,
    }),
    db.recommendation.findMany({
      where: { user_id: id, created_at: { gte: since } },
      include: { digest: { select: { id: true, title: true, url: true, article_type: true } } },
      orderBy: { created_at: "desc" },
    }),
  ]);

  const byDay = new Map<string, RecommendationDay["items"]>();
  for (const r of recs) {
    if (!r.created_at) continue;
    const key = utcDayKey(r.created_at);
    const items = byDay.get(key) ?? [];
    items.push({
      ...r.digest,
      rank: Number(r.rank) || 0,
      score: Number(r.relevance_score) || 0,
    });
    byDay.set(key, items);
  }
  const recommendationDays: RecommendationDay[] = [...byDay.entries()]
    .sort(([a], [b]) => (a < b ? 1 : -1))
    .map(([date, items]) => ({ date, items: items.sort((a, b) => a.rank - b.rank) }));

  return Response.json({
    member: serializeMember(user),
    deliveries: await hydrateDeliveries(deliveryRows),
    recommendation_days: recommendationDays,
    history_days: HISTORY_DAYS,
  });
}

/**
 * Change a subscriber's plan, subscription status, role, or active flag.
 *
 * Guard rails: an admin cannot demote or pause themselves (a one-click
 * lockout), and the last remaining admin cannot be demoted by anyone.
 */
export async function PATCH(req: Request, { params }: Ctx) {
  const gate = await requireAdmin();
  if (!gate.ok) return gate.response;

  const { id } = await params;

  let body: Record<string, unknown>;
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const target = await db.user.findUnique({ where: { id } });
  if (!target) {
    return Response.json({ error: "Member not found" }, { status: 404 });
  }

  const data: { plan?: string; subscription_status?: string; role?: string; is_active?: string } = {};

  if ("plan" in body) {
    if (!isAllowed(ALLOWED_PLANS, body.plan)) {
      return Response.json({ error: `plan must be one of: ${ALLOWED_PLANS.join(", ")}` }, { status: 400 });
    }
    data.plan = body.plan;
  }
  if ("subscription_status" in body) {
    if (!isAllowed(ALLOWED_STATUSES, body.subscription_status)) {
      return Response.json(
        { error: `subscription_status must be one of: ${ALLOWED_STATUSES.join(", ")}` },
        { status: 400 },
      );
    }
    data.subscription_status = body.subscription_status;
  }
  if ("role" in body) {
    if (!isAllowed(ALLOWED_ROLES, body.role)) {
      return Response.json({ error: `role must be one of: ${ALLOWED_ROLES.join(", ")}` }, { status: 400 });
    }
    data.role = body.role;
  }
  if ("is_active" in body) {
    if (typeof body.is_active !== "boolean") {
      return Response.json({ error: "is_active must be a boolean" }, { status: 400 });
    }
    data.is_active = body.is_active ? "true" : "false";
  }

  if (Object.keys(data).length === 0) {
    return Response.json({ error: "Nothing to update" }, { status: 400 });
  }

  const isSelf = target.id === gate.user.id;
  const demoting = isAdminRole(target.role) && data.role !== undefined && !isAdminRole(data.role);

  if (isSelf && demoting) {
    return Response.json({ error: "You can't remove your own admin access." }, { status: 409 });
  }
  if (isSelf && data.is_active === "false") {
    return Response.json({ error: "You can't pause your own account." }, { status: 409 });
  }
  if (demoting) {
    const adminCount = await db.user.count({ where: { role: "admin" } });
    if (adminCount <= 1) {
      return Response.json({ error: "Can't demote the last remaining admin." }, { status: 409 });
    }
  }

  const updated = await db.user.update({ where: { id }, data });

  // Account changes are consequential; leave a trail in the server logs.
  console.info(
    `[admin] ${gate.user.email} updated ${target.email}: ${JSON.stringify(data)} at ${iso(new Date())}`,
  );

  return Response.json({ member: serializeMember(updated) });
}
