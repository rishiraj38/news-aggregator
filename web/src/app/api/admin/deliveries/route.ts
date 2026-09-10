import { requireAdmin } from "@/lib/admin-auth";
import { hydrateDeliveries, utcDayKey } from "@/lib/admin-data";
import type { DeliveryDay } from "@/lib/admin-types";
import { db } from "@/lib/db";

const DAY_MS = 24 * 60 * 60 * 1000;
const RECENT_DAYS = 14;

/**
 * Who was emailed on a given UTC day, whether it landed, and exactly which
 * articles were in each email. `?date=YYYY-MM-DD`, defaulting to today.
 */
export async function GET(req: Request) {
  const gate = await requireAdmin();
  if (!gate.ok) return gate.response;

  const url = new URL(req.url);
  const requested = url.searchParams.get("date");
  const date = requested ?? utcDayKey(new Date());

  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(`${date}T00:00:00Z`))) {
    return Response.json({ error: "date must be YYYY-MM-DD" }, { status: 400 });
  }

  const start = new Date(`${date}T00:00:00.000Z`);
  const end = new Date(start.getTime() + DAY_MS);
  const recentSince = new Date(Date.now() - RECENT_DAYS * DAY_MS);

  const [rows, recent] = await Promise.all([
    db.emailDelivery.findMany({
      where: { sent_at: { gte: start, lt: end } },
      orderBy: { sent_at: "desc" },
    }),
    db.emailDelivery.findMany({
      where: { sent_at: { gte: recentSince } },
      select: { sent_at: true, status: true },
    }),
  ]);

  const dayCounts = new Map<string, DeliveryDay>();
  for (const r of recent) {
    if (!r.sent_at) continue;
    const key = utcDayKey(r.sent_at);
    const day = dayCounts.get(key) ?? { date: key, sent: 0, failed: 0 };
    if (r.status === "sent") day.sent += 1;
    else day.failed += 1;
    dayCounts.set(key, day);
  }

  const deliveries = await hydrateDeliveries(rows);

  return Response.json({
    date,
    deliveries,
    summary: {
      recipients: new Set(deliveries.map((d) => d.email)).size,
      sent: deliveries.filter((d) => d.status === "sent").length,
      failed: deliveries.filter((d) => d.status !== "sent").length,
    },
    days: [...dayCounts.values()].sort((a, b) => (a.date < b.date ? 1 : -1)),
  });
}
