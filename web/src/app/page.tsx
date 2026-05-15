import Link from "next/link";
import Navbar from "@/components/Navbar";
import SiteFooter from "@/components/SiteFooter";
import {
  ArrowRight,
  BookOpen,
  Check,
  Cpu,
  Mail,
  Radio,
  ScanSearch,
} from "lucide-react";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export default async function Home() {
  const { userId } = await auth();

  if (userId) {
    redirect("/dashboard");
  }

  return (
    <div className="relative z-10 min-h-dvh bg-surface-deep text-ink">
      <Navbar />

      <main>
        <section className="pt-[calc(5rem+env(safe-area-inset-top))] pb-16 sm:pb-24 px-4 sm:px-6 lg:px-8">
          <div className="max-w-6xl mx-auto">
            <div className="max-w-3xl">
              <p className="text-[0.8125rem] uppercase tracking-[0.22em] text-ink-faint font-medium mb-6">
                Daily digest · Technical sources · Ranked for you
              </p>
              <h1 className="font-display text-[clamp(2.35rem,6vw,3.85rem)] leading-[1.08] tracking-tight text-ink mb-6">
                Read less noise.
                <span className="block text-ink-muted mt-1 font-normal italic">
                  Keep the signal that advances your craft.
                </span>
              </h1>
              <p className="text-lg sm:text-xl text-ink-muted leading-relaxed max-w-2xl mb-10">
                Helix pulls from RSS feeds and long-form transcripts, scores items
                against your profile, and sends a tight briefing—so your mornings
                start with substance, not endless tabs.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
                <Link
                  href="/sign-up"
                  className="inline-flex items-center justify-center gap-2 min-h-12 px-7 rounded-md bg-accent text-surface-deep font-semibold text-[0.9375rem] hover:brightness-110 transition-[filter] shadow-[0_1px_0_rgba(255,255,255,0.12)_inset]"
                >
                  Begin free <ArrowRight className="w-4 h-4" strokeWidth={2} />
                </Link>
                <Link
                  href="#how-it-works"
                  className="inline-flex items-center justify-center min-h-12 px-7 rounded-md border border-line-strong text-ink-muted hover:text-ink hover:border-accent/40 hover:bg-accent-soft transition-colors text-[0.9375rem] font-medium"
                >
                  How it works
                </Link>
              </div>
            </div>

            <div className="mt-16 sm:mt-24 grid sm:grid-cols-3 gap-px bg-line rounded-lg overflow-hidden border border-line">
              {[
                { label: "Sources scanned", value: "Multi-feed", hint: "blogs · repos · papers" },
                { label: "Delivery", value: "Email + web", hint: "same digest, two surfaces" },
                { label: "Cadence", value: "Daily run", hint: "scheduled pipeline" },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="bg-surface px-5 py-6 sm:py-8 sm:px-7"
                >
                  <p className="text-xs uppercase tracking-wider text-ink-faint mb-2">
                    {stat.label}
                  </p>
                  <p className="font-display text-2xl sm:text-[1.65rem] text-ink mb-1">
                    {stat.value}
                  </p>
                  <p className="text-sm text-ink-muted">{stat.hint}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section
          id="how-it-works"
          className="py-16 sm:py-24 px-4 sm:px-6 lg:px-8 border-y border-line bg-surface"
        >
          <div className="max-w-6xl mx-auto">
            <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-8 mb-14 sm:mb-16">
              <div className="max-w-xl">
                <h2 className="font-display text-3xl sm:text-[2.125rem] tracking-tight mb-4">
                  A pipeline shaped like an editor&apos;s desk
                </h2>
                <p className="text-ink-muted leading-relaxed">
                  Ingestion, relevance scoring, and summarization stay separate—so
                  each stage can be tuned without turning the whole product into a
                  black box.
                </p>
              </div>
              <p className="text-sm text-ink-faint lg:text-right lg:max-w-xs leading-relaxed">
                Nothing here replaces clicking through to originals when the topic
                deserves depth.
              </p>
            </div>

            <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-5">
              {[
                {
                  icon: Radio,
                  title: "Ingest",
                  body: "RSS and transcripts normalized into one comparable stream.",
                },
                {
                  icon: ScanSearch,
                  title: "Rank",
                  body: "Scores reflect your stated interests—not generic hype metrics.",
                },
                {
                  icon: Cpu,
                  title: "Summarize",
                  body: "Structured outputs keep blurbs factual and skimmable.",
                },
                {
                  icon: Mail,
                  title: "Deliver",
                  body: "Land in your inbox on schedule; revisit anytime on the web.",
                },
              ].map(({ icon: Icon, title, body }) => (
                <article
                  key={title}
                  className="rounded-lg border border-line bg-surface-raised p-6 flex flex-col gap-4 hover:border-line-strong transition-colors"
                >
                  <Icon className="w-8 h-8 text-accent stroke-[1.25]" aria-hidden />
                  <div>
                    <h3 className="font-semibold text-ink mb-2">{title}</h3>
                    <p className="text-sm text-ink-muted leading-relaxed">{body}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="py-16 sm:py-24 px-4 sm:px-6 lg:px-8">
          <div className="max-w-6xl mx-auto grid lg:grid-cols-12 gap-12 lg:gap-16 items-start">
            <div className="lg:col-span-5 lg:sticky lg:top-28">
              <BookOpen className="w-9 h-9 text-accent mb-6 stroke-[1.25]" aria-hidden />
              <h2 className="font-display text-3xl sm:text-[2.125rem] tracking-tight mb-4">
                Written for practitioners
              </h2>
              <p className="text-ink-muted leading-relaxed mb-6">
                If your week is patches, designs, and docs—you don&apos;t need
                another carousel of headlines. You need context on what changed and
                why it might matter next quarter.
              </p>
              <ul className="space-y-3 text-sm text-ink-muted">
                <li className="flex gap-3">
                  <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                  Primary-source bias where possible
                </li>
                <li className="flex gap-3">
                  <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                  Reasoning snippets—not opaque thumbs-up scores
                </li>
                <li className="flex gap-3">
                  <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                  Quiet UI that respects focus
                </li>
              </ul>
            </div>
            <div className="lg:col-span-7 rounded-lg border border-line bg-surface-raised p-6 sm:p-10 font-mono text-[0.8125rem] leading-relaxed text-ink-muted overflow-x-auto">
              <p className="text-ink-faint mb-4 border-b border-line pb-4">
                excerpt · digest_preview.yaml
              </p>
              <pre className="whitespace-pre">
{`run_date: ${new Date().toISOString().slice(0, 10)}
profile:
  depth: technical
  themes: [systems, ml_infra, languages]

top_pick:
  title: "Why bounded contexts survive refactors"
  relevance: 9.1
  takeaway: >
    Domain boundaries aligned with deployment units;
    migration notes cite strangler fig pattern.`}
              </pre>
            </div>
          </div>
        </section>

        <section id="pricing" className="py-16 sm:py-24 px-4 sm:px-6 lg:px-8 bg-surface border-y border-line">
          <div className="max-w-6xl mx-auto">
            <header className="max-w-xl mb-12 sm:mb-14">
              <h2 className="font-display text-3xl sm:text-[2.125rem] tracking-tight mb-3">
                Straightforward tiers
              </h2>
              <p className="text-ink-muted leading-relaxed">
                Start on the house plan; upgrade when you want the full surface area.
              </p>
            </header>

            <div className="grid md:grid-cols-2 gap-6 lg:gap-8 max-w-4xl">
              <article className="rounded-lg border border-line bg-surface-deep p-8 flex flex-col">
                <h3 className="font-display text-xl mb-2">Explorer</h3>
                <p className="font-display text-4xl text-ink mb-1">$0</p>
                <p className="text-sm text-ink-muted mb-8">Essential daily briefing.</p>
                <ul className="space-y-3 text-sm text-ink-muted mb-10 grow">
                  <li className="flex gap-3">
                    <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                    Top articles in each digest
                  </li>
                  <li className="flex gap-3">
                    <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                    Weekend recap where configured
                  </li>
                </ul>
                <Link
                  href="/sign-up"
                  className="inline-flex justify-center items-center min-h-11 rounded-md border border-line-strong text-sm font-semibold hover:bg-surface-raised transition-colors"
                >
                  Create account
                </Link>
              </article>

              <article className="rounded-lg border border-accent/35 bg-surface-raised p-8 flex flex-col relative overflow-hidden shadow-[0_0_0_1px_rgba(201,162,39,0.12)]">
                <div className="absolute top-0 right-0 px-3 py-1 text-[0.6875rem] font-semibold uppercase tracking-wider bg-accent text-surface-deep">
                  Popular
                </div>
                <h3 className="font-display text-xl mb-2">Full access</h3>
                <p className="font-display text-4xl text-ink mb-1">
                  $7<span className="text-lg font-sans font-normal text-ink-muted">/mo</span>
                </p>
                <p className="text-sm text-ink-muted mb-8">
                  Research-minded readers who live in RSS-shaped brains.
                </p>
                <ul className="space-y-3 text-sm text-ink-muted mb-10 grow">
                  <li className="flex gap-3">
                    <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                    Full digest archive on the web
                  </li>
                  <li className="flex gap-3">
                    <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                    Custom keyword tracking
                  </li>
                  <li className="flex gap-3">
                    <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                    Paper and repo oriented pulls
                  </li>
                  <li className="flex gap-3">
                    <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                    Priority delivery windows
                  </li>
                </ul>
                <Link
                  href="/sign-up"
                  className="inline-flex justify-center items-center min-h-11 rounded-md bg-accent text-surface-deep text-sm font-semibold hover:brightness-110 transition-[filter]"
                >
                  Start seven-day trial
                </Link>
              </article>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
