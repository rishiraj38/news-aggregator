import { db } from "./db";

export interface DigestArticle {
  id: string;
  title: string;
  summary: string;
  url: string;
  source: string;
  created_at: Date;
}

/**
 * Fetches recent digests from the database for welcome email
 * Returns top 10 most recent articles
 */
export async function getRecentDigests(): Promise<DigestArticle[]> {
  const digests = await db.digest.findMany({
    where: {
      summary: {
        not: null,
      },
    },
    orderBy: {
      created_at: "desc",
    },
    take: 15, // Get more than needed in case some are invalid
    select: {
      id: true,
      title: true,
      summary: true,
      url: true,
      source: true,
      created_at: true,
    },
  });

  // Filter out any articles with empty summaries
  const validDigests = digests
    .filter((d: any) => d.summary && d.summary.length > 0)
    .slice(0, 10);

  return validDigests.map((d: any) => ({
    id: d.id,
    title: d.title,
    summary: d.summary || "",
    url: d.url,
    source: d.source,
    created_at: d.created_at,
  }));
}
