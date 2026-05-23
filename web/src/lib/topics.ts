/**
 * Canonical topic ids for personalization / ingest bundles.
 * Must stay aligned with Python `app/topic_packs/registry.py`.
 */
export const ALLOWED_TOPIC_IDS = [
  "technology",
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
    hint: "Labs, transcripts, OpenAI · Anthropic · TechCrunch · The Verge, plus curator YouTube scans.",
  },
];

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
