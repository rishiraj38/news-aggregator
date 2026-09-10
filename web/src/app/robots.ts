import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Account-only areas. Sign-in/sign-up stay crawlable so Google can read
        // their noindex tag; a Disallow would hide that tag from it.
        disallow: ["/api/", "/dashboard", "/admin", "/upgrade"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
