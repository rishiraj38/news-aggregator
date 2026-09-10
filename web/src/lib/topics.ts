/**
 * Canonical topic ids for personalization / ingest bundles.
 * Must stay aligned with Python `app/topic_packs/registry.py`.
 */
export const ALLOWED_TOPIC_IDS = [
  "technology",
  "startups",
  "politics",
  "sports",
  "cricket",
] as const;

export type TopicId = (typeof ALLOWED_TOPIC_IDS)[number];

/** Order: world/sports-first; add Technology when you want AI lab + transcript lanes. */
export const HELIX_TOPIC_PACKS: {
  id: TopicId;
  label: string;
  hint: string;
}[] = [
  {
    id: "politics",
    label: "Politics & world news",
    hint: "BBC top + World + Politics, Reuters wires, Guardian world — geopolitics and major headlines.",
  },
  {
    id: "sports",
    label: "Sports",
    hint: "BBC Sport desk — football, rugby, athletics, motorsport mix.",
  },
  {
    id: "cricket",
    label: "Cricket",
    hint: "BBC Sport cricket feed — Tests, ODIs, T20 arcs.",
  },
  {
    id: "technology",
    label: "Technology & AI",
    hint: "Labs, transcripts, OpenAI · Anthropic · TechCrunch · The Verge · Ars · Wired, plus curator YouTube scans.",
  },
  {
    id: "startups",
    label: "Startups & Y Combinator",
    hint: "YC blog, Hacker News front page and high-score stories — launches, funding and builder discussion.",
  },
];

/**
 * Free-text keyword lanes. Each keyword becomes its own ingest source
 * (Google News search + Hacker News) and matching stories are routed only to
 * the subscribers tracking that term.
 *
 * Normalization MUST mirror `normalize_keyword` in
 * `app/topic_packs/keywords.py` — the Python side derives the ingest source key
 * from this exact canonical form, so any drift silently orphans the lane.
 */
export const MAX_KEYWORDS_PER_USER = 10;
export const MIN_KEYWORD_CHARS = 2;
export const MAX_KEYWORD_CHARS = 60;

export function normalizeKeyword(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const cleaned = raw.trim().toLowerCase().replace(/\s+/g, " ");
  if (cleaned.length < MIN_KEYWORD_CHARS || cleaned.length > MAX_KEYWORD_CHARS) {
    return null;
  }
  if (!/[a-z0-9]/.test(cleaned)) return null;
  return cleaned;
}

/** Clean, de-duplicate and cap a keyword list. Invalid entries are dropped. */
export function canonicalKeywordSelection(raw: unknown): string[] {
  const input = typeof raw === "string" ? [raw] : raw;
  if (!Array.isArray(input)) return [];
  const out: string[] = [];
  for (const item of input) {
    const kw = normalizeKeyword(item);
    if (kw && !out.includes(kw)) out.push(kw);
    if (out.length >= MAX_KEYWORDS_PER_USER) break;
  }
  return out;
}

/** Empty / invalid selections → subscribe to every bundle (balanced nightly mix). */
export function canonicalTopicSelection(raw: unknown): TopicId[] {
  if (!Array.isArray(raw)) {
    return [...ALLOWED_TOPIC_IDS];
  }
  const allowedSet = new Set<string>(ALLOWED_TOPIC_IDS);
  const dedup = new Set<string>();
  for (const t of raw) {
    if (typeof t !== "string" || !allowedSet.has(t)) continue;
    if (!dedup.has(t)) dedup.add(t);
  }
  if (dedup.size === 0) {
    return [...ALLOWED_TOPIC_IDS];
  }
  return ALLOWED_TOPIC_IDS.filter((id) => dedup.has(id));
}
