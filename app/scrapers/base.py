from datetime import datetime, timedelta, timezone
from typing import List, Optional
from abc import ABC, abstractmethod
import os
import feedparser
import requests
from pydantic import BaseModel

from app.services.thumbnail_resolve import extract_first_img_from_html


def collect_entry_html_fragments(entry) -> List[str]:
    """RSS fields that may contain inline <img>."""
    snippets: List[str] = []
    for key in ("summary", "description"):
        val = entry.get(key)
        if isinstance(val, str) and val.strip():
            snippets.append(val)
    for block in getattr(entry, "content", None) or []:
        if isinstance(block, dict) and block.get("value"):
            snippets.append(block["value"])
    return snippets


def rss_entry_thumbnail_url(entry, link: str) -> Optional[str]:
    wired = extract_feed_entry_image_url(entry)
    if wired:
        return wired
    if link.startswith("http"):
        for html_snip in collect_entry_html_fragments(entry):
            found = extract_first_img_from_html(html_snip, link)
            if found:
                return found
    return None


def get_proxy_handler():
    """Create a URL opener with proxy support for feedparser."""
    proxy_username = os.getenv("WEBSHARE_USERNAME")
    proxy_password = os.getenv("WEBSHARE_PASSWORD")

    if not proxy_username or not proxy_password:
        return None

    from urllib.request import ProxyHandler, build_opener

    proxy_url = f"http://{proxy_username}:{proxy_password}@proxy.webshare.io:8080"
    proxy_support = ProxyHandler({"http": proxy_url, "https": proxy_url})
    opener = build_opener(proxy_support)
    return opener


def extract_feed_entry_image_url(entry) -> Optional[str]:
    """Best-effort thumbnail from RSS/Atom (media_thumbnail, media_content, enclosures, image)."""
    thumbs = getattr(entry, "media_thumbnail", None) or getattr(entry, "media_thumbnails", None)
    if thumbs:
        t0 = thumbs[0]
        u = None
        if isinstance(t0, dict):
            u = t0.get("url")
        if not u:
            u = getattr(t0, "url", None) or getattr(t0, "href", None)
        if u:
            return u

    for attr in ("media_content",):
        contents = getattr(entry, attr, None)
        if contents:
            for mc in contents:
                if not isinstance(mc, dict):
                    continue
                ctype = mc.get("type") or ""
                if ctype.startswith("image/") or mc.get("medium") == "image":
                    u = mc.get("url")
                    if u:
                        return u

    enclosures = getattr(entry, "enclosures", None)
    if enclosures:
        for enc in enclosures:
            if not isinstance(enc, dict):
                continue
            href = enc.get("href")
            ctype = enc.get("type") or ""
            if href and (ctype.startswith("image/") or not ctype):
                return href

    image = getattr(entry, "image", None)
    if isinstance(image, dict) and image.get("href"):
        return image["href"]

    return None


class Article(BaseModel):
    title: str
    description: str
    url: str
    guid: str
    published_at: datetime
    category: Optional[str] = None
    image_url: Optional[str] = None


class BaseScraper(ABC):
    @property
    @abstractmethod
    def rss_urls(self) -> List[str]:
        pass

    def get_articles(self, hours: int = 24) -> List[Article]:
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours)
        articles = []
        seen_guids = set()

        proxy_handler = get_proxy_handler()

        for rss_url in self.rss_urls:
            if proxy_handler:
                response = requests.get(rss_url, timeout=30)
                feed = feedparser.parse(response.content)
            else:
                feed = feedparser.parse(rss_url)

            if not feed.entries:
                continue

            for entry in feed.entries:
                published_parsed = getattr(entry, "published_parsed", None)
                if not published_parsed:
                    continue

                published_time = datetime(*published_parsed[:6], tzinfo=timezone.utc)
                if published_time >= cutoff_time:
                    guid = entry.get("id", entry.get("link", ""))
                    if guid not in seen_guids:
                        seen_guids.add(guid)
                        link = entry.get("link", "")
                        articles.append(
                            Article(
                                title=entry.get("title", ""),
                                description=entry.get("description", ""),
                                url=link,
                                guid=guid,
                                published_at=published_time,
                                category=entry.get("tags", [{}])[0].get("term")
                                if entry.get("tags")
                                else None,
                                image_url=rss_entry_thumbnail_url(entry, link),
                            )
                        )

        return articles
