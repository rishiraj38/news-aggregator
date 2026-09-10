import type { EmailDelivery, User } from "@prisma/client";
import { db } from "@/lib/db";
import type { AdminDelivery, AdminMember, DeliveryArticle } from "@/lib/admin-types";
import { effectiveTier, isTrialExempt, normalizePlan } from "@/lib/entitlements";
import { canonicalKeywordSelection, canonicalTopicSelection } from "@/lib/topics";

function parsePrefs(raw: string | null | undefined): Record<string, unknown> {
  try {
    const parsed = JSON.parse(raw || "{}");
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

/** `digest_ids` is a JSON list written by the pipeline; tolerate anything else. */
export function parseDigestIds(raw: string | null | undefined): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function iso(d: Date | null | undefined): string | null {
  return d ? d.toISOString() : null;
}

export function serializeMember(
  user: User,
  stats: Pick<AdminMember, "last_delivery" | "sent_30d" | "failed_30d"> = {
    last_delivery: null,
    sent_30d: 0,
    failed_30d: 0,
  },
): AdminMember {
  const prefs = parsePrefs(user.preferences);
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    plan: normalizePlan(user.plan),
    tier: effectiveTier(user.role, user.plan),
    subscription_status: user.subscription_status,
    is_active: String(user.is_active ?? "true").toLowerCase() === "true",
    created_at: iso(user.created_at),
    topics: canonicalTopicSelection(prefs.topics ?? null),
    keywords: canonicalKeywordSelection(prefs.keywords ?? []),
    trial_exempt: isTrialExempt(user.role, user.plan, user.subscription_status),
    pro_requested_at: iso(user.pro_requested_at),
    ...stats,
  };
}

/** Attach the actual articles (and recipient names) to delivery log rows. */
export async function hydrateDeliveries(rows: EmailDelivery[]): Promise<AdminDelivery[]> {
  const idsByRow = rows.map((r) => parseDigestIds(r.digest_ids));
  const allIds = [...new Set(idsByRow.flat())];
  const userIds = [...new Set(rows.map((r) => r.user_id))];

  const [digests, users] = await Promise.all([
    allIds.length
      ? db.digest.findMany({
          where: { id: { in: allIds } },
          select: { id: true, title: true, url: true, article_type: true },
        })
      : Promise.resolve([] as DeliveryArticle[]),
    userIds.length
      ? db.user.findMany({ where: { id: { in: userIds } }, select: { id: true, name: true } })
      : Promise.resolve([] as { id: string; name: string }[]),
  ]);

  const digestById = new Map(digests.map((d) => [d.id, d]));
  const nameById = new Map(users.map((u) => [u.id, u.name]));

  return rows.map((row, i) => {
    const ids = idsByRow[i];
    const articles = ids
      .map((id) => digestById.get(id))
      .filter((d): d is DeliveryArticle => Boolean(d));
    return {
      id: row.id,
      user_id: row.user_id,
      email: row.email,
      name: nameById.get(row.user_id) ?? null,
      kind: row.kind,
      subject: row.subject,
      status: row.status,
      error: row.error,
      sent_at: iso(row.sent_at),
      pipeline_run_id: row.pipeline_run_id,
      articles,
      missing_articles: ids.length - articles.length,
    };
  });
}

export function utcDayKey(d: Date): string {
  return d.toISOString().slice(0, 10);
}
