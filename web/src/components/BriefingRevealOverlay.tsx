"use client";

import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

/** Mark after the first onboarding reveal completes. */
const STORAGE_INTRO_DONE = "helix_briefing_intro_done";
/** Local calendar date `YYYY-MM-DD` of last daily welcome. */
const STORAGE_LAST_DAILY = "helix_briefing_last_daily_ymd";

export type BriefingRevealOverlayProps = {
  firstName: string;
  hasRecommendations: boolean;
  recommendationCountToday: number;
};

type Variant = "first" | "daily";

function localDateYmd(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function readVariant(): Variant | null {
  if (typeof window === "undefined") return null;
  try {
    const introDone = window.localStorage.getItem(STORAGE_INTRO_DONE);
    const lastDaily = window.localStorage.getItem(STORAGE_LAST_DAILY);
    const today = localDateYmd();
    if (introDone !== "1") return "first";
    if (lastDaily !== today) return "daily";
  } catch {
    return null;
  }
  return null;
}

function persistAfterReveal(variant: Variant) {
  try {
    if (variant === "first") window.localStorage.setItem(STORAGE_INTRO_DONE, "1");
    window.localStorage.setItem(STORAGE_LAST_DAILY, localDateYmd());
  } catch {
    /* private mode etc. */
  }
}

export default function BriefingRevealOverlay({
  firstName,
  hasRecommendations,
  recommendationCountToday,
}: BriefingRevealOverlayProps) {
  const [mounted, setMounted] = useState(false);
  const [variant, setVariant] = useState<Variant | null>(null);
  const [open, setOpen] = useState(false);
  const [entered, setEntered] = useState(false);
  const persistRef = useRef<Variant | null>(null);

  const reducedMotionRef = useRef(false);

  /** Commit exit + teardown + storage. */
  const finish = useCallback(() => {
    if (persistRef.current) persistAfterReveal(persistRef.current);
    persistRef.current = null;
    setOpen(false);
    setEntered(false);
    document.body.style.overflow = "";
  }, []);

  const dismiss = useCallback(() => {
    window.setTimeout(finish, 900);
    setEntered(false);
  }, [finish]);

  useEffect(() => {
    reducedMotionRef.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    startTransition(() => setMounted(true));
  }, []);

  useEffect(() => {
    if (!mounted) return;

    const v = readVariant();
    if (!v) return;

    if (reducedMotionRef.current) {
      persistAfterReveal(v);
      return;
    }

    persistRef.current = v;
    setVariant(v);
    setOpen(true);
    document.body.style.overflow = "hidden";

    const rafIds: number[] = [];
    rafIds.push(
      window.requestAnimationFrame(() => {
        rafIds.push(
          window.requestAnimationFrame(() => startTransition(() => setEntered(true))),
        );
      }),
    );

    const holdMs = v === "first" ? 3600 : 2400;

    const autoClose = window.setTimeout(() => {
      dismiss();
    }, holdMs + 950);

    return () => {
      rafIds.forEach((id) => window.cancelAnimationFrame(id));
      window.clearTimeout(autoClose);
      persistRef.current = null;
      document.body.style.overflow = "";
    };
  }, [mounted, dismiss]);

  useEffect(() => {
    if (!open || !variant) return;
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open, variant, dismiss]);

  useEffect(() => {
    const onBg = (e: MouseEvent) => {
      const t = e.target as HTMLElement;
      if (t.dataset.briefingDismiss === "backdrop") dismiss();
    };
    if (open) window.addEventListener("click", onBg);
    return () => window.removeEventListener("click", onBg);
  }, [open, dismiss]);

  if (!mounted || !variant || !open) return null;

  const display = firstName.trim() || "there";

  const lines =
    variant === "first"
      ? {
          eyebrow: "Welcome to Helix",
          title: `${display}, you’re signed in.`,
          subtitle:
            "Overnight lanes become a ranked dossier—voices stay interleaved instead of drowned out.",
        }
      : hasRecommendations
        ? {
            eyebrow: "Today’s dossier",
            title:
              recommendationCountToday > 0
                ? `${recommendationCountToday} curated pick${recommendationCountToday === 1 ? "" : "s"} from today’s ingest.`
                : "Deck updated—scroll for the ranked mix.",
            subtitle:
              "Headlines below are scored, summarized, and balanced across the bundles you keep open.",
          }
        : {
            eyebrow: "Pipeline pulse",
            title: `${display}, you’re synced.`,
            subtitle:
              "Tonight’s ingest is still staging your surface. Tomorrow’s automation will refill this grid as soon as the curator locks scores.",
          };

  const brandLine =
    variant === "first"
      ? "First launch · synthesized calm"
      : "Daily welcome · synthesized feed";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="briefing-reveal-heading"
      aria-describedby="briefing-reveal-desc"
      className={cn(
        "fixed inset-0 z-[210] isolation-auto select-none briefing-reveal-viewport-bg",
        "transition-[opacity,backdrop-filter] duration-[880ms]",
        entered ? "opacity-100 backdrop-blur-2xl" : "opacity-0 backdrop-blur-md",
      )}
    >
      {/* Back dismiss layer */}
      <button
        type="button"
        data-briefing-dismiss="backdrop"
        className="absolute inset-0 cursor-default outline-none briefing-reveal-vignette"
        aria-label="Dismiss welcome animation"
      />

      <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
        {/* Drifting Gemini-style blobs */}
        <span className="briefing-reveal-blob briefing-reveal-blob-a" />
        <span className="briefing-reveal-blob briefing-reveal-blob-b" />
        <span className="briefing-reveal-blob briefing-reveal-blob-c" />
        <span className="briefing-reveal-blob briefing-reveal-blob-gold" />

        {/* Fine scan + grid shimmer */}
        <div className="absolute inset-0 helix-grid opacity-[0.16] briefing-reveal-grid-sheen" />
        <div className="absolute inset-0 briefing-reveal-ray" />
      </div>

      <div
        className={cn(
          "relative z-10 mx-auto flex min-h-dvh w-full max-w-[min(32rem,calc(100vw-2rem))] flex-col items-center justify-center px-7 py-14 text-center",
          "transition-[opacity,filter,transform] duration-[760ms]",
          entered
            ? "translate-y-0 scale-100 blur-0 opacity-100 delay-[80ms]"
            : "translate-y-5 scale-[0.96] blur-md opacity-[0] delay-0",
        )}
      >
        <div className="relative mb-14 flex justify-center pointer-events-none" aria-hidden>
          <span className="briefing-reveal-spin-halo briefing-spin-slow" />
          <div className="relative flex h-36 w-36 items-center justify-center rounded-full border border-line-strong bg-surface-deep/70 shadow-[0_0_72px_-8px_rgb(129_140_248/0.35)] backdrop-blur-md briefing-reveal-glass-pulse">
            <Sparkles
              className="h-[2.2rem] w-[2.2rem] text-accent drop-shadow-[0_0_20px_rgb(212_175_55/0.5)] briefing-reveal-icon-pop"
              strokeWidth={1.65}
              aria-hidden
            />
          </div>
        </div>

        <p className="text-[11px] font-bold uppercase tracking-[0.42em] text-ink-muted/92 mb-4 briefing-reveal-rise briefing-rise-d140">
          {brandLine}
        </p>
        <p className="text-[12px] font-semibold uppercase tracking-[0.32em] text-accent/94 mb-3 briefing-reveal-rise briefing-rise-d220">
          {lines.eyebrow}
        </p>
        <h2
          id="briefing-reveal-heading"
          className="font-display text-[clamp(1.45rem,4.25vw,2.06rem)] leading-[1.12] tracking-[-0.03em] text-ink mb-5 briefing-reveal-rise briefing-rise-d300 px-2"
        >
          {lines.title}
        </h2>
        <p
          id="briefing-reveal-desc"
          className="text-[0.95rem] leading-relaxed text-ink-muted/95 mb-14 max-w-lg briefing-reveal-rise briefing-rise-d420 px-3"
        >
          {lines.subtitle}
        </p>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            dismiss();
          }}
          className="pointer-events-auto min-h-[2.875rem] rounded-full bg-linear-to-r from-brand/90 via-accent to-brand-deep/90 px-9 text-[13px] font-semibold uppercase tracking-[0.18em] text-surface-deep shadow-[0_18px_50px_-32px_rgb(79_70_229/1)] transition-[scale,brightness,box-shadow] duration-200 hover:brightness-[1.08] hover:shadow-[0_22px_64px_-38px_rgb(212_175_55/0.35)] active:scale-[0.98] briefing-reveal-rise briefing-rise-d540 mb-12"
        >
          Enter briefing
        </button>

        <span className="text-[11px] text-ink-faint/95 tracking-[0.12em] font-medium briefing-reveal-rise briefing-rise-d640 uppercase">
          Press Escape or backdrop to skip · once per calendar day afterwards
        </span>
      </div>
    </div>
  );
}
