import { cn } from "@/lib/utils";
import type { DeliveryArticle } from "@/lib/admin-types";
import { digestLaneFromArticleType, digestLaneHumanLabel, digestLaneStyles } from "@/lib/digest-topic";
import type { Tier } from "@/lib/entitlements";
import { TIER_LABELS } from "@/lib/entitlements";

export function TierBadge({ tier }: { tier: Tier }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider border",
        tier === "admin" && "border-amber-400/40 bg-amber-400/[0.12] text-amber-200",
        tier === "pro" && "border-violet-400/40 bg-violet-500/[0.12] text-violet-300",
        tier === "free" && "border-line-strong bg-surface-deep text-ink-faint",
      )}
    >
      {TIER_LABELS[tier]}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const sent = status === "sent";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border",
        sent
          ? "border-emerald-400/35 bg-emerald-500/[0.1] text-emerald-300"
          : "border-rose-400/40 bg-rose-500/[0.12] text-rose-300",
      )}
    >
      {sent ? "Delivered" : "Failed"}
    </span>
  );
}

const KIND_LABELS: Record<string, string> = {
  digest: "Daily digest",
  trial_warning: "Trial warning",
  trial_expired: "Trial expired",
  admin_welcome: "Admin welcome",
};

export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

export function formatWhen(isoDate: string | null): string {
  if (!isoDate) return "—";
  const d = new Date(isoDate);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ArticleList({ articles }: { articles: Array<DeliveryArticle & { score?: number }> }) {
  if (articles.length === 0) {
    return <p className="text-xs text-ink-faint">No articles recorded.</p>;
  }
  return (
    <ol className="space-y-2">
      {articles.map((a, i) => {
        const lane = digestLaneFromArticleType(a.article_type);
        return (
          <li key={`${a.id}-${i}`} className="flex gap-3 items-start">
            <span className="w-5 shrink-0 text-right text-xs tabular-nums text-ink-faint pt-0.5">{i + 1}</span>
            <div className="min-w-0 flex-1">
              <a
                href={a.url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-ink hover:text-accent transition-colors break-words"
              >
                {a.title}
              </a>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className={digestLaneStyles(a.article_type).pill}>{digestLaneHumanLabel(lane)}</span>
                {typeof a.score === "number" && (
                  <span className="text-[11px] tabular-nums text-ink-faint">score {a.score.toFixed(1)}</span>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function PanelMessage({ children, tone = "muted" }: { children: React.ReactNode; tone?: "muted" | "error" }) {
  return (
    <p className={cn("text-sm py-6", tone === "error" ? "text-rose-400/95" : "text-ink-faint")}>{children}</p>
  );
}
