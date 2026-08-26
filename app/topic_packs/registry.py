"""Topic bundles ↔ ingest sources. v1 packs use curated public RSS endpoints."""

from __future__ import annotations

from typing import Any, FrozenSet, List, Mapping, MutableMapping, Sequence, Set

# Digest `article_type` values that belong to the default tech pipeline
TECH_ARTICLE_SOURCES: FrozenSet[str] = frozenset(
    {"youtube", "openai", "anthropic", "techcrunch", "theverge"}
)

ALLOWED_TOPIC_IDS: tuple[str, ...] = ("technology", "politics", "sports", "cricket")

TOPIC_LABELS: dict[str, str] = {
    "technology": "Technology & AI",
    "politics": "Politics & world affairs",
    "sports": "Sports",
    "cricket": "Cricket",
}

# Registry entries drive extra RSS ingestion (stored in general_rss_articles.source → digest.article_type)
RSS_TOPIC_FEED_SCRAPERS: List[dict[str, Any]] = [
    {
        "registry_name": "topic_pol_bbcpolitics",
        "source_key": "topic_pol_bbcpolitics",
        "topic_id": "politics",
        "rss_urls": [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://feeds.bbci.co.uk/news/politics/rss.xml",
            "https://www.theguardian.com/world/rss",
        ],
    },
    {
        "registry_name": "topic_sport_bbcsport",
        "source_key": "topic_sport_bbcsport",
        "topic_id": "sports",
        "rss_urls": ["https://feeds.bbci.co.uk/sport/rss.xml"],
    },
    {
        "registry_name": "topic_cricket_bbccricket",
        "source_key": "topic_cricket_bbccricket",
        "topic_id": "cricket",
        "rss_urls": ["https://feeds.bbci.co.uk/sport/cricket/rss.xml"],
    },
]

_SOURCE_TOPIC: dict[str, str] = {row["source_key"]: row["topic_id"] for row in RSS_TOPIC_FEED_SCRAPERS}


def _topic_from_article_type(article_type: str) -> str | None:
    if article_type in TECH_ARTICLE_SOURCES:
        return "technology"
    if article_type in _SOURCE_TOPIC:
        return _SOURCE_TOPIC[article_type]
    return None


def digest_matches_topics(article_type: str, user_topics: Set[str]) -> bool:
    """
    Gate digests during personalization. Known sources must map to one of the subscriber's bundles.
    Unknown sources stay eligible so older rows or migrations never empty the funnel silently.
    """
    topic = _topic_from_article_type(article_type)
    if topic is None:
        return True
    return topic in user_topics


def normalize_user_topics(prefs: Mapping[str, Any]) -> List[str]:
    """
    Canonical topic ids saved under preferences['topics']. Falls back sensibly when missing.
    """
    raw = prefs.get("topics")
    out: List[str] = []

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        for t in raw:
            if isinstance(t, str) and t.strip() and t in ALLOWED_TOPIC_IDS:
                if t not in out:
                    out.append(t)

    if out:
        return out

    # Legacy: derive from keywords / interests strings
    bag: List[str] = []
    for key in ("interests", "keywords"):
        val = prefs.get(key)
        if isinstance(val, list):
            bag.extend(str(x).lower() for x in val)
        elif isinstance(val, str):
            bag.append(val.lower())

    derived: List[str] = []

    def _has(*needles: str) -> bool:
        return any(any(n in h for n in needles) for h in bag)

    if _has("politic", "election", "parliament"):
        derived.append("politics")
    if _has("cricket", "ipl", "ashes"):
        derived.append("cricket")
    elif _has("sport", "football", "soccer", "nba", "tennis"):
        derived.append("sports")

    if _has(
        "llm",
        "machine learning",
        "embedding",
        "transformer",
        "openai",
        "anthropic",
        "ai",
        "tech",
        "software",
        "developer",
        "kubernetes",
        "rust",
        "python",
        "hardware",
        "gpu",
        "chip",
    ):
        derived.append("technology")

    # De-dupe while preserving selection order
    final: List[str] = []
    for t in derived:
        if t in ALLOWED_TOPIC_IDS and t not in final:
            final.append(t)

    # No explicit topics → full mix so digests naturally span lanes (sport, cricket, geopolitics, tech).
    return final if final else list(ALLOWED_TOPIC_IDS)


def format_topic_line_for_prompt(prefs: MutableMapping[str, Any]) -> str:
    topics = normalize_user_topics(prefs)
    labels = ", ".join(TOPIC_LABELS[t] for t in topics if t in TOPIC_LABELS)
    return labels or ", ".join(TOPIC_LABELS[t] for t in ALLOWED_TOPIC_IDS)
