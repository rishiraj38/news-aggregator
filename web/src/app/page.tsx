import Link from "next/link";
import Navbar from "@/components/Navbar";
import SiteFooter from "@/components/SiteFooter";
import {
  ArrowRight,
  BookOpen,
  Check,
  Cpu,
  Instagram,
  Mail,
  Radio,
  ScanSearch,
  Sparkles,
} from "lucide-react";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { SITE_INSTAGRAM_HREF } from "@/lib/site";

export default async function Home() {
  const { userId } = await auth();

  if (userId) {
    redirect("/dashboard");
  }

  return (
    <div className="relative z-10 min-h-dvh bg-surface-deep text-ink overflow-x-hidden">
      <Navbar />

      <main>
        {/* Hero */}
        <section className="relative pt-[calc(5rem+env(safe-area-inset-top))] pb-20 sm:pb-28 px-4 sm:px-6 lg:px-8">
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-[min(85vh,900px)] helix-aurora opacity-70"
            aria-hidden
          />
          <div
            className="pointer-events-none absolute inset-x-0 top-[4rem] h-[560px] helix-grid opacity-25"
            aria-hidden
          />

          <div className="max-w-6xl mx-auto relative">
            <div className="flex flex-wrap items-center gap-3 mb-8">
              <span className="inline-flex items-center gap-2 rounded-full border border-line-strong bg-surface-raised/80 backdrop-blur-sm px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-muted">
                <Sparkles className="w-3.5 h-3.5 text-accent" strokeWidth={2} aria-hidden />
                Helix v1
              </span>
              <span className="text-xs text-ink-faint tracking-wide hidden sm:inline">
                Curator-grade · Ships daily · No doom-scroll
              </span>
            </div>

            <div className="max-w-[46rem]">
              <h1 className="font-display text-[clamp(2.5rem,6.8vw,4rem)] leading-[1.04] tracking-tight text-ink mb-6 animate-helix-float">
                Signal you can&nbsp;
                <span className="text-transparent bg-clip-text bg-linear-to-br from-brand via-accent to-brand-deep">
                  defend in a meeting
                </span>
                <span className="block mt-3 text-[0.92em] font-normal italic text-ink-muted">
                  — distilled from transcripts, RSS, and repos, ranked to your lane.
                </span>
              </h1>

              <p className="text-lg sm:text-[1.175rem] text-ink-muted leading-[1.7] max-w-2xl mb-10">
                Helix ingests the technical wild, reads your curator profile once, then serves a
                restrained morning dossier: what moved, why it echoes your backlog, where to drill
                deeper when you&apos;re caffeinated - not when you&apos;re mid-deploy.
              </p>

              <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 mb-11">
                <Link
                  href="/sign-up"
                  className="group inline-flex items-center justify-center gap-2 min-h-12 px-8 rounded-xl bg-accent text-surface-deep font-semibold text-[0.9375rem] hover:brightness-110 shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_16px_40px_-20px_rgba(212,175,55,0.55)] transition-[filter,transform] active:scale-[0.99]"
                >
                  Start free
                  <ArrowRight
                    className="w-4 h-4 group-hover:translate-x-0.5 transition-transform"
                    strokeWidth={2}
                  />
                </Link>
                <a
                  href={SITE_INSTAGRAM_HREF}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-insta-gradient group inline-flex items-center justify-center gap-2 min-h-12 px-8 rounded-xl border border-line-strong bg-surface-raised/60 backdrop-blur-sm text-ink font-medium text-[0.9375rem]"
                >
                  <Instagram className="w-[1.125rem] h-[1.125rem]" strokeWidth={2} aria-hidden />
                  <span>Breaking visuals on IG</span>
                </a>
              </div>

              <div className="flex flex-wrap items-center gap-x-5 gap-y-3 text-[13px] text-ink-faint mb-8">
                <span className="inline-flex items-center gap-2 border border-line px-3 py-1.5 rounded-lg bg-surface/50">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400/90 shadow-[0_0_8px_rgba(52,211,153,0.5)]" />
                  Digest pipeline monitored
                </span>
                <span className="text-ink-muted">Multi-source · Personalized · Email-first</span>
              </div>
            </div>

            <div className="mt-20 sm:mt-28 grid sm:grid-cols-3 gap-3 sm:gap-0 rounded-2xl overflow-hidden border border-line bg-surface-raised/30 backdrop-blur-md">
              {[
                { label: "Ingest breadth", value: "Feeds · video · repos", hint: "normalized nightly" },
                { label: "Rank model", value: "Profile-aligned", hint: "score + curator reasoning" },
                { label: "Surfaces", value: "Inbox · this app", hint: "+ Instagram flashes" },
              ].map((stat, i) => (
                <div
                  key={stat.label}
                  className={`px-6 py-7 sm:px-8 ${i !== 2 ? "sm:border-r border-line" : ""} border-b sm:border-b-0 border-line`}
                >
                  <p className="text-[11px] uppercase tracking-[0.2em] text-ink-faint mb-3">
                    {stat.label}
                  </p>
                  <p className="font-display text-xl sm:text-2xl text-ink mb-1.5 leading-snug">
                    {stat.value}
                  </p>
                  <p className="text-sm text-ink-muted">{stat.hint}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How */}
        <section
          id="how-it-works"
          className="relative py-20 sm:py-28 px-4 sm:px-6 lg:px-8 border-y border-line bg-surface/80"
        >
          <div className="max-w-6xl mx-auto">
            <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-10 mb-16 sm:mb-20">
              <div className="max-w-xl">
                <h2 className="font-display text-[clamp(1.85rem,3.5vw,2.625rem)] tracking-tight mb-4">
                  A pipeline modeled like&nbsp;
                  <span className="text-brand">newsroom choreography</span>
                </h2>
                <p className="text-ink-muted leading-[1.7] text-[1.05rem]">
                  Every stage exposes its intent: capture is dumb, relevance is deliberate, summaries
                  are scoped, delivery is deterministic. Tune one layer without rewriting the saga.
                </p>
              </div>
              <p className="text-sm text-ink-faint lg:text-right lg:max-w-[14rem] leading-relaxed border-l lg:border-l-0 lg:border-r border-line pl-5 lg:pl-0 lg:pr-6">
                Truth lives in originals - Helix is the compass, not the substitute librarian.
              </p>
            </div>

            <div className="grid md:grid-cols-2 xl:grid-cols-12 gap-4 sm:gap-5">
              {[
                {
                  icon: Radio,
                  title: "Ingest",
                  body: "RSS and transcripts flattened into comparable signal - duplicate hosts culled aggressively.",
                  span: "xl:col-span-5",
                },
                {
                  icon: ScanSearch,
                  title: "Rank",
                  body: "Scores tether to YOUR interests; every card ships a curator explanation you can skim or ignore.",
                  span: "xl:col-span-7 xl:min-h-[200px]",
                },
                {
                  icon: Cpu,
                  title: "Summarize",
                  body: "Dense blurbs - not tweet-length SEO - preserve nouns engineers search for.",
                  span: "xl:col-span-7 xl:min-h-[200px]",
                },
                {
                  icon: Mail,
                  title: "Deliver",
                  body: "Overnight cron, inbox artifact, synced web surface. Instagram gets the billboard version.",
                  span: "xl:col-span-5",
                },
              ].map(({ icon: Icon, title, body, span }) => (
                <article
                  key={title}
                  className={`rounded-2xl border border-line bg-surface-deep/60 backdrop-blur-sm p-7 sm:p-8 flex flex-col gap-5 hover:border-line-strong hover:shadow-[0_28px_60px_-40px_rgba(99,102,241,0.35)] transition-all duration-300 ${span}`}
                >
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-subtle border border-brand/15">
                    <Icon className="w-6 h-6 text-brand stroke-[1.35]" aria-hidden />
                  </div>
                  <div>
                    <h3 className="font-display text-lg sm:text-xl text-ink mb-2">{title}</h3>
                    <p className="text-[0.9375rem] text-ink-muted leading-relaxed">{body}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Practitioners + code */}
        <section className="py-20 sm:py-28 px-4 sm:px-6 lg:px-8">
          <div className="max-w-6xl mx-auto grid lg:grid-cols-12 gap-14 lg:gap-18 items-start">
            <div className="lg:col-span-5 lg:sticky lg:top-[6.25rem]">
              <BookOpen className="w-10 h-10 text-accent mb-6 stroke-[1.15]" aria-hidden />
              <h2 className="font-display text-[clamp(1.85rem,3.5vw,2.5rem)] tracking-tight mb-5">
                Tuned for people who merge before breakfast
              </h2>
              <p className="text-ink-muted leading-[1.7] mb-7 text-[1.05rem]">
                Designers shipping tokens, infra wrangling quotas, founders reading between hype
                cycles - everyone drowning in novelty. Helix trims the bulletin to narratives that fold
                into your quarter, not trending widgets.
              </p>
              <ul className="space-y-3.5 text-[0.9375rem] text-ink-muted">
                {[
                  "Primary-source bias when feeds allow it.",
                  "Reasoning strings travel with relevance scores.",
                  "UI quiets chrome so copy leads.",
                ].map((t) => (
                  <li key={t} className="flex gap-3">
                    <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
            <div className="lg:col-span-7 rounded-2xl border border-line-strong bg-linear-to-br from-surface-raised via-surface-deep to-surface-raised p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
              <div className="rounded-[0.875rem] border border-line bg-[#070605] p-7 sm:p-10 font-mono text-[13px] leading-relaxed text-ink-muted overflow-x-auto">
                <p className="text-ink-faint mb-5 border-b border-line pb-4 flex justify-between gap-4">
                  <span>digest.preview.yaml</span>
                  <span className="text-brand/80">live window</span>
                </p>
                <pre className="whitespace-pre text-[12.5px] sm:text-[13px]">
                  {`run_date: ${new Date().toISOString().slice(0, 10)}
edition: helix-v1
profile_bias:
  tempo: deliberate
  stack_hints: [systems, evals, product craft]

featured:
  headline: "When eval harnesses behave like flaky CI"
  relevance_score: 9.2
  curator_note: >
    Mirrors how teams regress prompt drift - worth comparing
    to your current offline eval notebooks before next retro.`}
                </pre>
              </div>
            </div>
          </div>
        </section>

        {/* Instagram CTA ribbon */}
        <section className="py-16 sm:py-20 px-4 sm:px-6 lg:px-8">
          <div className="max-w-6xl mx-auto relative overflow-hidden rounded-3xl border border-brand/25 bg-linear-to-r from-brand-deep/40 via-surface-raised to-brand-deep/30 p-[1px]">
            <div className="rounded-[calc(1.5rem-1px)] bg-surface-deep/90 backdrop-blur-xl px-8 py-12 sm:px-12 sm:py-14 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-8">
              <div className="max-w-xl">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-brand mb-3">
                  Between digests
                </p>
                <h2 className="font-display text-2xl sm:text-3xl tracking-tight mb-3">
                  Follow the faster visual wire
                </h2>
                <p className="text-ink-muted leading-relaxed">
                  We post breaking cards and caption-sized context on Instagram - same rigor, built for
                  thumb-scrolling between meetings.
                </p>
              </div>
              <a
                href={SITE_INSTAGRAM_HREF}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-insta-gradient group inline-flex items-center justify-center gap-2.5 min-h-12 px-8 rounded-xl bg-ink text-surface-deep font-semibold text-sm shrink-0 border border-transparent shadow-[0_18px_40px_-18px_rgba(240,235,227,0.35)]"
              >
                <Instagram className="w-5 h-5" strokeWidth={2} aria-hidden />
                <span>@formula1_boys_69</span>
              </a>
            </div>
          </div>
        </section>

        {/* Pricing */}
        <section id="pricing" className="py-20 sm:py-28 px-4 sm:px-6 lg:px-8 bg-surface border-y border-line">
          <div className="max-w-6xl mx-auto">
            <header className="max-w-2xl mb-14 sm:mb-16">
              <h2 className="font-display text-[clamp(1.85rem,3.5vw,2.625rem)] tracking-tight mb-4">
                Plans that stay out of your way
              </h2>
              <p className="text-ink-muted leading-[1.7] text-[1.05rem]">
                Start where you are. Upgrade when the archive, keyword depth, and delivery windows
                become part of your muscle memory.
              </p>
            </header>

            <div className="grid md:grid-cols-2 gap-6 lg:gap-8 max-w-4xl">
              <article className="rounded-2xl border border-line bg-surface-deep/80 p-9 flex flex-col ring-1 ring-white/[0.03]">
                <h3 className="font-display text-xl mb-2">Explorer</h3>
                <p className="font-display text-4xl text-ink mb-1">$0</p>
                <p className="text-sm text-ink-muted mb-9">Lean daily briefing - perfect for taste-testing.</p>
                <ul className="space-y-3 text-sm text-ink-muted mb-11 grow">
                  <li className="flex gap-3">
                    <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                    Curated top articles each run
                  </li>
                  <li className="flex gap-3">
                    <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                    Web surface for revisiting
                  </li>
                </ul>
                <Link
                  href="/sign-up"
                  className="inline-flex justify-center items-center min-h-11 rounded-xl border border-line-strong text-sm font-semibold hover:bg-surface-raised transition-colors"
                >
                  Create account
                </Link>
              </article>

              <article className="rounded-2xl border border-accent/40 bg-surface-raised p-9 flex flex-col relative overflow-hidden shadow-[0_32px_80px_-40px_rgba(212,175,55,0.35)] ring-1 ring-accent/15">
                <div className="absolute top-0 right-0 px-3.5 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] bg-accent text-surface-deep">
                  Most chosen
                </div>
                <h3 className="font-display text-xl mb-2">Full access</h3>
                <p className="font-display text-4xl text-ink mb-1">
                  $7<span className="text-lg font-sans font-normal text-ink-muted">/mo</span>
                </p>
                <p className="text-sm text-ink-muted mb-9">
                  For readers who treat RSS like oxygen and want Helix to scale with them.
                </p>
                <ul className="space-y-3 text-sm text-ink-muted mb-11 grow">
                  {[
                    "Full digest archive on the web",
                    "Custom keyword tracking",
                    "Paper + repo oriented pulls",
                    "Priority delivery windows",
                  ].map((t) => (
                    <li key={t} className="flex gap-3">
                      <Check className="w-4 h-4 shrink-0 mt-0.5 text-accent" strokeWidth={2} />
                      {t}
                    </li>
                  ))}
                </ul>
                <Link
                  href="/sign-up"
                  className="inline-flex justify-center items-center min-h-11 rounded-xl bg-accent text-surface-deep text-sm font-semibold hover:brightness-110 transition-[filter]"
                >
                  Start seven-day trial
                </Link>
              </article>
            </div>
          </div>
        </section>

        {/* Closing CTA */}
        <section className="py-16 sm:py-20 px-4 sm:px-6 lg:px-8">
          <div className="max-w-6xl mx-auto text-center px-6 py-14 rounded-3xl border border-line bg-surface-raised/40 backdrop-blur-sm">
            <p className="font-display text-2xl sm:text-[1.75rem] text-ink mb-4 tracking-tight">
              Let your inbox feel edited again.
            </p>
            <p className="text-ink-muted max-w-lg mx-auto mb-8 text-[1.025rem]">
              Two minutes with Helix replaces twenty tabs of “might be relevant.”
            </p>
            <Link
              href="/sign-up"
              className="inline-flex items-center gap-2 min-h-12 px-9 rounded-xl bg-accent text-surface-deep font-semibold hover:brightness-110 transition-[filter]"
            >
              Ship me the digest <ArrowRight className="w-4 h-4" strokeWidth={2} />
            </Link>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
