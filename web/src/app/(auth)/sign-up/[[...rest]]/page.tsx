import Link from "next/link";
import { SignUp } from "@clerk/nextjs";

export default function Page() {
  return (
    <div className="relative z-10 min-h-dvh flex flex-col justify-between px-4 py-6 sm:py-8 bg-surface-deep text-ink overflow-x-hidden">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <span className="briefing-auth-orb briefing-auth-a" aria-hidden />
        <span className="briefing-auth-orb briefing-auth-b" aria-hidden />
      </div>
      <div className="pointer-events-none absolute inset-0 helix-aurora opacity-[0.42]" aria-hidden />
      <div className="pointer-events-none absolute inset-0 helix-grid opacity-[0.28]" aria-hidden />

      {/* Top navigation header */}
      <header className="w-full max-w-lg mx-auto flex items-center justify-between relative z-20 pt-2 pb-4">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm font-medium text-ink-muted hover:text-accent transition-colors hover-shine"
        >
          <span aria-hidden>←</span>
          <span>Helix home</span>
        </Link>
        <Link href="/" className="flex items-center gap-2 opacity-85 hover:opacity-100 transition-opacity">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="Helix" width={22} height={22} className="object-contain" />
          <span className="font-display text-sm tracking-tight text-ink">Helix</span>
        </Link>
      </header>

      {/* Centered Auth Card */}
      <main className="w-full max-w-md mx-auto my-auto flex flex-col items-center justify-center relative z-10 py-4">
        <div className="w-full text-center mb-7">
          <p className="font-display text-2xl sm:text-3xl tracking-tight mb-2 text-ink">Create your account</p>
          <p className="text-sm text-ink-muted leading-relaxed max-w-sm mx-auto">
            We sync your profile to the digest database on first dashboard visit - then the daily job can target your interests.
          </p>
        </div>
        <div className="w-full flex justify-center">
          <SignUp
            routing="path"
            path="/sign-up"
            appearance={{
              variables: {
                colorPrimary: "#d4af37",
                colorBackground: "#11100e",
                colorInputBackground: "#1a1816",
                colorText: "#f0ebe3",
                colorTextSecondary: "#a39e94",
                colorNeutral: "#6f6a61",
                borderRadius: "0.75rem",
              },
              elements: {
                card: "rounded-2xl shadow-[0_24px_64px_-32px_rgba(0,0,0,0.85)] border border-line-strong bg-surface",
                headerTitle: "font-display text-xl",
                socialButtonsBlockButton: "border-line-strong hover:border-accent/30",
                formButtonPrimary: "shadow-none font-semibold bg-accent hover:brightness-110 transition-[filter]",
              },
            }}
          />
        </div>
      </main>

      {/* Subtle footer */}
      <footer className="w-full max-w-lg mx-auto py-3 text-center text-xs text-ink-faint relative z-10">
        © {new Date().getFullYear()} Helix · AI News Aggregator
      </footer>
    </div>
  );
}
