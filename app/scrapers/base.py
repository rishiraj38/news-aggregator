from datetime import datetime, timedelta, timezone
from typing import List, Optional
from abc import ABC, abstractmethod
import logging
import os
import feedparser
import requests
from pydantic import BaseModel

from app.services.thumbnail_resolve import extract_first_img_from_html

_logger = logging.getLogger(__name__)


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
    """Prefer the largest advertised media:thumbnail when the feed publishes several sizes."""

    def _dim_int(raw) -> int:
        if raw is None:
            return 0
        if isinstance(raw, bool):
            return 0
        if isinstance(raw, int):
            return max(0, raw)
        s = str(raw).strip().split()[0] if str(raw).strip() else ""
        if not s.isdigit():
            return 0
        return max(0, int(s))

    def _dimensions(t) -> tuple[Optional[str], int]:
        u = None
        if isinstance(t, dict):
            u = t.get("url") or t.get("href")
            w = _dim_int(t.get("width"))
            h = _dim_int(t.get("height"))
        else:
            u = getattr(t, "url", None) or getattr(t, "href", None)
            w = _dim_int(getattr(t, "width", None))
            h = _dim_int(getattr(t, "height", None))
        if not u:
            return None, 0
        area = max(w * h, w, h, 1)
        return str(u).strip(), int(area)

    raw_thumbs = getattr(entry, "media_thumbnail", None) or getattr(entry, "media_thumbnails", None)
    if raw_thumbs:
        thumbs_list = raw_thumbs if isinstance(raw_thumbs, (list, tuple)) else [raw_thumbs]
        ranked: list[tuple[str, int]] = []
        for t in thumbs_list:
            u, score = _dimensions(t)
            if u:
                ranked.append((u, score))
        if ranked:
            ranked.sort(key=lambda item: item[1], reverse=True)
            return ranked[0][0]

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
            try:
                if proxy_handler:
                    response = requests.get(rss_url, timeout=30)
                    response.raise_for_status()
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
            except Exception as exc:
                _logger.warning("Skipping RSS endpoint %s: %s", rss_url, exc)
                continue

        return articles
