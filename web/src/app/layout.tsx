import type { Metadata } from "next";
import { IBM_Plex_Sans, Newsreader } from "next/font/google";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { Analytics } from "@vercel/analytics/react";
import {
  SITE_DESCRIPTION,
  SITE_GITHUB_HREF,
  SITE_INSTAGRAM_HREF,
  SITE_NAME,
  SITE_TITLE,
  SITE_URL,
} from "@/lib/site";

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

// Ownership is verified in Search Console with the HTML file in public/
// (google12e56e6fa520b24a.html). The meta-tag method uses a *different* token,
// shown under "HTML tag" in Search Console — the file name is not that token,
// and emitting it produced an invalid tag. Only emit one when it's configured.
const googleSiteVerification = process.env.GOOGLE_SITE_VERIFICATION?.trim();

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_TITLE,
    template: `%s · ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  applicationName: SITE_NAME,
  authors: [{ name: "Helix Team" }],
  generator: "Next.js",
  keywords: [
    "helix",
    "helix news",
    "helix ai news",
    "helix daily briefing",
    "personalized news briefing",
    "daily news digest",
    "ai news digest",
    "startup news",
    "cricket news digest",
    "news curator",
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
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    url: SITE_URL,
    siteName: SITE_NAME,
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/logo.png",
        width: 512,
        height: 512,
        alt: "Helix logo",
      },
    ],
  },
  twitter: {
    // The only share image is the square logo, which "summary_large_image" crops.
    card: "summary",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: ["/logo.png"],
  },
  icons: {
    icon: "/favicon.ico",
    apple: "/logo.png",
  },
  ...(googleSiteVerification ? { verification: { google: googleSiteVerification } } : {}),
};

/**
 * Google chooses the name it displays for a site largely from WebSite
 * structured data on the home page, so that node leads, and its name matches the
 * title and og:site_name exactly.
 */
const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      name: SITE_NAME,
      alternateName: ["Helix News", "Helix AI News", "Helix News Curator"],
      url: SITE_URL,
      inLanguage: "en",
      publisher: { "@id": `${SITE_URL}/#organization` },
    },
    {
      "@type": "Organization",
      "@id": `${SITE_URL}/#organization`,
      name: SITE_NAME,
      url: SITE_URL,
      logo: `${SITE_URL}/logo.png`,
      sameAs: [SITE_INSTAGRAM_HREF, SITE_GITHUB_HREF],
    },
    {
      "@type": "WebApplication",
      "@id": `${SITE_URL}/#webapp`,
      name: SITE_NAME,
      url: SITE_URL,
      description:
        "Personalized daily news briefings. Helix pulls stories from AI labs, the tech press, startups, politics, sports and cricket, summarizes each one, ranks them against your interests, and emails you the best of them every day.",
      applicationCategory: "NewsApplication",
      operatingSystem: "Web",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
      },
      publisher: { "@id": `${SITE_URL}/#organization` },
    },
  ],
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
