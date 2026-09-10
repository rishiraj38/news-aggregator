import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Check, Sparkles } from "lucide-react";
import Navbar from "@/components/Navbar";
import UpgradeRequestButton from "@/components/UpgradeRequestButton";
import { getCurrentDbUser } from "@/lib/admin-auth";
import { effectiveTier, isAdminRole, TIER_LABELS } from "@/lib/entitlements";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Upgrade to Pro · Helix",
  robots: { index: false, follow: false },
};

const FREE_FEATURES = [
  "A curated daily briefing",
  "Every topic bundle, mixed for you",
  "Your dashboard of past picks",
];

const PRO_FEATURES = [
  "Everything in Free",
  "Choose exactly which topic bundles you get",
  "Private keyword tracking across news and Hacker News",
  "Keyword matches reserved in every briefing",
  "No trial expiry",
];

function FeatureList({ items, tone }: { items: string[]; tone: "free" | "pro" }) {
  return (
    <ul className="space-y-3 text-sm text-ink-muted">
      {items.map((item) => (
        <li key={item} className="flex gap-3">
          <Check
            className={cn("w-4 h-4 shrink-0 mt-0.5", tone === "pro" ? "text-violet-300" : "text-accent")}
            strokeWidth={2}
            aria-hidden
          />
          {item}
        </li>
      ))}
    </ul>
  );
}

export default async function UpgradePage() {
  // Middleware guarantees a signed-in visitor; a missing row means the account
  // hasn't been synced yet, which the dashboard does on first visit.
  const user = await getCurrentDbUser();
  if (!user) redirect("/dashboard");

  const tier = effectiveTier(user.role, user.plan);
  const isFree = tier === "free";

  return (
    <div className="relative z-10 min-h-dvh bg-surface-deep text-ink overflow-x-hidden">
      <Navbar isAdmin={isAdminRole(user.role)} />
      <main className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-10 pt-[calc(5rem+env(safe-area-inset-top))] pb-16 sm:pb-24 space-y-10">
        <header className="space-y-3">
          <p className="text-[0.7rem] uppercase tracking-[0.28em] text-ink-faint font-semibold flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-violet-300" strokeWidth={2} aria-hidden />
            Helix Pro
          </p>
          <h1 className="font-display text-[clamp(2rem,4.6vw,3.05rem)] tracking-[-0.03em] leading-[1.05]">
            {isFree ? "Upgrade to Pro" : "You already have Pro"}
          </h1>
          <p className="text-[0.9625rem] text-ink-muted leading-relaxed max-w-[38rem]">
            {isFree
              ? "Make the briefing yours: pick the bundles you care about and track any company, person, or technology."
              : `Your account is on the ${TIER_LABELS[tier]} plan, so every Pro feature is already unlocked.`}
          </p>
        </header>

        <div className="grid gap-5 md:grid-cols-2">
          <article className="rounded-2xl border border-line bg-surface/80 p-7 flex flex-col gap-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-display text-xl">Free</h2>
              {isFree && (
                <span className="rounded-full border border-line-strong px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-ink-faint">
                  Your plan
                </span>
              )}
            </div>
            <p className="font-display text-4xl">$0</p>
            <FeatureList items={FREE_FEATURES} tone="free" />
          </article>

          <article className="rounded-2xl border border-violet-400/40 bg-surface-raised p-7 flex flex-col gap-5 ring-1 ring-violet-400/15">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-display text-xl">Pro</h2>
              {!isFree && (
                <span className="rounded-full border border-violet-400/40 bg-violet-500/[0.12] px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-violet-300">
                  Your plan
                </span>
              )}
            </div>
            <p className="font-display text-4xl">
              $7<span className="text-lg font-sans font-normal text-ink-muted">/mo</span>
            </p>
            <FeatureList items={PRO_FEATURES} tone="pro" />
          </article>
        </div>

        {isFree ? (
          <section className="rounded-2xl border border-violet-400/30 bg-violet-500/[0.05] p-6 sm:p-8 space-y-4">
            <h2 className="font-display text-xl">Request Pro access</h2>
            <p className="text-sm text-ink-muted leading-relaxed max-w-[36rem]">
              Payments aren&rsquo;t live yet. During early access, send a request and an admin will switch your
              account to Pro — no card needed.
            </p>
            <UpgradeRequestButton initialRequestedAt={user.pro_requested_at?.toISOString() ?? null} />
          </section>
        ) : (
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center min-h-11 px-6 rounded-xl bg-accent text-surface-deep text-sm font-semibold hover:brightness-110 transition-[filter]"
          >
            Back to your dashboard
          </Link>
        )}
      </main>
    </div>
  );
}
