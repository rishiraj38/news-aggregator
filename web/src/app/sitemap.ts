import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

/**
 * Only the public marketing page belongs here. Sign-in and sign-up are thin
 * Clerk screens that canonicalize to "/", so listing them sent Google
 * conflicting signals; every other route requires an account.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: SITE_URL,
      lastModified: new Date(),
      changeFrequency: "weekly",
      priority: 1,
    },
  ];
}
