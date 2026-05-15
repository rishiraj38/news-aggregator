import Link from "next/link";

export default function SiteFooter() {
  return (
    <footer className="relative z-10 border-t border-line mt-24">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14 flex flex-col sm:flex-row gap-8 sm:items-center sm:justify-between">
        <div>
          <p className="font-display text-lg text-ink tracking-tight">
            Helix
          </p>
          <p className="text-sm text-ink-faint mt-1 max-w-xs">
            Automated curation—not a substitute for reading primary sources.
          </p>
        </div>
        <div className="flex flex-wrap gap-x-8 gap-y-3 text-sm text-ink-muted">
          <Link href="/sign-in" className="hover:text-accent transition-colors">
            Sign in
          </Link>
          <Link href="/dashboard" className="hover:text-accent transition-colors">
            Feed
          </Link>
          <a href="#pricing" className="hover:text-accent transition-colors">
            Pricing
          </a>
        </div>
      </div>
      <div className="border-t border-line py-6 text-center text-xs text-ink-faint">
        © {new Date().getFullYear()} Helix. Built for learners who value signal over noise.
      </div>
    </footer>
  );
}
