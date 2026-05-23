/** Map ingest `digest.article_type` to UX lane labels + accents (digest cards, stats). */

const TECH_SOURCES = new Set([
  "youtube",
  "openai",
  "anthropic",
  "techcrunch",
  "theverge",
]);

const PACK_TO_LANE = {
  topic_pol_bbcpolitics: "politics",
  topic_sport_bbcsport: "sports",
  topic_cricket_bbccricket: "cricket",
} as const;

export type DigestLane =
  | "technology"
  | "politics"
  | "sports"
  | "cricket"
  | "other";

export function digestLaneFromArticleType(articleType: string): DigestLane {
  const at = articleType.trim();
  if (TECH_SOURCES.has(at)) return "technology";
  if (at in PACK_TO_LANE) {
    return PACK_TO_LANE[at as keyof typeof PACK_TO_LANE] as Exclude<
      DigestLane,
      "technology" | "other"
    >;
  }
  return "other";
}

export function digestLaneStyles(articleType: string): {
  lane: DigestLane;
  pill: string;
  /** Thick left accent for cards (historical alias). Prefer `cardRail`. */
  borderAccent: string;
  cardRail: string;
} {
  const lane = digestLaneFromArticleType(articleType);

  switch (lane) {
    case "technology":
      return {
        lane,
        pill:
          "rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-brand-subtle border border-brand/40 text-brand",
        cardRail: "border-l-[4px] border-l-brand",
        borderAccent: "border-l-[4px] border-l-brand",
      };
    case "politics":
      return {
        lane,
        pill:
          "rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-rose-500/[0.1] border border-rose-400/25 text-rose-200",
        cardRail: "border-l-[4px] border-l-rose-400/95",
        borderAccent: "border-l-[4px] border-l-rose-400/95",
      };
    case "sports":
      return {
        lane,
        pill:
          "rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-emerald-500/[0.1] border border-emerald-400/35 text-emerald-300",
        cardRail: "border-l-[4px] border-l-emerald-400/95",
        borderAccent: "border-l-[4px] border-l-emerald-400/95",
      };
    case "cricket":
      return {
        lane,
        pill:
          "rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-sky-500/[0.1] border border-sky-400/35 text-sky-300",
        cardRail: "border-l-[4px] border-l-sky-400/95",
        borderAccent: "border-l-[4px] border-l-sky-400/95",
      };
    default:
      return {
        lane,
        pill:
          "rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-surface-deep border border-line-strong text-ink-faint uppercase",
        cardRail: "border-l-[4px] border-l-accent/70",
        borderAccent: "border-l-[4px] border-l-accent/70",
      };
  }
}

export function digestLaneHumanLabel(lane: DigestLane): string {
  switch (lane) {
    case "technology":
      return "Tech & AI";
    case "politics":
      return "World";
    case "sports":
      return "Sports";
    case "cricket":
      return "Cricket";
    default:
      return "Feed";
  }
}
