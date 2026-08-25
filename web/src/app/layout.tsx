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

const baseUrl =
  typeof process.env.NEXT_PUBLIC_APP_URL === "string" && process.env.NEXT_PUBLIC_APP_URL
    ? process.env.NEXT_PUBLIC_APP_URL
    : "https://helix-seven-eta.vercel.app";

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: {
    default: "Helix — AI News Curator & Technical Intelligence Dossier",
    template: "%s · Helix News Curator",
  },
  description:
    "Helix is an autonomous AI news curator and technical intelligence platform. It ingests, digests, ranks, and delivers high-signal news from transcripts, RSS feeds, and repositories tailored to your profile.",
  applicationName: "Helix News Curator",
  authors: [{ name: "Helix Team" }],
  generator: "Next.js",
  keywords: [
    "helix news curator",
    "helix ai news curator",
    "helix news",
    "ai news curator",
    "news curator",
    "technical news aggregator",
    "developer news curator",
    "ai technical digest",
    "daily ai briefing",
    "personalized news curation",
    "engineering newsletter",
    "automated news curator",
    "tech news intelligence",
  ],
  alternates: {
    canonical: "/",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  openGraph: {
    title: "Helix — AI News Curator & Technical Intelligence Dossier",
    description:
      "Autonomous AI news curator: transcripts, feeds, and repos distilled into personalized ranked briefings. Signal you can defend in a meeting.",
    url: baseUrl,
    siteName: "Helix News Curator",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/logo.png",
        width: 512,
        height: 512,
        alt: "Helix News Curator Logo",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Helix — AI News Curator & Technical Intelligence",
    description:
      "Autonomous AI news curator and technical intelligence platform. Ranked morning dossiers tailored to your interests.",
    images: ["/logo.png"],
  },
  icons: {
    icon: "/favicon.ico",
    apple: "/logo.png",
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebApplication",
      "@id": `${baseUrl}/#webapp`,
      "name": "Helix News Curator",
      "alternateName": [
        "Helix",
        "Helix AI News Curator",
        "Helix AI News Aggregator",
        "Helix Technical Intelligence"
      ],
      "url": baseUrl,
      "description":
        "Autonomous AI news curator that ingests technical RSS feeds, YouTube transcripts, and engineering blogs, digests them with LLMs, and delivers personalized ranked dossiers.",
      "applicationCategory": "NewsApplication",
      "operatingSystem": "Web",
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD"
      },
      "screenshot": `${baseUrl}/logo.png`,
      "softwareVersion": "1.0"
    },
    {
      "@type": "Organization",
      "@id": `${baseUrl}/#organization`,
      "name": "Helix",
      "url": baseUrl,
      "logo": `${baseUrl}/logo.png`,
      "sameAs": [
        "https://www.instagram.com/formula1_boys_69/"
      ]
    }
  ]
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark">
        <head>
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
          />
        </head>
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
