"""YouTube video discovery via Data API v3 (primary) or channel RSS (fallback).

yt-dlp gets blocked by YouTube's bot detection on datacenter IPs (GitHub Actions).
The Data API is free (10,000 units/day; each search costs 100 units) and reliable.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import feedparser
import requests

logger = logging.getLogger(__name__)

_YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class SearchAgent:
    def __init__(self, top_n: int = 5):
        self.top_n = top_n
        self.api_key: Optional[str] = os.getenv("YOUTUBE_API_KEY")

    # ------------------------------------------------------------------
    # Primary: YouTube Data API v3
    # ------------------------------------------------------------------
    def _search_via_api(self, query: str) -> List[Dict[str, Any]]:
        """Search YouTube using the official Data API v3."""
        if not self.api_key:
            return []

        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "date",
            "maxResults": min(self.top_n + 5, 25),
            "publishedAfter": (
                datetime.now(timezone.utc) - timedelta(days=7)
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "videoDuration": "medium",  # 4–20 min
            "key": self.api_key,
        }

        try:
            resp = requests.get(_YT_SEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(f"YouTube API search failed: {exc}")
            return []

        video_ids = [
            item["id"]["videoId"]
            for item in data.get("items", [])
            if item.get("id", {}).get("videoId")
        ]

        if not video_ids:
            return []

        # Fetch duration + stats in one batch call (costs 1 unit per video)
        details = self._fetch_video_details(video_ids)

        candidates: List[Dict[str, Any]] = []
        for item in data.get("items", []):
            vid = item["id"].get("videoId")
            if not vid:
                continue

            snippet = item.get("snippet", {})
            detail = details.get(vid, {})
            duration_sec = detail.get("duration", 0)

            # Skip shorts (< 3 min)
            if duration_sec < 180:
                continue

            published_raw = snippet.get("publishedAt", "")
            try:
                pub_date = datetime.strptime(
                    published_raw[:10], "%Y-%m-%d"
                ).strftime("%Y%m%d")
            except (ValueError, TypeError):
                pub_date = datetime.now().strftime("%Y%m%d")

            candidates.append({
                "video_id": vid,
                "title": snippet.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "channel": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "published_at": pub_date,
                "views": detail.get("views", 0),
                "description": snippet.get("description", ""),
            })

        return candidates[: self.top_n]

    def _fetch_video_details(
        self, video_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Batch-fetch duration and view count for a list of video IDs."""
        if not self.api_key or not video_ids:
            return {}

        params = {
            "part": "contentDetails,statistics",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }

        try:
            resp = requests.get(_YT_VIDEOS_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning(f"YouTube video details fetch failed: {exc}")
            return {}

        result: Dict[str, Dict[str, Any]] = {}
        for item in data.get("items", []):
            vid = item["id"]
            duration_iso = (
                item.get("contentDetails", {}).get("duration", "PT0S")
            )
            result[vid] = {
                "duration": _parse_iso_duration(duration_iso),
                "views": int(
                    item.get("statistics", {}).get("viewCount", 0)
                ),
            }
        return result

    # ------------------------------------------------------------------
    # Fallback: Channel RSS feeds (no API key needed)
    # ------------------------------------------------------------------
    def _search_via_rss(self, _query: str) -> List[Dict[str, Any]]:
        """Fall back to scraping featured channel RSS feeds."""
        from app.config import FEATURED_CHANNELS

        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        candidates: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for channel_id in FEATURED_CHANNELS:
            rss_url = (
                f"https://www.youtube.com/feeds/videos.xml"
                f"?channel_id={channel_id}"
            )
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries:
                    vid = entry.get("yt_videoid", "")
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)

                    pub_parsed = getattr(entry, "published_parsed", None)
                    if not pub_parsed:
                        continue
                    pub_time = datetime(
                        *pub_parsed[:6], tzinfo=timezone.utc
                    )
                    if pub_time < cutoff:
                        continue

                    # Skip Shorts by title heuristic
                    title = entry.get("title", "")
                    if title.startswith("#") or len(title) < 15:
                        continue

                    candidates.append({
                        "video_id": vid,
                        "title": title,
                        "url": entry.get("link", f"https://www.youtube.com/watch?v={vid}"),
                        "channel": entry.get("author", ""),
                        "channel_id": channel_id,
                        "published_at": pub_time.strftime("%Y%m%d"),
                        "views": 0,
                        "description": entry.get("summary", ""),
                    })
            except Exception as exc:
                logger.warning(f"RSS fallback failed for channel {channel_id}: {exc}")

        return candidates[: self.top_n]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def search_videos(self, query: str) -> List[Dict[str, Any]]:
        """
        Search YouTube for videos. Uses Data API v3 if YOUTUBE_API_KEY
        is set, otherwise falls back to featured channel RSS feeds.
        """
        logger.info(f"🔍 Searching YouTube for: '{query}'")

        if self.api_key:
            results = self._search_via_api(query)
            if results:
                logger.info(f"   Found {len(results)} candidates via API for '{query}'")
                return results
            logger.warning("API search returned 0 results, trying RSS fallback...")

        results = self._search_via_rss(query)
        logger.info(
            f"   Found {len(results)} candidates via RSS fallback for '{query}'"
        )
        return results


def _parse_iso_duration(iso: str) -> int:
    """Convert ISO 8601 duration (PT1H2M30S) to seconds."""
    import re

    match = re.match(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "PT0S"
    )
    if not match:
        return 0
    h, m, s = (int(g) if g else 0 for g in match.groups())
    return h * 3600 + m * 60 + s


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = SearchAgent()
    results = agent.search_videos("AI News today")
    import json
    print(json.dumps(results, indent=2))
