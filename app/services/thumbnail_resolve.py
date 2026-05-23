"""Resolve article thumbnails when RSS did not expose media:* / enclosures."""

from __future__ import annotations

import html as html_std
import logging
import re
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse, urljoin

import requests

logger = logging.getLogger(__name__)

_YOUTUBE_IMG_RE = re.compile(
    r"https?://i\.ytimg\.com/vi/([^/]+)/(?:default|mqdefault|hqdefault|sddefault|maxresdefault)\.jpg",
    re.I,
)


def best_youtube_still(video_id: str, *, timeout: float = 3.0) -> str:
    """
    Prefer the largest sensible YouTube still. maxres exists for HD uploads; hq/sd fall back cleanly.
    Skips degenerate tiny maxres responses (covers missing poster).
    """
    variants = ("maxresdefault", "sddefault", "hqdefault", "mqdefault", "default")
    base = f"https://i.ytimg.com/vi/{video_id}"
    fallback = f"{base}/hqdefault.jpg"
    for name in variants:
        u = f"{base}/{name}.jpg"
        try:
            r = requests.head(u, timeout=timeout, allow_redirects=True)
            if r.status_code != 200:
                continue
            cl = int(r.headers.get("Content-Length", "0") or "0")
            if name == "maxresdefault" and 0 < cl < 3800:
                continue
            if cl == 0:
                continue
            return u
        except requests.RequestException:
            continue
    return fallback


def sharpen_public_thumbnail_url(url: Optional[str]) -> Optional[str]:
    """Upgrade known CDN thumbnails right before embedding in HTML (no ingest-time cost)."""
    if not url or not isinstance(url, str):
        return url
    m = _YOUTUBE_IMG_RE.search(url.strip())
    if m:
        return best_youtube_still(m.group(1))
    if "ichef.bbci.co.uk" in url and "?" in url:
        return _bbc_ichef_widen(url)
    return url


def _bbc_ichef_widen(url: str) -> str:
    """When BBC ichef URLs carry a pixel width hint, bump it for sharper email previews."""
    try:
        parsed = urlparse(url)
        q = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)]
        changed = False
        out_q: list[tuple[str, str]] = []
        for k, v in q:
            if k.lower() in ("width", "w") and v.isdigit() and int(v) > 0 and int(v) < 976:
                out_q.append((k, "976"))
                changed = True
            else:
                out_q.append((k, v))
        if changed:
            new_query = urlencode(out_q)
            return urlunparse(parsed._replace(query=new_query))
    except Exception:
        pass
    return url



# First <img src="..."> in HTML summaries (common on TechCrunch, Verge, etc.)
_IMG_SRC_RE = re.compile(r"""<img[^>]+src\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)
# OG / Twitter fallback
_META_IMAGE_RES = (
    re.compile(
        r"""<meta[^>]+property\s*=\s*["']og:image["'][^>]+content\s*=\s*["']([^"']+)["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]+content\s*=\s*["']([^"']+)["'][^>]+property\s*=\s*["']og:image["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]+name\s*=\s*["']twitter:image["'][^>]+content\s*=\s*["']([^"']+)["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""<meta[^>]+name\s*=\s*["']twitter:image:src["'][^>]+content\s*=\s*["']([^"']+)["']""",
        re.IGNORECASE,
    ),
)

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def extract_first_img_from_html(
    fragment: Optional[str], page_url: str = ""
) -> Optional[str]:
    if not fragment or not fragment.strip():
        return None
    m = _IMG_SRC_RE.search(fragment)
    if not m:
        return None
    raw = html_std.unescape(m.group(1).strip())
    if not raw:
        return None
    if page_url.startswith("http"):
        return normalize_image_url(page_url, raw)
    if raw.startswith("//"):
        return "https:" + raw
    if raw.startswith("http://"):
        return "https://" + raw[7:]
    return raw if raw.startswith("https://") else None


def normalize_image_url(page_url: str, candidate: str) -> Optional[str]:
    c = html_std.unescape(candidate.strip())
    if not c:
        return None
    if c.startswith("//"):
        c = "https:" + c
    elif c.startswith("/"):
        base = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
        c = urljoin(base, c)
    elif not c.startswith("http"):
        c = urljoin(page_url + "/", c)
    if c.startswith("http://"):
        c = "https://" + c[7:]
    return c if c.startswith("https://") else None


def fetch_og_or_twitter_image(page_url: str, timeout: float = 6.0) -> Optional[str]:
    """
    Light HTML fetch + meta tag scrape. Callers typically cache URL -> result per email send.
    """
    if not page_url or not page_url.startswith(("http://", "https://")):
        return None
    try:
        r = requests.get(
            page_url,
            timeout=timeout,
            headers={
                "User-Agent": _BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        r.raise_for_status()
    except requests.RequestException as e:
        logger.debug("thumbnail og fetch failed for %s: %s", page_url, e)
        return None

    text = r.text[:800_000]
    for rx in _META_IMAGE_RES:
        m = rx.search(text)
        if m:
            url = normalize_image_url(page_url, m.group(1))
            if url:
                return sharpen_public_thumbnail_url(url) or url
    return None
