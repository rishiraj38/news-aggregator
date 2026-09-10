import { requireAdmin } from "@/lib/admin-auth";
import { hydrateDeliveries, iso, serializeMember, utcDayKey } from "@/lib/admin-data";
import type { RecommendationDay } from "@/lib/admin-types";
import { db } from "@/lib/db";
import { planMemberUpdate } from "@/lib/member-update";

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
 * Change a subscriber's tier (Free / Pro / Admin), subscription status, or
 * active flag. Validation and guard rails live in `planMemberUpdate`: an admin
 * can't demote or pause themselves, and the last admin can't be demoted.
 */
export async function PATCH(req: Request, { params }: Ctx) {
  const gate = await requireAdmin();
  if (!gate.ok) return gate.response;

  const { id } = await params;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const target = await db.user.findUnique({ where: { id } });
  if (!target) {
    return Response.json({ error: "Member not found" }, { status: 404 });
  }

  const adminCount = await db.user.count({ where: { role: "admin" } });
  const plan = planMemberUpdate(body, { id: target.id, role: target.role }, gate.user.id, adminCount);
  if (!plan.ok) {
    return Response.json({ error: plan.error }, { status: plan.status });
  }

  const updated = await db.user.update({ where: { id }, data: plan.data });

  // Account changes are consequential; leave a trail in the server logs.
  console.info(
    `[admin] ${gate.user.email} updated ${target.email}: ${JSON.stringify(plan.data)} at ${iso(new Date())}`,
  );

  return Response.json({ member: serializeMember(updated) });
}
