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
  topic_startup_ychn: "startups",
  topic_tech_general: "technology",
  topic_tech_research: "technology",
} as const;

/** Per-subscriber keyword lanes are stored as `kw_<slug>_<hash>` article types. */
const KEYWORD_PREFIX = "kw_";

export type DigestLane =
  | "technology"
  | "startups"
  | "politics"
  | "sports"
  | "cricket"
  | "keyword"
  | "other";

export function digestLaneFromArticleType(articleType: string): DigestLane {
  const at = articleType.trim();
  if (at.startsWith(KEYWORD_PREFIX)) return "keyword";
  if (TECH_SOURCES.has(at)) return "technology";
  if (at in PACK_TO_LANE) {
    return PACK_TO_LANE[at as keyof typeof PACK_TO_LANE] as Exclude<
      DigestLane,
      "keyword" | "other"
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
    case "startups":
      return {
        lane,
        pill:
          "rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-orange-500/[0.1] border border-orange-400/35 text-orange-300",
        cardRail: "border-l-[4px] border-l-orange-400/95",
        borderAccent: "border-l-[4px] border-l-orange-400/95",
      };
    case "keyword":
      return {
        lane,
        pill:
          "rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-violet-500/[0.12] border border-violet-400/35 text-violet-300",
        cardRail: "border-l-[4px] border-l-violet-400/95",
        borderAccent: "border-l-[4px] border-l-violet-400/95",
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
    case "startups":
      return "Startups";
    case "keyword":
      return "Your keyword";
    default:
      return "Feed";
  }
}
