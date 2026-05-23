import Link from "next/link";
import { Instagram } from "lucide-react";
import { SITE_INSTAGRAM_HREF } from "@/lib/site";

export default function SiteFooter() {
  return (
    <footer className="relative z-10 border-t border-line mt-24 overflow-hidden">
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[min(50%,340px)] helix-aurora opacity-[0.35]"
        aria-hidden
      />
      <div className="pointer-events-none absolute inset-0 helix-grid opacity-[0.25]" aria-hidden />
      <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14 flex flex-col sm:flex-row gap-10 sm:items-start sm:justify-between">
        <div>
          <p className="font-display text-lg text-ink tracking-tight">Helix</p>
          <p className="text-sm text-ink-muted mt-2 max-w-sm leading-relaxed">
            Automated curation—not a substitute for reading primary sources. Built for builders who want signal without the scroll.
          </p>
        </div>
        <div className="flex flex-wrap gap-x-10 gap-y-4 text-sm text-ink-muted">
          <Link
            href="/sign-in"
            className="hover-shine hover:text-accent transition-colors"
          >
            Sign in
          </Link>
          <Link
            href="/dashboard"
            className="hover-shine hover:text-accent transition-colors"
          >
            Feed
          </Link>
          <a href="#pricing" className="hover-shine hover:text-accent transition-colors">
            Pricing
          </a>
          <a
            href={SITE_INSTAGRAM_HREF}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 hover-shine hover:text-accent transition-colors"
          >
            <Instagram className="w-4 h-4 opacity-70" strokeWidth={1.85} aria-hidden />
            Updates
          </a>
        </div>
      </div>
      <div className="relative border-t border-line py-6 text-center text-xs text-ink-faint px-4">
        © {new Date().getFullYear()} Helix. Built for learners who value signal over noise.
      </div>
    </footer>
  );
}
