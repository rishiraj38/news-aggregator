import { currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { db } from "@/lib/db";
import Navbar from "@/components/Navbar";
import {
  Sparkles,
  Clock,
  ExternalLink,
  Lock,
  ChevronDown,
  ArrowUpRight,
  Activity,
  Newspaper,
  Layers,
} from "lucide-react";
import { PipelineStatus } from "@/components/PipelineStatus";
import TopicBundlePicker from "@/components/TopicBundlePicker";
import { ALLOWED_TOPIC_IDS, canonicalTopicSelection } from "@/lib/topics";
import {
  digestLaneFromArticleType,
  digestLaneHumanLabel,
  digestLaneStyles,
  type DigestLane,
} from "@/lib/digest-topic";
import { cn } from "@/lib/utils";
import type { Digest, Recommendation } from "@prisma/client";
import BriefingRevealOverlay from "@/components/BriefingRevealOverlay";

type RecWithDigest = Recommendation & { digest: Digest };

function countRecommendationsToday(recs: RecWithDigest[]): number {
  const todayLabel = new Date().toDateString();
  let n = 0;
  for (const r of recs) {
    const raw = r.digest.created_at ?? r.created_at;
    if (!raw) continue;
    const d = new Date(raw);
    if (d.toDateString() === todayLabel) n++;
  }
  return n;
}

const MIX_LANES: DigestLane[] = ["politics", "sports", "cricket", "technology"];
const MIX_BAR_TW: Partial<Record<DigestLane, string>> = {
  politics: "bg-rose-400/90",
  sports: "bg-emerald-400/90",
  cricket: "bg-sky-400/90",
  technology: "bg-brand",
};

function summarizeLaneMix(recs: RecWithDigest[]) {
  const counts = {
    technology: 0,
    politics: 0,
    sports: 0,
    cricket: 0,
    other: 0,
  } as Record<DigestLane, number>;

  let scoreSum = 0;
  for (const r of recs) {
    const lane = digestLaneFromArticleType(r.digest.article_type);
    counts[lane]++;
    scoreSum += Number(r.relevance_score);
  }
  const n = recs.length;
  const activeLanes = MIX_LANES.filter((l) => counts[l] > 0).length;
  const mixScore =
    activeLanes <= 1
      ? "Focused lane"
      : activeLanes <= 3
        ? `Balanced · ${activeLanes} lanes`
        : "Full-stack mix · 4 bundles";

  return {
    counts,
    total: n,
    avgScore: n ? scoreSum / n : 0,
    activeLanes,
    mixScore,
    barTotalMix: MIX_LANES.reduce((s, l) => s + counts[l], 0) || 1,
  };
}

export default async function Dashboard() {
  const user = await currentUser();

  if (!user) {
    redirect("/sign-in");
  }

  let dbUser = await db.user.findUnique({
    where: { email: user.emailAddresses[0].emailAddress },
  });

  const defaultTopics = [...ALLOWED_TOPIC_IDS];

  if (!dbUser) {
    const email = user.emailAddresses[0].emailAddress;
    const name = `${user.firstName} ${user.lastName}`.trim() || "Anonymous";

    const defaultPrefs = JSON.stringify({
      interests: ["World news", "Cricket", "Politics", "Technology"],
      topics: defaultTopics,
      config: { prefer_technical_depth: false },
    });

    try {
      dbUser = await db.user.create({
        data: {
          id: user.id,
          email: email,
          name: name,
          preferences: defaultPrefs,
          is_active: "true",
          title: "New User",
          expertise_level: "Intermediate",
          role: "user",
          subscription_status: "trial",
        },
      });
      console.log("Created new user in Postgres:", dbUser.id);

      try {
        const { sendWelcomeEmail } = await import("@/lib/mailer");
        await sendWelcomeEmail(email, name);
      } catch (emailErr) {
        console.error("Failed to send welcome email:", emailErr);
      }
    } catch (e) {
      console.error("Error syncing user:", e);
    }
  }

  const recommendations = await db.recommendation.findMany({
    where: { user_id: dbUser?.id || user.id },
    orderBy: { created_at: "desc" },
    take: 20,
    include: {
      digest: true,
    },
  });

  let topicIdsForPicker = defaultTopics;
  if (dbUser?.preferences) {
    try {
      const p = JSON.parse(dbUser.preferences) as { topics?: unknown };
      topicIdsForPicker = canonicalTopicSelection(p.topics ?? null);
    } catch {
      topicIdsForPicker = defaultTopics;
    }
  }

  const laneSummary = summarizeLaneMix(recommendations);
  const firstName = user.firstName || "Friend";
  const picksToday = countRecommendationsToday(recommendations);

  return (
    <div className="relative z-10 min-h-dvh bg-surface-deep text-ink overflow-x-hidden">
      <BriefingRevealOverlay
        firstName={firstName}
        hasRecommendations={recommendations.length > 0}
        recommendationCountToday={picksToday}
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-[3.75rem] h-[min(78vh,720px)] helix-aurora opacity-[0.5]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-x-0 top-[4.5rem] h-[620px] helix-grid opacity-[0.42]"
        aria-hidden
      />
      <Navbar />

      <main className="relative max-w-[78rem] mx-auto px-4 sm:px-6 lg:px-10 pt-[calc(5rem+env(safe-area-inset-top))] pb-16 sm:pb-28 space-y-10 sm:space-y-14">
        <header className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:gap-12 items-start">
          <div className="space-y-4">
            <p className="text-[0.7rem] sm:text-[0.75rem] uppercase tracking-[0.28em] text-ink-faint font-semibold flex items-center gap-2 flex-wrap">
              <Sparkles className="w-3.5 h-3.5 text-accent" strokeWidth={2} aria-hidden />
              Helix control room
            </p>
            <h1 className="font-display text-[clamp(2rem,4.6vw,3.05rem)] tracking-[-0.03em] leading-[1.05]">
              <span className="text-transparent bg-clip-text bg-linear-to-br from-ink via-ink to-ink-muted/85">
                {firstName}&rsquo;s briefing desk
              </span>
            </h1>
            <p className="text-[0.9625rem] sm:text-[1.02rem] text-ink-muted leading-relaxed max-w-[36rem]">
              Live view of curator-ranked stories. Dense when you pick one lane,{" "}
              <span className="text-ink font-medium">interleaved</span> when several bundles are active - matching
              the overnight pipeline diversity pass.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row lg:flex-col gap-3 lg:justify-end">
            <div
              className={cn(
                "inline-flex items-center gap-3 rounded-2xl border px-4 py-3.5 text-sm font-medium backdrop-blur-sm shadow-[0_18px_50px_-32px_rgb(15_23_42/1)]",
                dbUser?.role === "admin"
                  ? "border-accent/35 bg-accent-soft/70 text-ink"
                  : "border-line bg-surface-raised/85 text-ink-muted",
              )}
            >
              <Sparkles className="w-4 h-4 text-accent shrink-0" strokeWidth={1.75} />
              {dbUser?.role === "admin" ? "Administrator" : "Explorer plan"}
            </div>
          </div>
        </header>

        {recommendations.length > 0 && (
          <section
            aria-label="Digest pulse"
            className="rounded-[1.35rem] border border-line/90 bg-linear-to-br from-surface via-surface-raised/30 to-surface-deep/95 p-[1px] shadow-[0_26px_80px_-52px_rgb(0_0_0/1)]"
          >
            <div className="rounded-[1.28rem] bg-surface/75 backdrop-blur-md px-5 py-6 sm:p-8">
              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-8">
                <div className="space-y-2 max-w-xl">
                  <div className="flex items-center gap-2 text-[0.6875rem] font-bold uppercase tracking-[0.22em] text-ink-faint">
                    <Activity className="w-4 h-4 text-accent" strokeWidth={2} aria-hidden />
                    Lane mix · last 20
                  </div>
                  <p className="font-display text-[1.35rem] sm:text-[1.5rem] tracking-tight leading-snug">
                    {laneSummary.mixScore}
                  </p>
                  <p className="text-sm text-ink-muted leading-relaxed">
                    Shares reflect surfaced recommendations in your feed - not raw ingest volume. Aim for breadth
                    when you subscribe to multiple bundles.
                  </p>
                </div>

                <div className="grid gap-4 sm:grid-cols-3 lg:gap-6 shrink-0 lg:min-w-[min(420px,100%)]">
                  <article className="rounded-xl border border-line/85 bg-surface-deep/55 px-4 py-3.5 flex flex-col justify-center gap-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-ink-faint">
                      Stories loaded
                    </span>
                    <span className="font-display text-2xl tracking-tight tabular-nums">
                      {laneSummary.total}
                    </span>
                  </article>
                  <article className="rounded-xl border border-line/85 bg-surface-deep/55 px-4 py-3.5 flex flex-col justify-center gap-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-ink-faint">
                      Avg relevance
                    </span>
                    <span className="font-display text-2xl tracking-tight tabular-nums text-accent">
                      {laneSummary.avgScore.toFixed(1)}
                    </span>
                  </article>
                  <article className="rounded-xl border border-line/85 bg-surface-deep/55 px-4 py-3.5 flex flex-col justify-center gap-1 sm:col-span-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-ink-faint">
                      Active bundles
                    </span>
                    <span className="font-display text-2xl tracking-tight">{laneSummary.activeLanes}</span>
                  </article>
                </div>
              </div>

              <div className="mt-8 flex h-[0.6875rem] w-full rounded-full border border-line/75 bg-surface-deep/70 overflow-hidden shadow-inner gap-px">
                {MIX_LANES.flatMap((lane) => {
                  const pct = laneSummary.counts[lane] / laneSummary.barTotalMix;
                  if (!pct || pct <= 0) return [];
                  return [
                    <div
                      key={lane}
                      className={cn(
                        "min-h-full min-w-0 transition-[flex-grow] duration-500",
                        MIX_BAR_TW[lane],
                      )}
                      title={`${digestLaneHumanLabel(lane)}: ${laneSummary.counts[lane]} · ${Math.round(pct * 100)}%`}
                      style={{ flexGrow: pct }}
                    />,
                  ];
                })}
                {laneSummary.counts.other > 0 ? (
                  <div
                    className="bg-ink-muted/35 min-h-full min-w-0"
                    title={`Feed: ${laneSummary.counts.other}`}
                    style={{
                      flexGrow: laneSummary.counts.other / laneSummary.barTotalMix,
                    }}
                  />
                ) : null}
              </div>
              <dl className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2 text-[11px] text-ink-faint uppercase tracking-[0.12em] font-semibold">
                {MIX_LANES.map((lane) => (
                  <div key={lane} className="flex items-center gap-2 min-w-0">
                    <span
                      className={cn(
                        "h-1.5 w-1.5 rounded-full shrink-0",
                        MIX_BAR_TW[lane] ?? "bg-ink-muted/50",
                      )}
                      aria-hidden
                    />
                    <dt className="truncate">{digestLaneHumanLabel(lane)}</dt>
                    <dd className="ml-auto tabular-nums">{laneSummary.counts[lane]}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </section>
        )}

        {dbUser?.role === "admin" && (
          <section className="rounded-2xl border border-accent/25 bg-accent-soft/[0.12] backdrop-blur-sm px-5 py-5 sm:px-7">
            <PipelineStatus />
          </section>
        )}

        <section className="rounded-2xl border border-line/85 bg-surface/80 backdrop-blur-sm p-6 sm:p-8 lg:p-9 shadow-[0_26px_80px_-62px_rgb(15_23_42/1)] relative overflow-hidden">
          <span
            className="pointer-events-none absolute inset-y-12 -right-20 w-[220px] rounded-full blur-3xl bg-brand/14 opacity-60"
            aria-hidden
          />
          <div className="relative flex flex-col gap-6 sm:flex-row sm:gap-10">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-accent/35 bg-accent-soft/50">
              <Layers className="w-5 h-5 text-accent" strokeWidth={1.85} aria-hidden />
            </div>
            <TopicBundlePicker initialTopics={topicIdsForPicker} />
          </div>
        </section>

        <section className="rounded-2xl border border-line/85 bg-surface/80 backdrop-blur-sm p-6 sm:p-8 lg:p-9 shadow-[0_26px_80px_-62px_rgb(15_23_42/1)]">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-8">
            <div className="min-w-0 flex-1">
              <h2 className="text-[0.7rem] font-bold uppercase tracking-[0.2em] text-ink-faint mb-5 flex flex-wrap items-center gap-2">
                <Newspaper className="w-4 h-4 text-ink-muted" strokeWidth={1.85} aria-hidden />
                Interest filters
                {dbUser?.role === "admin" ? (
                  <span className="text-[0.625rem] font-semibold normal-case px-2.5 py-0.5 rounded-full border border-accent/35 bg-accent-soft text-ink">
                    Unlocked
                  </span>
                ) : (
                  <Lock className="w-3.5 h-3.5 text-ink-faint" strokeWidth={2} aria-label="Locked" />
                )}
              </h2>
              <div className="flex flex-wrap gap-2">
                {(() => {
                  try {
                    const prefs = dbUser?.preferences
                      ? JSON.parse(dbUser.preferences as string)
                      : {};
                    const interests =
                      prefs.interests || prefs.keywords || ["Tech News"];
                    return interests.map((tag: string) => (
                      <span
                        key={tag}
                        className="px-3 py-2 rounded-xl bg-surface-raised/95 text-[0.9rem] text-ink-muted border border-line/90"
                      >
                        {tag}
                      </span>
                    ));
                  } catch {
                    return (
                      <span className="text-sm text-ink-faint">Default interests</span>
                    );
                  }
                })()}
                <span
                  className="px-3 py-2 rounded-xl border border-dashed border-line-strong text-[0.9rem] text-ink-faint cursor-default"
                  title={
                    dbUser?.role === "admin"
                      ? "Managed in admin tools"
                      : "Upgrade to customize"
                  }
                >
                  + Keyword
                </span>
              </div>
            </div>
            <div className="shrink-0 lg:text-right lg:max-w-[14rem]">
              {dbUser?.role === "admin" ? (
                <button
                  type="button"
                  className="inline-flex w-full lg:w-auto items-center justify-center gap-2 min-h-11 px-5 rounded-xl bg-accent text-surface-deep text-sm font-semibold hover:brightness-110 transition-[filter] shadow-[0_16px_40px_-26px_rgb(79_70_229/1)]"
                >
                  <Sparkles className="w-4 h-4" strokeWidth={2} />
                  Manage keywords
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    className="inline-flex w-full lg:w-auto items-center justify-center gap-2 min-h-11 px-5 rounded-xl border border-line-strong bg-surface-raised text-sm font-semibold text-ink hover:border-accent/35 transition-colors"
                  >
                    Customize (upgrade)
                  </button>
                  <p className="text-[11px] text-ink-faint mt-2.5">
                    Unlock custom themes on Full access.
                  </p>
                </>
              )}
            </div>
          </div>
        </section>

        {recommendations.length === 0 ? (
          <div className="rounded-2xl border border-line/85 bg-linear-to-b from-surface to-surface-deep/96 px-6 sm:px-10 py-[4.25rem] text-center shadow-[0_38px_100px_-64px_rgb(0_0_0/0.85)]">
            <Sparkles
              className="w-[3rem] h-[3rem] mx-auto mb-7 text-accent/95"
              strokeWidth={1.15}
              aria-hidden
            />
            <h2 className="font-display text-[1.82rem] sm:text-[2.05rem] tracking-tight mb-4">
              Pipeline registered you
            </h2>
            <p className="text-ink-muted max-w-[26rem] mx-auto leading-relaxed mb-10 text-[0.9625rem]">
              Overnight jobs harvest aligned feeds. Once the curator ships your first recommendations, they land
              here - no gimmicky refresh rituals.
            </p>
            <div className="inline-flex flex-wrap justify-center gap-3 px-5 py-2.5 rounded-xl border border-line-strong bg-surface-raised/90 text-[0.9rem] text-ink-muted">
              <Clock className="w-4 h-4 text-accent shrink-0" strokeWidth={2} />
              Typical cadence: next scheduled run within ~24h
            </div>
          </div>
        ) : (
          <GroupedFeed recommendations={recommendations} />
        )}
      </main>
    </div>
  );
}

function GroupedFeed({ recommendations }: { recommendations: RecWithDigest[] }) {
  const groups = {
    today: [] as RecWithDigest[],
    yesterday: [] as RecWithDigest[],
    earlier: [] as RecWithDigest[],
  };

  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);

  recommendations.forEach((rec) => {
    const raw = rec.digest.created_at ?? rec.created_at;
    const date = raw ? new Date(raw) : new Date(0);
    if (date.toDateString() === today.toDateString()) {
      groups.today.push(rec);
    } else if (date.toDateString() === yesterday.toDateString()) {
      groups.yesterday.push(rec);
    } else {
      groups.earlier.push(rec);
    }
  });

  return (
    <div className="space-y-14 sm:space-y-16">
      {groups.today.length > 0 && (
        <FeedSection title="Today" items={groups.today} defaultOpen />
      )}
      {groups.yesterday.length > 0 && (
        <FeedSection title="Yesterday" items={groups.yesterday} />
      )}
      {groups.earlier.length > 0 && (
        <FeedSection title="Archive" items={groups.earlier} />
      )}
    </div>
  );
}

function FeedSection({
  title,
  items,
  defaultOpen = false,
}: {
  title: string;
  items: RecWithDigest[];
  defaultOpen?: boolean;
}) {
  return (
    <details className="group" open={defaultOpen}>
      <summary className="flex cursor-pointer items-center gap-4 mb-7 sm:mb-9 list-none [&::-webkit-details-marker]:hidden">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-line bg-surface-raised shadow-sm group-open:bg-accent-soft group-open:border-accent/30 transition-colors">
          <ChevronDown
            className="w-[1.0625rem] h-[1.0625rem] text-ink-muted group-open:rotate-180 transition-transform duration-200"
            strokeWidth={2}
          />
        </span>
        <h2 className="font-display text-[clamp(1.22rem,2.4vw,1.72rem)] tracking-tight">{title}</h2>
        <span className="h-px flex-1 bg-linear-to-r from-line to-transparent min-w-[1.75rem]" aria-hidden />
        <span className="text-[0.8125rem] text-ink-faint tabular-nums shrink-0 font-medium">
          {items.length} {items.length === 1 ? "item" : "items"}
        </span>
      </summary>

      <div className="grid gap-6 sm:gap-7 md:grid-cols-2 xl:grid-cols-3">
        {items.map((rec) => {
          const displayedAt = rec.digest.created_at ?? rec.created_at;
          const laneSx = digestLaneStyles(rec.digest.article_type);
          const scoreNum = Number(rec.relevance_score);
          const scoreHue =
            scoreNum >= 8
              ? "text-emerald-400/97"
              : scoreNum >= 6
                ? "text-accent"
                : "text-amber-300/93";

          return (
            <article
              key={rec.id}
              className={cn(
                "group/card relative isolate flex flex-col rounded-2xl border border-line/95 bg-surface-raised/92 backdrop-blur-[2px]",
                "p-5 sm:p-6 lg:p-[1.375rem]",
                "transition-[border-color,transform,box-shadow] duration-200",
                "hover:border-accent/30 hover:-translate-y-0.5",
                "hover:shadow-[0_28px_70px_-40px_rgb(15_23_42/0.95)]",
                laneSx.cardRail,
              )}
            >
              <div className="flex items-center justify-between gap-3 mb-3.5">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={laneSx.pill}>{digestLaneHumanLabel(laneSx.lane)}</span>
                  <span className="text-[10px] font-medium uppercase tracking-wider text-ink-faint/80 truncate">
                    {rec.digest.article_type.replace(/_/g, " · ")}
                  </span>
                </div>
                <span
                  className={cn("text-[0.9rem] font-bold tabular-nums shrink-0", scoreHue)}
                  title="Curator relevance"
                >
                  {scoreNum.toFixed(1)}
                </span>
              </div>

              <h3 className="font-display text-[1.12rem] sm:text-[1.2rem] leading-snug mb-4">
                <a
                  href={rec.digest.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ink hover:text-accent transition-colors underline-offset-[5px] hover:underline inline-flex gap-2 items-start"
                >
                  {rec.digest.title}
                  <ArrowUpRight
                    className="w-[1.0625rem] h-[1.0625rem] shrink-0 mt-0.5 opacity-38 group-hover/card:opacity-100 transition-opacity"
                    strokeWidth={2}
                    aria-hidden
                  />
                </a>
              </h3>

              <p className="digest-prose line-clamp-4 mb-5 flex-1 text-[0.9425rem] leading-relaxed text-ink-muted">
                {rec.digest.summary}
              </p>

              <blockquote className="text-[0.8125rem] leading-relaxed text-ink-muted/95 border-l-[3px] border-accent/42 pl-3.5 mb-6 italic">
                {rec.reasoning}
              </blockquote>

              <div className="mt-auto flex items-center gap-2 text-[11px] font-semibold text-ink-faint pt-5 border-t border-line/85 uppercase tracking-[0.12em]">
                <Clock className="w-3.5 h-3.5 shrink-0" strokeWidth={2} aria-hidden />
                {displayedAt ? (
                  <time dateTime={displayedAt.toISOString()}>
                    {displayedAt.toLocaleDateString(undefined, {
                      weekday: "short",
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </time>
                ) : (
                  <span className="normal-case tracking-normal opacity-65">Date pending</span>
                )}
                <ExternalLink
                  className="w-3.5 h-3.5 ml-auto opacity-0 group-hover/card:opacity-55 transition-opacity"
                  strokeWidth={2}
                  aria-hidden
                />
              </div>
            </article>
          );
        })}
      </div>
    </details>
  );
}
