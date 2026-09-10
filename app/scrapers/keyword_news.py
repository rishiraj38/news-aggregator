"""Fetch news for one subscriber-supplied keyword.

Two complementary sources:

* **Google News RSS search** — arbitrary query support against the whole news
  index, which is what makes free-text keywords possible at all.
* **Hacker News (Algolia)** — catches launches, Show HN and discussion that
  mainstream aggregators miss, and is where most YC-adjacent chatter lands.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List
from urllib.parse import quote_plus

import requests

from app.scrapers.base import Article, BaseScraper

_logger = logging.getLogger(__name__)

_HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
_HN_MIN_POINTS = 5
_HN_MAX_HITS = 20

# A broad term like "ai agents" matches ~100 Google News items per day. Without
# a cap one popular keyword would crowd every other source out of the digest
# batch, which is the same failure the source round-robin exists to prevent.
KEYWORD_MAX_ARTICLES = max(1, int(os.getenv("KEYWORD_MAX_ARTICLES", "15") or 15))


def google_news_rss_url(keyword: str) -> str:
    """Google News search feed. Quoted so multi-word terms match as a phrase."""
    query = quote_plus(f'"{keyword}"' if " " in keyword.strip() else keyword)
    return (
        f"https://news.google.com/rss/search?q={query}"
        "&hl=en-US&gl=US&ceid=US:en"
    )


class KeywordNewsScraper(BaseScraper):
    """One instance per tracked keyword; results are stored under its source key."""

    def __init__(self, keyword: str):
        self.keyword = keyword

    @property
    def rss_urls(self) -> List[str]:
        return [google_news_rss_url(self.keyword)]

    def get_articles(self, hours: int = 24) -> List[Article]:
        articles = super().get_articles(hours)
        seen = {a.guid for a in articles}

        for hit in self._hacker_news_hits(hours):
            if hit.guid not in seen:
                seen.add(hit.guid)
                articles.append(hit)

        articles.sort(key=lambda a: a.published_at, reverse=True)
        capped = articles[:KEYWORD_MAX_ARTICLES]

        _logger.info(
            "Keyword '%s' → %d article(s) in the last %dh (keeping %d newest)",
            self.keyword, len(articles), hours, len(capped),
        )
        return capped

    def _hacker_news_hits(self, hours: int) -> List[Article]:
        """Recent HN stories matching the keyword, filtered by score."""
        since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
        params = {
            "query": self.keyword,
            "tags": "story",
            "numericFilters": f"created_at_i>{since},points>{_HN_MIN_POINTS}",
            "hitsPerPage": _HN_MAX_HITS,
        }
        try:
            resp = requests.get(_HN_SEARCH_URL, params=params, timeout=20)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except Exception as exc:  # noqa: BLE001
            _logger.warning("HN search failed for '%s': %s", self.keyword, exc)
            return []

        out: List[Article] = []
        for hit in hits:
            object_id = str(hit.get("objectID") or "").strip()
            title = (hit.get("title") or "").strip()
            if not object_id or not title:
                continue

            discussion = f"https://news.ycombinator.com/item?id={object_id}"
            # Prefer the linked article; Ask/Show HN posts have no external url.
            url = (hit.get("url") or "").strip() or discussion

            created = hit.get("created_at_i")
            try:
                published = datetime.fromtimestamp(int(created), tz=timezone.utc)
            except (TypeError, ValueError):
                continue

            points = hit.get("points") or 0
            comments = hit.get("num_comments") or 0
            body = (hit.get("story_text") or "").strip()
            summary = (
                f"Hacker News discussion ({points} points, {comments} comments): {discussion}"
            )

            out.append(
                Article(
                    title=title,
                    description=f"{body}\n\n{summary}".strip(),
                    url=url,
                    guid=f"hn:{object_id}",
                    published_at=published,
                    category="hackernews",
                )
            )
        return out


def fetch_keyword_articles(keyword: str, hours: int = 24) -> List[Article]:
    return KeywordNewsScraper(keyword).get_articles(hours=hours)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for a in fetch_keyword_articles("ai agents", hours=48)[:5]:
        print(f"- [{a.category or 'news'}] {a.title[:80]}")
