#!/usr/bin/env python3
"""
Build a "breaking banner" portrait card from the top-ranked digest story and optionally
publish via Instagram Graph API.

Security
--------
- Rotating leaked passwords is pointless if they were pasted in plaintext; revoke and use tokens.
- Never commit META_ACCESS_TOKEN, IMGUR_CLIENT_ID, etc. Put them only in `.env`.

Instagram automation uses Meta\'s Instagram Graph API (Business/Creator + Facebook Page +
long-lived Page token). Plain username/password browsers automation is brittle and violates ToS.

Env (optional publishing)
-------------------------
  META_ACCESS_TOKEN          Long-lived Page access token with instagram_content_publish
  INSTAGRAM_BUSINESS_ID      Numeric Instagram user ID from Meta tools
  IMGUR_CLIENT_ID            Anonymous Imgur uploads (free tier) so Graph can fetch image_url
  NEWS_GRAPHIC_TICKER        Ticker wording in red bar (default: BREAKING NEWS)
  HELIX_LOGO_PATH            Optional PNG (transparent) for corner logo; else renders Helix pill mark

Or skip Imgur by hosting the JPEG yourself and setting:
  INSTAGRAM_SOURCE_IMAGE_URL  Public HTTPS URL to the same image you generated (advanced)

Usage
-----
  uv sync
  uv run python publish_instagram_card.py --dry-run
  uv run python publish_instagram_card.py --publish
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(_REPO_ROOT / "app" / ".env")
load_dotenv(_REPO_ROOT / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_USER = "rishiraj438gt@gmail.com"
OUT_DIR = Path("outputs") / "instagram"


def _slug(text: str, max_len: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len] or "card").rstrip("-")


def _main_headline_from_title(title: str) -> str:
    """Short red headline: first heavy phrase or first ~3 words."""
    t = title.strip()
    if not t:
        return "BREAKING"
    words = t.split()
    if len(words) <= 3:
        return t.upper()
    return " ".join(words[:3]).upper()


def _detail_from_summary(summary: str, title: str, max_chars: int = 320) -> str:
    s = (summary or "").strip() or title
    s = re.sub(r"\s+", " ", s)
    return s[:max_chars].rstrip() + ("…" if len(s) > max_chars else "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Breaking-news style Instagram card + optional publish")
    ap.add_argument("--email", default=DEFAULT_USER, help="User for curator profile (must exist in DB)")
    ap.add_argument("--hours", type=int, default=168, help="Digest lookback window")
    ap.add_argument("--dry-run", action="store_true", help="Only write JPEG; do not call Meta/Imgur")
    ap.add_argument("--publish", action="store_true", help="Publish via Instagram Graph (needs env tokens)")
    ap.add_argument("--main", type=str, default="", help="Override red headline")
    ap.add_argument("--detail", type=str, default="", help="Override white detail block")
    ap.add_argument("--bg-url", type=str, default="", help="Override background image URL")
    args = ap.parse_args()

    from app.database.connection import engine
    from app.database.models import Base
    from app.database.schema_migrations import ensure_image_url_columns
    from app.database.repository import Repository
    from app.services.user_service import UserService
    from app.agent.curator_agent import CuratorAgent
    from app.services.process_email import _resolve_thumbnail_for_digest
    from app.services.news_graphic import BreakingGraphicSpec, render_breaking_news_card, save_card
    from app.services.instagram_publish import publish_jpeg_feed_post

    Base.metadata.create_all(engine)
    ensure_image_url_columns()

    logo_png = os.getenv("HELIX_LOGO_PATH", "").strip() or None

    repo = Repository()
    user_svc = UserService()
    user = user_svc.get_user_by_email(args.email)
    if not user:
        logger.error("No DB user for %s", args.email)
        return 1

    digests = repo.get_recent_digests(hours=args.hours, exclude_sent=False)
    if not digests:
        logger.error("No digests.")
        return 1

    profile = user_svc.get_user_profile(user)
    ranked = CuratorAgent(profile).rank_digests(digests)
    if not ranked:
        logger.error("Curator returned empty.")
        return 1

    top_digest_id = ranked[0].digest_id
    d = next((x for x in digests if x["id"] == top_digest_id), None)
    if not d:
        logger.error("Digest row missing.")
        return 1

    og_cache: dict = {}
    thumb_url = _resolve_thumbnail_for_digest(d, og_cache)

    main_h = args.main.strip() or _main_headline_from_title(d["title"])
    detail = args.detail.strip() or _detail_from_summary(d["summary"], d["title"])
    bg = args.bg_url.strip() or thumb_url

    spec = BreakingGraphicSpec(
        main_headline=main_h,
        detail_text=detail,
        background_image_url=bg,
        ticker_text=os.getenv("NEWS_GRAPHIC_TICKER", "BREAKING NEWS"),
        logo_path=logo_png,
    )
    rgb = render_breaking_news_card(spec)
    slug = _slug(d["title"])
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    outfile = OUT_DIR / f"{ts}-{slug}.jpg"
    save_card(rgb, outfile)
    logger.info("Wrote card: %s", outfile.resolve())

    if not args.publish:
        if args.dry_run:
            logger.info("Dry-run: no Meta calls.")
        else:
            logger.info("Card saved. Pass --publish to post (needs tokens).")
        return 0

    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    ig_id = os.getenv("INSTAGRAM_BUSINESS_ID", "").strip()
    imgur_id = os.getenv("IMGUR_CLIENT_ID", "").strip()
    bypass_url = os.getenv("INSTAGRAM_SOURCE_IMAGE_URL", "").strip()

    if not token or not ig_id:
        logger.error("META_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ID are required for --publish.")
        return 1

    if not bypass_url and not imgur_id:
        logger.error(
            "Add IMGUR_CLIENT_ID to .env or set INSTAGRAM_SOURCE_IMAGE_URL to a public HTTPS JPEG."
        )
        return 1

    caption_lines = [
        d["title"],
        "",
        d.get("summary", "")[:2100],
        "",
        "Read more: " + d.get("url", ""),
        "",
        "#ainews #tech #newsletter",
    ]
    caption = "\n".join(x for x in caption_lines if x is not None)[:2100]

    try:
        result = publish_jpeg_feed_post(
            jpeg_path=outfile if not bypass_url else None,
            caption=caption,
            access_token=token,
            instagram_business_id=ig_id,
            imgur_client_id=imgur_id or None,
            image_url=bypass_url or None,
        )
        logger.info("Published Instagram media id: %s", result.get("instagram_media_id"))
        return 0
    except Exception as e:
        logger.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
