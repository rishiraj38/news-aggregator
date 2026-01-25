from typing import List, Callable, Any
from .scrapers.youtube import YouTubeScraper, ChannelVideo
from .scrapers.openai import OpenAIScraper
from .scrapers.anthropic import AnthropicScraper
from .database.repository import Repository


def _save_youtube_videos(
    scraper: YouTubeScraper, repo: Repository, hours: int
) -> List[ChannelVideo]:
    from .config import SEARCH_QUERIES
    from app.services.search_agent import SearchAgent
    from datetime import datetime

    agent = SearchAgent(top_n=5)
    videos = []
    video_dicts = []
    seen_ids = set()

    for query in SEARCH_QUERIES:
        candidates = agent.search_videos(query)
        for cand in candidates:
            vid_id = cand["video_id"]
            if vid_id in seen_ids:
                continue
            seen_ids.add(vid_id)
            
            # Get Transcript
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
                }
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
            }
            for a in articles
        ]
        save_func(article_dicts)
    return articles


SCRAPER_REGISTRY = [
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
]


def run_scrapers(hours: int = 24) -> dict:
    repo = Repository()
    results = {}

    for name, scraper, save_func in SCRAPER_REGISTRY:
        try:
            items = save_func(scraper, repo, hours)
            results[name] = items
        except Exception:
            results[name] = []

    return results


if __name__ == "__main__":
    results = run_scrapers(hours=24)
    print(f"YouTube videos: {len(results['youtube'])}")
    print(f"OpenAI articles: {len(results['openai'])}")
    print(f"Anthropic articles: {len(results['anthropic'])}")
