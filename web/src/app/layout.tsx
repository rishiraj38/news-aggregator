import type { Metadata } from "next";
import { IBM_Plex_Sans, Newsreader } from "next/font/google";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { Analytics } from "@vercel/analytics/react";

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  display: "swap",
});

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ibm-plex",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase:
    typeof process.env.NEXT_PUBLIC_APP_URL === "string" && process.env.NEXT_PUBLIC_APP_URL
      ? new URL(process.env.NEXT_PUBLIC_APP_URL)
      : undefined,
  title: {
    default: "Helix — Curated technical intelligence",
    template: "%s · Helix",
  },
  description:
    "A morning dossier for builders: transcripts, feeds, and repos distilled into ranked briefings tailored to how you ship.",
  keywords: [
    "technical digest",
    "developer news",
    "RSS summaries",
    "AI curation",
    "engineering briefing",
  ],
  openGraph: {
    title: "Helix — Curated technical intelligence",
    description:
      "Personalized technical digests: what moved overnight, why it matters to your stack, links when you’re ready to go deep.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Helix — Curated technical intelligence",
    description:
      "Signal-over-noise digest for people who ship software. Ranked, summarized, shipped daily.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark">
        <body
          className={`${newsreader.variable} ${ibmPlexSans.variable} antialiased min-h-dvh`}
        >
          {children}
          <Analytics />
        </body>
      </html>
    </ClerkProvider>
  );
}
