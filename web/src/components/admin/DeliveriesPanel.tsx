"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";
import type { AdminDelivery, DeliveryDay } from "@/lib/admin-types";
import { cn } from "@/lib/utils";
import { ArticleList, formatWhen, kindLabel, PanelMessage, StatusPill } from "./AdminBits";
import { useAdminJson } from "./useAdminJson";

type DeliveriesResponse = {
  date: string;
  deliveries: AdminDelivery[];
  summary: { recipients: number; sent: number; failed: number };
  days: DeliveryDay[];
};

function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function DeliveriesPanel() {
  const [date, setDate] = useState(todayUtc);
  const { data, error, loading, reload } = useAdminJson<DeliveriesResponse>(
    `/api/admin/deliveries?date=${date}`,
  );

  // The hook keeps the previous day's data until the new day arrives; compare
  // dates instead of mirroring a loading flag into state.
  const stale = !data || data.date !== date;

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row gap-3 sm:items-end sm:justify-between">
        <div>
          <label htmlFor="delivery-date" className="block text-[10px] font-bold uppercase tracking-[0.16em] text-ink-faint mb-1.5">
            Day (UTC)
          </label>
          <input
            id="delivery-date"
            type="date"
            value={date}
            max={todayUtc()}
            onChange={(e) => e.target.value && setDate(e.target.value)}
            className="min-h-10 rounded-xl bg-surface-raised border border-line px-3 text-sm text-ink focus:border-accent/45 focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={reload}
          className="inline-flex items-center justify-center gap-2 min-h-10 px-4 rounded-xl border border-line-strong bg-surface-raised text-sm font-semibold text-ink hover:border-accent/35 transition-colors cursor-pointer"
        >
          <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} strokeWidth={2} />
          Refresh
        </button>
      </div>

      {data && data.days.length > 0 && (
        <div className="flex flex-wrap gap-2" aria-label="Recent days with emails">
          {data.days.map((d) => (
            <button
              key={d.date}
              type="button"
              onClick={() => setDate(d.date)}
              aria-pressed={d.date === date}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs transition-colors cursor-pointer",
                d.date === date
                  ? "border-accent/50 bg-accent-soft text-ink"
                  : "border-line bg-surface-raised/70 text-ink-muted hover:border-line-strong",
              )}
            >
              {d.date}
              <span className="ml-2 tabular-nums text-emerald-300">{d.sent}</span>
              {d.failed > 0 && <span className="ml-1 tabular-nums text-rose-300">/{d.failed}</span>}
            </button>
          ))}
        </div>
      )}

      {error ? (
        <PanelMessage tone="error">{error}</PanelMessage>
      ) : stale ? (
        <PanelMessage>Loading emails for {date}…</PanelMessage>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2.5 max-w-md">
            {(
              [
                ["Recipients", data.summary.recipients, "text-ink"],
                ["Delivered", data.summary.sent, "text-emerald-300"],
                ["Failed", data.summary.failed, data.summary.failed ? "text-rose-300" : "text-ink-faint"],
              ] as const
            ).map(([label, value, tone]) => (
              <div key={label} className="rounded-xl border border-line bg-surface-raised/70 px-3 py-3">
                <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-ink-faint">{label}</div>
                <div className={cn("font-display text-2xl tabular-nums mt-1", tone)}>{value}</div>
              </div>
            ))}
          </div>

          {data.deliveries.length === 0 ? (
            <PanelMessage>No emails logged on {date}.</PanelMessage>
          ) : (
            <ul className="space-y-2.5">
              {data.deliveries.map((d) => (
                <li key={d.id} className="rounded-2xl border border-line bg-surface-raised/50">
                  <details>
                    <summary className="cursor-pointer px-4 py-3 flex flex-wrap items-center gap-x-3 gap-y-1.5">
                      <StatusPill status={d.status} />
                      <span className="font-medium text-ink">{d.name ?? d.email}</span>
                      <span className="text-xs text-ink-faint break-all">{d.email}</span>
                      <span className="text-xs text-ink-muted">{kindLabel(d.kind)}</span>
                      <span className="text-xs text-ink-faint sm:ml-auto">{formatWhen(d.sent_at)}</span>
                    </summary>
                    <div className="px-4 pb-4 space-y-3 border-t border-line pt-3">
                      {d.subject && <p className="text-xs text-ink-muted">Subject: {d.subject}</p>}
                      {d.error && <p className="text-xs text-rose-300 break-words">Error: {d.error}</p>}
                      {d.kind === "digest" ? (
                        <ArticleList articles={d.articles} />
                      ) : (
                        <p className="text-xs text-ink-faint">Account email — no articles.</p>
                      )}
                      {d.missing_articles > 0 && (
                        <p className="text-[11px] text-ink-faint">
                          {d.missing_articles} article(s) in this email have since been removed.
                        </p>
                      )}
                    </div>
                  </details>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
