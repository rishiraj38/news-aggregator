/** Public-facing links shared across marketing + footer */
export const SITE_INSTAGRAM_HREF = "https://www.instagram.com/formula1_boys_69/";
export const SITE_GITHUB_HREF = "https://github.com/rishiraj38/news-aggregator";

/**
 * Canonical origin, used for metadataBase, canonical URLs, the sitemap, robots,
 * and structured data. When moving to a custom domain, set NEXT_PUBLIC_APP_URL
 * and every one of those signals follows.
 */
export const SITE_URL = (process.env.NEXT_PUBLIC_APP_URL || "https://helix-seven-eta.vercel.app").replace(
  /\/+$/,
  "",
);

/**
 * The brand name Google should show for the site. Keep the title, og:site_name,
 * and the WebSite structured data all agreeing on this — Google chooses a site
 * name from those signals together, and mixed names ("Helix" vs "Helix News
 * Curator") make it less likely to pick the one you want.
 */
export const SITE_NAME = "Helix";

export const SITE_TITLE = "Helix — Personalized Daily News Briefings";

export const SITE_DESCRIPTION =
  "Helix is a personalized daily news briefing: AI, tech, startups, politics, sports and cricket, summarized and ranked to your interests and sent to your inbox.";
