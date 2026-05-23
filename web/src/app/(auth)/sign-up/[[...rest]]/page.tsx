import Link from "next/link";
import { SignUp } from "@clerk/nextjs";

export default function Page() {
  return (
    <div className="relative z-10 min-h-dvh flex flex-col items-center justify-center px-4 py-16 bg-surface-deep text-ink overflow-x-hidden">
      <div className="pointer-events-none absolute inset-0 helix-aurora opacity-[0.42]" aria-hidden />
      <div className="pointer-events-none absolute inset-0 helix-grid opacity-[0.28]" aria-hidden />
      <Link
        href="/"
        className="absolute top-[max(1.25rem,env(safe-area-inset-top))] left-4 sm:left-8 text-sm font-medium text-ink-muted hover:text-accent transition-colors hover-shine z-20"
      >
        ← Helix home
      </Link>
      <div className="w-full max-w-md mb-10 text-center relative z-10">
        <p className="font-display text-2xl tracking-tight mb-2">Create your account</p>
        <p className="text-sm text-ink-muted leading-relaxed">
          We sync your profile to the digest database on first dashboard visit—then the daily job can target your interests.
        </p>
      </div>
      <div className="w-full flex justify-center relative z-10">
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
    </div>
  );
}
