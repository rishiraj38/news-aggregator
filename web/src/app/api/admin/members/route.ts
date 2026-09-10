import { requireAdmin } from "@/lib/admin-auth";
import { iso, serializeMember } from "@/lib/admin-data";
import type { AdminMember, AdminTotals } from "@/lib/admin-types";
import { db } from "@/lib/db";

const STATS_WINDOW_DAYS = 30;

/** Every subscriber, with tier, subscription state, and recent delivery health. */
export async function GET() {
  const gate = await requireAdmin();
  if (!gate.ok) return gate.response;

  const since = new Date(Date.now() - STATS_WINDOW_DAYS * 24 * 60 * 60 * 1000);

  const [users, deliveries] = await Promise.all([
    db.user.findMany({ orderBy: { created_at: "desc" } }),
    db.emailDelivery.findMany({
      where: { sent_at: { gte: since } },
      select: { user_id: true, status: true, kind: true, sent_at: true },
      orderBy: { sent_at: "desc" },
    }),
  ]);

  const stats = new Map<string, Pick<AdminMember, "last_delivery" | "sent_30d" | "failed_30d">>();
  for (const d of deliveries) {
    const s = stats.get(d.user_id) ?? { last_delivery: null, sent_30d: 0, failed_30d: 0 };
    // Rows arrive newest-first, so the first one seen per user is the latest.
    if (!s.last_delivery) {
      s.last_delivery = { sent_at: iso(d.sent_at), status: d.status, kind: d.kind };
    }
    if (d.status === "sent") s.sent_30d += 1;
    else s.failed_30d += 1;
    stats.set(d.user_id, s);
  }

  const members = users.map((u) => serializeMember(u, stats.get(u.id)));

  const totals: AdminTotals = {
    total: members.length,
    free: members.filter((m) => m.tier === "free").length,
    pro: members.filter((m) => m.tier === "pro").length,
    admin: members.filter((m) => m.tier === "admin").length,
    expired: members.filter((m) => m.subscription_status === "expired").length,
    paused: members.filter((m) => !m.is_active).length,
  };

  return Response.json({ members, totals, stats_window_days: STATS_WINDOW_DAYS });
}
