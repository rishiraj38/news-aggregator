import { auth } from "@clerk/nextjs/server";
import { db } from "@/lib/db";
import {
  canonicalKeywordSelection,
  canonicalTopicSelection,
  MAX_KEYWORDS_PER_USER,
} from "@/lib/topics";

/**
 * Update the caller's personalization preferences.
 *
 * Accepts `topics`, `keywords`, or both — each is applied only when present, so
 * the keyword editor and the bundle picker can save independently without
 * clobbering each other.
 */
export async function PATCH(req: Request) {
  const { userId } = await auth();
  if (!userId) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: Record<string, unknown>;
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!body || typeof body !== "object") {
    return Response.json({ error: "Invalid body" }, { status: 400 });
  }

  const hasTopics = Object.prototype.hasOwnProperty.call(body, "topics");
  const hasKeywords = Object.prototype.hasOwnProperty.call(body, "keywords");

  if (!hasTopics && !hasKeywords) {
    return Response.json(
      { error: "Provide a topics and/or keywords payload" },
      { status: 400 },
    );
  }

  if (hasKeywords && body.keywords !== null && !Array.isArray(body.keywords)) {
    return Response.json(
      { error: "keywords must be an array of strings" },
      { status: 400 },
    );
  }

  const user = await db.user.findUnique({ where: { id: userId } });
  if (!user) {
    return Response.json({ error: "User not synced yet — open dashboard once" }, { status: 404 });
  }

  let prefs: Record<string, unknown> = {};
  try {
    prefs = JSON.parse(user.preferences || "{}") as Record<string, unknown>;
  } catch {
    prefs = {};
  }

  const result: { ok: true; topics?: string[]; keywords?: string[]; dropped?: number } = {
    ok: true,
  };

  if (hasTopics) {
    const topics = canonicalTopicSelection(body.topics);
    prefs.topics = topics;
    result.topics = topics;
  }

  if (hasKeywords) {
    const submitted = Array.isArray(body.keywords) ? body.keywords : [];
    const keywords = canonicalKeywordSelection(submitted);
    // Report anything normalization discarded (blank, too short/long, duplicate,
    // or past the cap) so the UI can tell the user rather than silently losing it.
    const dropped = Math.max(0, submitted.length - keywords.length);
    prefs.keywords = keywords;
    result.keywords = keywords;
    if (dropped > 0) result.dropped = dropped;
  }

  await db.user.update({
    where: { id: userId },
    data: { preferences: JSON.stringify(prefs) },
  });

  return Response.json(result);
}

export async function GET() {
  const { userId } = await auth();
  if (!userId) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const user = await db.user.findUnique({ where: { id: userId } });
  if (!user) {
    return Response.json({ error: "User not synced yet" }, { status: 404 });
  }

  let prefs: Record<string, unknown> = {};
  try {
    prefs = JSON.parse(user.preferences || "{}") as Record<string, unknown>;
  } catch {
    prefs = {};
  }

  return Response.json({
    topics: canonicalTopicSelection(prefs.topics ?? null),
    keywords: canonicalKeywordSelection(prefs.keywords ?? []),
    maxKeywords: MAX_KEYWORDS_PER_USER,
  });
}
