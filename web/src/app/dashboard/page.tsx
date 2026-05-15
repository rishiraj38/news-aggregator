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
} from "lucide-react";
import { PipelineStatus } from "@/components/PipelineStatus";
import type { Digest, Recommendation } from "@prisma/client";

type RecWithDigest = Recommendation & { digest: Digest };

export default async function Dashboard() {
  const user = await currentUser();

  if (!user) {
    redirect("/sign-in");
  }

  let dbUser = await db.user.findUnique({
    where: { email: user.emailAddresses[0].emailAddress },
  });

  if (!dbUser) {
    const email = user.emailAddresses[0].emailAddress;
    const name = `${user.firstName} ${user.lastName}`.trim() || "Anonymous";

    const defaultPrefs = JSON.stringify({
      interests: ["LLMs", "Generative AI", "Tech News"],
      config: { prefer_technical_depth: true },
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

  return (
    <div className="relative z-10 min-h-dvh bg-surface-deep text-ink">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-[calc(5rem+env(safe-area-inset-top))] pb-16 sm:pb-24">
        <header className="mb-10 sm:mb-12 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6 border-b border-line pb-8">
          <div className="max-w-2xl">
            <p className="text-[0.8125rem] uppercase tracking-[0.2em] text-ink-faint font-medium mb-3">
              Your digest
            </p>
            <h1 className="font-display text-[clamp(1.85rem,4vw,2.65rem)] tracking-tight leading-tight mb-3">
              Morning briefing
            </h1>
            <p className="text-ink-muted leading-relaxed">
              <span className="text-ink font-medium">{user.firstName}</span>, here is what the curator surfaced recently—newest first within each day.
            </p>
          </div>
          <div
            className={`inline-flex items-center self-start px-4 py-2 rounded-md border text-sm font-medium ${
              dbUser?.role === "admin"
                ? "border-accent/40 bg-accent-soft text-ink"
                : "border-line-strong bg-surface-raised text-ink-muted"
            }`}
          >
            <Sparkles className="w-4 h-4 mr-2 text-accent shrink-0" strokeWidth={1.75} />
            {dbUser?.role === "admin" ? "Administrator" : "Explorer plan"}
          </div>
        </header>

        {dbUser?.role === "admin" && (
          <div className="mb-10">
            <PipelineStatus />
          </div>
        )}

        <section className="mb-12 rounded-lg border border-line bg-surface p-6 sm:p-8">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-8">
            <div className="min-w-0 flex-1">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-faint mb-4 flex flex-wrap items-center gap-2">
                Active filters
                {dbUser?.role === "admin" ? (
                  <span className="text-[0.6875rem] font-medium normal-case px-2 py-0.5 rounded border border-accent/35 bg-accent-soft text-ink">
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
                    const interests = prefs.interests || ["Tech News"];
                    return interests.map((tag: string) => (
                      <span
                        key={tag}
                        className="px-3 py-1.5 rounded-md bg-surface-raised text-sm text-ink-muted border border-line"
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
                  className="px-3 py-1.5 rounded-md border border-dashed border-line-strong text-sm text-ink-faint cursor-default"
                  title={dbUser?.role === "admin" ? "Managed in admin tools" : "Upgrade to customize"}
                >
                  + Keyword
                </span>
              </div>
            </div>
            <div className="shrink-0 lg:text-right">
              {dbUser?.role === "admin" ? (
                <button
                  type="button"
                  className="inline-flex items-center gap-2 min-h-11 px-5 rounded-md bg-accent text-surface-deep text-sm font-semibold hover:brightness-110 transition-[filter]"
                >
                  <Sparkles className="w-4 h-4" strokeWidth={2} />
                  Manage keywords
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 min-h-11 px-5 rounded-md border border-line-strong bg-surface-raised text-sm font-semibold text-ink hover:border-accent/35 transition-colors"
                  >
                    Customize (upgrade)
                  </button>
                  <p className="text-xs text-ink-faint mt-2">
                    Unlock custom themes on Full access.
                  </p>
                </>
              )}
            </div>
          </div>
        </section>

        {recommendations.length === 0 ? (
          <div className="rounded-lg border border-line bg-surface px-8 py-16 text-center">
            <Sparkles className="w-11 h-11 mx-auto mb-5 text-accent/90" strokeWidth={1.25} />
            <h2 className="font-display text-2xl tracking-tight mb-3">
              Pipeline registered you
            </h2>
            <p className="text-ink-muted max-w-md mx-auto leading-relaxed mb-8">
              The daily job ingests sources overnight. When the first digest lands for your profile, it will show up here—no refresh tricks required.
            </p>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-line-strong bg-surface-raised text-sm text-ink-muted">
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
    <div className="space-y-12 sm:space-y-14">
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
      <summary className="flex cursor-pointer items-center gap-3 mb-6 sm:mb-8 list-none [&::-webkit-details-marker]:hidden">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-line bg-surface-raised group-open:bg-accent-soft group-open:border-accent/25 transition-colors">
          <ChevronDown
            className="w-4 h-4 text-ink-muted group-open:rotate-180 transition-transform duration-200"
            strokeWidth={2}
          />
        </span>
        <h2 className="font-display text-xl sm:text-2xl tracking-tight">{title}</h2>
        <span className="h-px flex-1 bg-line min-w-[2rem]" aria-hidden />
        <span className="text-sm text-ink-faint tabular-nums shrink-0">
          {items.length} {items.length === 1 ? "item" : "items"}
        </span>
      </summary>

      <div className="grid gap-5 sm:gap-6 md:grid-cols-2 xl:grid-cols-3">
        {items.map((rec) => {
          const displayedAt = rec.digest.created_at ?? rec.created_at;
          return (
          <article
            key={rec.id}
            className="group/card relative flex flex-col rounded-lg border border-line bg-surface-raised p-5 sm:p-6 transition-[border-color,box-shadow] hover:border-line-strong hover:shadow-[0_18px_40px_-28px_rgba(0,0,0,0.75)]"
          >
            <div className="flex items-start justify-between gap-3 mb-4">
              <span className="inline-flex items-center px-2 py-1 rounded text-[0.6875rem] font-semibold uppercase tracking-wider bg-surface-deep border border-line text-ink-faint">
                {rec.digest.article_type}
              </span>
              <span
                className={`text-sm font-semibold tabular-nums shrink-0 ${
                  Number(rec.relevance_score) >= 8 ? "text-emerald-400/95" : "text-accent"
                }`}
              >
                {Number(rec.relevance_score).toFixed(1)}
              </span>
            </div>

            <h3 className="font-display text-[1.125rem] sm:text-[1.2rem] leading-snug mb-3 pr-6">
              <a
                href={rec.digest.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-ink hover:text-accent transition-colors underline-offset-4 hover:underline inline-flex gap-1 items-start"
              >
                {rec.digest.title}
                <ArrowUpRight
                  className="w-4 h-4 shrink-0 mt-0.5 opacity-40 group-hover/card:opacity-100 transition-opacity"
                  strokeWidth={2}
                  aria-hidden
                />
              </a>
            </h3>

            <p className="digest-prose line-clamp-4 mb-5 flex-1">{rec.digest.summary}</p>

            <blockquote className="text-[0.8125rem] leading-relaxed text-ink-muted border-l-2 border-accent/40 pl-3 mb-6 italic">
              {rec.reasoning}
            </blockquote>

            <div className="mt-auto flex items-center gap-2 text-xs font-medium text-ink-faint pt-4 border-t border-line">
              <Clock className="w-3.5 h-3.5 shrink-0" strokeWidth={2} />
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
                  <span>—</span>
                )}
              <ExternalLink className="w-3.5 h-3.5 ml-auto opacity-0 group-hover/card:opacity-60 transition-opacity" strokeWidth={2} aria-hidden />
            </div>
          </article>
          );
        })}
      </div>
    </details>
  );
}
