import { Lock, Sparkles } from "lucide-react";

type Props = {
  locked: boolean;
  /** Overlay headline, e.g. "Keyword tracking is a Pro feature". */
  title: string;
  /** What upgrading unlocks. */
  pitch: string;
  /** Optional reassurance about what the Free plan already includes. */
  note?: string;
  children: React.ReactNode;
};

/**
 * Shows a Pro-only section to Free subscribers as a locked preview rather than
 * hiding it, so they can see what upgrading unlocks.
 *
 * The preview is `inert` and `aria-hidden`: it can't be focused, clicked, or
 * read out, so assistive tech gets the overlay text instead. This is purely
 * presentation — the preferences API rejects the write for Free accounts anyway.
 */
export default function ProLock({ locked, title, pitch, note, children }: Props) {
  if (!locked) return <>{children}</>;

  return (
    <div className="relative min-h-[17rem]">
      <div inert aria-hidden className="pointer-events-none select-none opacity-30 blur-[1.5px] saturate-50">
        {children}
      </div>

      <div className="absolute inset-0 flex items-center justify-center p-2 sm:p-4">
        <div className="w-full max-w-sm rounded-2xl border border-violet-400/35 bg-surface-deep/92 backdrop-blur-md px-6 py-6 text-center shadow-[0_28px_70px_-36px_rgb(0_0_0/0.95)]">
          <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full border border-violet-400/40 bg-violet-500/[0.14]">
            <Lock className="w-5 h-5 text-violet-300" strokeWidth={2} aria-hidden />
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-400/40 bg-violet-500/[0.12] px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-violet-300">
            <Sparkles className="w-3 h-3" strokeWidth={2.25} aria-hidden />
            Pro
          </span>
          <h3 className="mt-3 font-display text-lg tracking-tight text-ink">{title}</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{pitch}</p>
          {note && <p className="mt-3 text-[11px] text-ink-faint">{note}</p>}
        </div>
      </div>
    </div>
  );
}
