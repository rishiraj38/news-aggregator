import logging
from typing import List, Callable, Any

from app.topic_packs.registry import RSS_TOPIC_FEED_SCRAPERS

from .scrapers.youtube import YouTubeScraper, ChannelVideo
from .scrapers.openai import OpenAIScraper
from .scrapers.anthropic import AnthropicScraper
from .scrapers.techcrunch import TechCrunchScraper
from .scrapers.theverge import TheVergeScraper
from .database.repository import Repository

logger = logging.getLogger(__name__)


def _save_youtube_videos(
    scraper: YouTubeScraper, repo: Repository, hours: int
) -> List[ChannelVideo]:
    import os
    import time

    from .config import SEARCH_QUERIES
    from app.services.search_agent import SearchAgent
    from datetime import datetime

    agent = SearchAgent(top_n=5)
    videos = []
    video_dicts = []
    seen_ids = set()

    # Transcripts are fetched inline, one network round trip per video, and
    # YouTube throttles hard from CI. Cap the whole stage so a bad day costs
    # minutes rather than the entire workflow budget; videos past the budget are
    # still stored and simply have no transcript to digest from.
    budget_seconds = float(os.getenv("YT_TRANSCRIPT_BUDGET_SECONDS", "180") or 180)
    started = time.monotonic()
    skipped_for_budget = 0

    for query in SEARCH_QUERIES:
        candidates = agent.search_videos(query)
        for cand in candidates:
            vid_id = cand["video_id"]
            if vid_id in seen_ids:
                continue
            seen_ids.add(vid_id)

            # Get Transcript
            if budget_seconds > 0 and (time.monotonic() - started) > budget_seconds:
                skipped_for_budget += 1
                transcript = None
            else:
                transcript = scraper.get_transcript(vid_id)
            
            # Parse Date
            try:
                pub_date = datetime.strptime(cand["published_at"], "%Y%m%d")
            except (ValueError, TypeError):
                pub_date = datetime.now()

            # Create Object
            v = ChannelVideo(
                title=cand["title"],
                url=cand["url"],
                video_id=vid_id,
                published_at=pub_date,
                description=cand.get("description", ""),
                transcript=transcript.text if transcript else None
            )
            
            videos.append(v)
            video_dicts.append(
                {
                    "video_id": v.video_id,
                    "title": v.title,
                    "url": v.url,
                    "channel_id": cand.get("channel_id", "Unknown"),
                    "published_at": v.published_at,
                    "description": v.description,
                    "transcript": v.transcript,
                    "image_url": f"https://i.ytimg.com/vi/{v.video_id}/hqdefault.jpg",
                }
            )
            
    if skipped_for_budget:
        logger.warning(
            "YouTube transcript budget of %.0fs exhausted — %d video(s) stored without transcripts.",
            budget_seconds, skipped_for_budget,
        )

    if video_dicts:
        repo.bulk_create_youtube_videos(video_dicts)
    return videos


def _save_rss_articles(
    scraper, repo: Repository, hours: int, save_func: Callable
) -> List[Any]:
    articles = scraper.get_articles(hours=hours)
    if articles:
        article_dicts = [
            {
                "guid": a.guid,
                "title": a.title,
                "url": a.url,
                "published_at": a.published_at,
                "description": a.description,
                "category": a.category,
                "image_url": a.image_url,
            }
            for a in articles
        ]
        save_func(article_dicts)
    return articles


def _make_general_rss_save(source_key: str) -> Callable:
    return lambda s, r, h: _save_rss_articles(
        s,
        r,
        h,
        lambda articles, sk=source_key: r.bulk_create_general_rss_articles(articles, sk),
    )


def _topic_pack_scraper_rows() -> List[tuple[str, Any, Callable]]:
    from app.scrapers.configurable_rss import ConfigurableRSSScraper

    rows: List[tuple[str, Any, Callable]] = []
    for pack in RSS_TOPIC_FEED_SCRAPERS:
        scraper = ConfigurableRSSScraper(pack["rss_urls"])
        rows.append((pack["registry_name"], scraper, _make_general_rss_save(pack["source_key"])))
    return rows


_SCRAPER_REGISTRY_CORE: List[tuple[str, Any, Callable]] = [
    ("youtube", YouTubeScraper(), _save_youtube_videos),
    (
        "openai",
        OpenAIScraper(),
        lambda s, r, h: _save_rss_articles(s, r, h, r.bulk_create_openai_articles),
    ),
    (
        "anthropic",
        AnthropicScraper(),
        lambda s, r, h: _save_rss_articles(s, r, h, r.bulk_create_anthropic_articles),
    ),
    (
        "techcrunch",
        TechCrunchScraper(),
        _make_general_rss_save("techcrunch"),
    ),
    (
        "theverge",
        TheVergeScraper(),
        _make_general_rss_save("theverge"),
    ),
]


SCRAPER_REGISTRY = _SCRAPER_REGISTRY_CORE + _topic_pack_scraper_rows()


def _keyword_scraper_rows(repo: Repository) -> List[tuple[str, Any, Callable]]:
    """One ingest lane per keyword any active subscriber is tracking.

    Built at call time rather than import time because the set of keywords
    lives in the database and changes whenever someone edits their preferences.
    """
    import os

    from app.scrapers.keyword_news import KeywordNewsScraper
    from app.topic_packs.keywords import keyword_source_key

    limit = max(0, int(os.getenv("KEYWORD_MAX_TERMS", "25") or 25))
    if limit == 0:
        return []

    try:
        keywords = repo.get_tracked_keywords(limit=limit)
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not load tracked keywords: %s", exc)
        return []

    if not keywords:
        return []

    logger.info("Tracked keywords this run (%d): %s", len(keywords), ", ".join(keywords))
    return [
        (
            keyword_source_key(kw),
            KeywordNewsScraper(kw),
            _make_general_rss_save(keyword_source_key(kw)),
        )
        for kw in keywords
    ]


def run_scrapers(hours: int = 24) -> dict:
    repo = Repository()
    results = {}

    for name, scraper, save_func in SCRAPER_REGISTRY + _keyword_scraper_rows(repo):
        try:
            items = save_func(scraper, repo, hours)
            results[name] = items
            logger.info("Scraper %s → %d item(s)", name, len(items) if items else 0)
        except Exception as exc:
            # Previously swallowed silently, so a broken source looked identical
            # to a quiet one and the run still reported success.
            logger.error("Scraper %s failed: %s", name, exc, exc_info=True)
            results[name] = []

    empty = [n for n, v in results.items() if not v]
    if empty:
        logger.warning("Scrapers returning nothing this run: %s", ", ".join(sorted(empty)))

    return results


if __name__ == "__main__":
    results = run_scrapers(hours=24)
    print(f"YouTube videos: {len(results['youtube'])}")
    print(f"OpenAI articles: {len(results['openai'])}")
    print(f"Anthropic articles: {len(results['anthropic'])}")
