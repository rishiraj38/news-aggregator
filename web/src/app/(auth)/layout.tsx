import type { Metadata } from "next";

// Sign-in and sign-up are thin Clerk screens with nothing worth ranking. Keep
// them out of search results but let crawlers follow links out of them.
// robots.txt deliberately doesn't Disallow these routes: a blocked page's
// noindex tag is never seen, so Google could still list the bare URL.
export const metadata: Metadata = {
  robots: { index: false, follow: true },
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
