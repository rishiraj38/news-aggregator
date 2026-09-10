"use client";

import type { AdminDelivery, AdminMember, RecommendationDay } from "@/lib/admin-types";
import { ArticleList, formatWhen, kindLabel, PanelMessage, StatusPill } from "./AdminBits";
import { useAdminJson } from "./useAdminJson";

type Detail = {
  member: AdminMember;
  deliveries: AdminDelivery[];
  recommendation_days: RecommendationDay[];
  history_days: number;
};

export default function MemberDetail({ memberId }: { memberId: string }) {
  const { data, error, loading } = useAdminJson<Detail>(
    `/api/admin/members/${encodeURIComponent(memberId)}`,
  );

  if (loading && !data) return <PanelMessage>Loading member…</PanelMessage>;
  if (error) return <PanelMessage tone="error">{error}</PanelMessage>;
  if (!data) return null;

  const { member, deliveries, recommendation_days: days, history_days: historyDays } = data;

  return (
    <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
      <div className="space-y-5">
        <div>
          <h4 className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-faint mb-2">Personalization</h4>
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="text-ink-faint text-xs">Topic bundles</dt>
              <dd className="text-ink-muted">{member.topics.join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="text-ink-faint text-xs">Keywords</dt>
              <dd className="text-ink-muted">{member.keywords.join(", ") || "None"}</dd>
            </div>
            <div>
              <dt className="text-ink-faint text-xs">Joined</dt>
              <dd className="text-ink-muted">{formatWhen(member.created_at)}</dd>
            </div>
            <div>
              <dt className="text-ink-faint text-xs">Trial clock</dt>
              <dd className="text-ink-muted">
                {member.trial_exempt ? "Exempt — won't expire" : "Expires 27 days after joining"}
              </dd>
            </div>
          </dl>
          {member.tier === "free" && (member.keywords.length > 0 || member.topics.length < 5) && (
            <p className="mt-3 text-[11px] text-amber-200/85">
              Saved preferences are ignored on the Free plan — the pipeline sends the fixed briefing.
            </p>
          )}
        </div>

        <div>
          <h4 className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-faint mb-2">
            Picked for them · last {historyDays} days
          </h4>
          {days.length === 0 ? (
            <p className="text-xs text-ink-faint">No recommendations in this window.</p>
          ) : (
            <div className="space-y-2">
              {days.map((day) => (
                <details key={day.date} className="rounded-xl border border-line bg-surface-deep/60 px-3 py-2">
                  <summary className="cursor-pointer text-sm text-ink-muted flex items-center justify-between gap-2">
                    <span>{day.date}</span>
                    <span className="text-xs tabular-nums text-ink-faint">{day.items.length} stories</span>
                  </summary>
                  <div className="pt-3">
                    <ArticleList articles={day.items} />
                  </div>
                </details>
              ))}
            </div>
          )}
        </div>
      </div>

      <div>
        <h4 className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink-faint mb-2">Emails sent</h4>
        {deliveries.length === 0 ? (
          <p className="text-xs text-ink-faint">
            No emails in the delivery log yet. The log starts from when it was introduced; earlier days appear
            under &ldquo;Picked for them&rdquo;.
          </p>
        ) : (
          <div className="space-y-2">
            {deliveries.map((d) => (
              <details key={d.id} className="rounded-xl border border-line bg-surface-deep/60 px-3 py-2">
                <summary className="cursor-pointer flex flex-wrap items-center gap-x-3 gap-y-1">
                  <StatusPill status={d.status} />
                  <span className="text-sm text-ink">{kindLabel(d.kind)}</span>
                  <span className="text-xs text-ink-faint">{formatWhen(d.sent_at)}</span>
                  {d.articles.length > 0 && (
                    <span className="text-xs tabular-nums text-ink-faint ml-auto">{d.articles.length} stories</span>
                  )}
                </summary>
                <div className="pt-3 space-y-3">
                  {d.subject && <p className="text-xs text-ink-muted">Subject: {d.subject}</p>}
                  {d.error && <p className="text-xs text-rose-300 break-words">Error: {d.error}</p>}
                  {d.kind === "digest" && <ArticleList articles={d.articles} />}
                  {d.missing_articles > 0 && (
                    <p className="text-[11px] text-ink-faint">
                      {d.missing_articles} article(s) in this email have since been removed.
                    </p>
                  )}
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
