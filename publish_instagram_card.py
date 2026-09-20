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
  META_ACCESS_TOKEN               Access token (scopes depend on META_GRAPH_MEDIA_BASE host)
  INSTAGRAM_BUSINESS_ID           Numeric IG Business/Creator ID
  META_GRAPH_MEDIA_BASE           Default facebook Graph; instagram login → https://graph.instagram.com/v21.0

  META_PUBLIC_IMAGE_UPLOAD        auto (Cloudinary prepended if CLOUDINARY_* set; else catbox→0x0→file.io→transfer.sh) + Imgur if set
  META_PUBLIC_IMAGE_UPLOAD_ORDER  Comma-separated override (omit Cloudinary prepend when this is set)
  META_SKIP_FACEBOOK_PAGE_STAGING  true skips unpublished Page-photo step on facebook.com Graph only

  META_FACEBOOK_PAGE_ID           Optional FB Page for Page-photo staging (needs facebook-capable token)
  IMGUR_CLIENT_ID                 Optional last-resort Imgur uploads

  INSTAGRAM_SOURCE_IMAGE_URL       Your CDN / bucket HTTPS JPEG (bypass anon hosts entirely)

  NEWS_GRAPHIC_TICKER             Red bar ticker (default: BREAKING NEWS)
  HELIX_LOGO_PATH                 Optional PNG corner logo
  CLOUDINARY_CLOUD_NAME           Unsigned upload preset (recommended for CI; see `.env.example`)
  CLOUDINARY_UPLOAD_PRESET        Dashboard → Upload → Unsigned uploading

Usage
-----
  uv sync
  uv run python publish_instagram_card.py --dry-run
  uv run python publish_instagram_card.py --test-upload [--imgur-file /path/card.jpg]
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
# Mirrors web/src/lib/site.ts. Set HELIX_WEBSITE_URL / HELIX_INSTAGRAM_HANDLE to override;
# keep these in step if the site moves to a custom domain.
DEFAULT_SITE_URL = "https://helix-seven-eta.vercel.app"
DEFAULT_IG_HANDLE = "@formula1_boys_69"
GRAPH_ME = "https://graph.facebook.com/v21.0/me"
GRAPH_ACCOUNTS = "https://graph.facebook.com/v21.0/me/accounts"


def sanitize_meta_access_token(raw: str) -> str:
    """
    Normalize common META_ACCESS_TOKEN copy-paste mistakes (quotes, Bearer, BOM, stray newlines/spaces).

    Never logs token contents.
    """
    if not raw:
        return ""

    raw_s = raw.strip()
    t = "".join(raw_s.splitlines())
    if "\n" in raw_s or "\r" in raw_s:
        logger.warning("META_ACCESS_TOKEN: flattened newlines from paste.")

    for prefix in ("Bearer ", "bearer ", "BEARER "):
        if t.startswith(prefix):
            t = t[len(prefix) :].strip()
            logger.warning("META_ACCESS_TOKEN: stripped Bearer prefix.")

    if len(t) >= 2 and (
        (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'"))
    ):
        t = t[1:-1].strip()
        logger.warning("META_ACCESS_TOKEN: removed wrapping quotes.")

    stealth_bytes = ("\ufeff", "\u200b", "\u200c", "\u200d", "\xa0")
    stripped = "".join(ch for ch in t if ch not in stealth_bytes).strip()
    if stripped != t:
        logger.warning("META_ACCESS_TOKEN: removed BOM / invisible spacing.")
        t = stripped

    if " " in t:
        condensed = "".join(t.split())
        if condensed != t:
            logger.warning("META_ACCESS_TOKEN: collapsed whitespace (broken paste).")
        t = condensed

    return t


def test_public_image_upload(jpeg_override: str) -> int:
    """Smoke-test anonymous public JPEG URLs (same chain as `--publish`; Imgur optional)."""
    from app.services.instagram_publish import upload_local_jpeg_to_public_https

    path: Path
    if jpeg_override.strip():
        path = Path(jpeg_override).expanduser().resolve()
        if not path.is_file():
            logger.error("Not a file: %s", path)
            return 1
    else:
        try:
            from PIL import Image
        except ImportError as exc:
            logger.error("Need Pillow for synthetic JPEG: %s", exc)
            return 1

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / ".public_upload_smoke.jpg"
        Image.new("RGB", (96, 96), color=(20, 90, 120)).save(path, format="JPEG", quality=92)
        logger.info("Wrote synthetic JPEG %s", path)

    cid = os.getenv("IMGUR_CLIENT_ID", "").strip() or None
    try:
        url = upload_local_jpeg_to_public_https(path, imgur_client_id=cid)
        print(f"\nPublic upload OK — URL:\n{url}\n")
        logger.info("Public image host probe succeeded.")
        return 0
    except Exception as exc:
        logger.error("%s", exc)
        print(
            """

Public-upload troubleshooting
-----------------------------
META_PUBLIC_IMAGE_UPLOAD=auto uses Cloudinary first when CLOUDINARY_CLOUD_NAME + CLOUDINARY_UPLOAD_PRESET are set;
otherwise anon mirrors (Catbox → 0x0.st → file.io → transfer.sh).

• GitHub Actions: add Cloudinary secrets (unsigned preset — no upload API secret).
• All mirrors blocked: set INSTAGRAM_SOURCE_IMAGE_URL to a direct HTTPS .jpg URL.
• Re-order: META_PUBLIC_IMAGE_UPLOAD_ORDER=cloudinary,catbox,file_io,transfer_sh,zero_x_zero
• Pin Cloudinary only: META_PUBLIC_IMAGE_UPLOAD=cloudinary
• Imgur last: META_PUBLIC_IMAGE_UPLOAD=auto + IMGUR_CLIENT_ID (after other backends).
"""
.strip()
        )
        return 1


def instagram_diagnose() -> int:
    """
    Sanity-check META_ACCESS_TOKEN + INSTAGRAM_BUSINESS_ID against Graph API.
    Does not touch the DB or publish posts.
    """
    import requests

    token = sanitize_meta_access_token(os.getenv("META_ACCESS_TOKEN", ""))
    ig_expect = os.getenv("INSTAGRAM_BUSINESS_ID", "").strip()
    fb_page_override = os.getenv("META_FACEBOOK_PAGE_ID", "").strip()

    print(
        """
Instagram / Meta diagnostics
----------------------------
Something only YOU can do in Meta (no code can bypass it):

  1) Developers dashboard → Products → Instagram → API setup
  2) Next to formula1_boys_69 click "Generate token"
  3) Copy the long string Meta shows ONCE → put into app/.env:

     META_ACCESS_TOKEN=paste_here_no_quotes

  If lost, regenerate. Meta does not show old tokens again.
""".strip()
    )
    print()

    if not ig_expect:
        logger.error("INSTAGRAM_BUSINESS_ID missing in app/.env (numeric id under IG username).")
        return 1
    logger.info("INSTAGRAM_BUSINESS_ID present: %s", ig_expect)

    if not token:
        logger.error("META_ACCESS_TOKEN empty → generate in Meta Developer Console, paste into app/.env")
        return 1
    logger.info("META_ACCESS_TOKEN looks present (~%s chars)", len(token))

    if fb_page_override:
        logger.info("META_FACEBOOK_PAGE_ID override: %s", fb_page_override)

    try:
        r = requests.get(GRAPH_ME, params={"fields": "id,name", "access_token": token}, timeout=60)
        me = r.json()
    except requests.RequestException as e:
        logger.error("Could not reach Graph /me: %s", e)
        return 1

    if "error" in me:
        logger.info("/me on graph.facebook.com failed (often normal): %s", me["error"])

        ig_r = requests.get(
            "https://graph.instagram.com/v21.0/me",
            params={
                "fields": "id,username,user_id",
                "access_token": token,
            },
            timeout=60,
        )
        ig_me = ig_r.json()
        if ig_r.ok and "error" not in ig_me:
            logger.info(
                "Token validates for Instagram-login on graph.instagram.com (user=%s).",
                ig_me.get("username") or ig_me.get("id"),
            )

            ib = os.getenv("META_GRAPH_MEDIA_BASE", "").strip().lower()
            if "instagram.com" in ib:
                bypass_src = os.getenv("INSTAGRAM_SOURCE_IMAGE_URL", "").strip()
                logger.info(
                    "Instagram-login flow: META_GRAPH_MEDIA_BASE instagram.com ✓ "
                    "(facebook.com `/me` fails are normal)."
                )
                if bypass_src:
                    logger.info("INSTAGRAM_SOURCE_IMAGE_URL overrides anonymous upload hosts.")
                else:
                    logger.info(
                        "Anonymous hosts (META_PUBLIC_IMAGE_UPLOAD=auto) will stage JPEG unless you set INSTAGRAM_SOURCE_IMAGE_URL."
                    )

                logger.info(
                    "Probe upload chain: uv run python publish_instagram_card.py --test-upload"
                )
                print(
                    "\nInstagram-login diagnostics OK: media publishes via graph.instagram.com; "
                    "public JPEG staging uses META_PUBLIC_IMAGE_UPLOAD (no Imgur required).\n"
                )
                return 0

            logger.warning(
                "Token works as Instagram-login but META_GRAPH_MEDIA_BASE is not instagram.com "
                '(add `META_GRAPH_MEDIA_BASE=https://graph.instagram.com/v21.0` to app/.env) '
                "or switch to a Facebook Graph User/Page token.",
            )

        print(
            '\nIf this is not Instagram-login (no graph.instagram.com user): regenerate token '
            '(no quotes, one line META_ACCESS_TOKEN=...).'
            "\nOtherwise set META_GRAPH_MEDIA_BASE for Instagram-publish host per app/.env comments."
        )
        print(
            "Also ensure App Roles → testers include this account while App Mode is Development."
        )
        return 1
    print(f'Graph /me id={me.get("id")} name={me.get("name")!r}')
    print()

    r2 = requests.get(
        GRAPH_ACCOUNTS,
        params={
            "fields": "id,name,instagram_business_account",
            "access_token": token,
            "limit": "100",
        },
        timeout=60,
    )
    acct_payload = r2.json()
    if r2.status_code >= 400 or "error" in acct_payload:
        logger.warning(
            "/me/accounts not available (%s)",
            acct_payload.get("error", acct_payload),
        )
        print(
            "If publish asks for META_FACEBOOK_PAGE_ID: use Graph Explorer GET /me/accounts, "
            "or open your linked Facebook Page About → Page ID.\n"
        )
    else:
        rows = acct_payload.get("data") or []
        print("Facebook Pages for this token (match your INSTAGRAM_BUSINESS_ID):")
        for row in rows:
            ig_b = row.get("instagram_business_account") or {}
            ig_nid = ig_b.get("id")
            mark = ""
            if ig_nid is not None and str(ig_nid) == str(ig_expect):
                mark = "  <-- matches INSTAGRAM_BUSINESS_ID"
            pid = row.get("id")
            pname = row.get("name")
            print(f"  Page id={pid} name={pname!r} instagram_business_account={ig_nid}{mark}")

        from app.services.instagram_publish import discover_facebook_page_for_instagram

        resolved = discover_facebook_page_for_instagram(token, ig_expect)
        if resolved:
            print(f"\nPut this in app/.env (or confirm it matches):\nMETA_FACEBOOK_PAGE_ID={resolved}\n")
        elif not fb_page_override:
            print(
                "\nNo Page auto-matched. You can rely on META_PUBLIC_IMAGE_UPLOAD anon hosts,\n"
                "set META_FACEBOOK_PAGE_ID manually, or add INSTAGRAM_SOURCE_IMAGE_URL.\n"
            )

    print(
        "App Mode: Development only works for invited Testers on that app; switch Live + App Review for others.\n"
        "Next: uv run python publish_instagram_card.py --dry-run\n"
        "Then: uv run python publish_instagram_card.py --publish\n"
    )
    return 0


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


def _normalize_curator_digest_id(raw: object) -> str:
    """Strip common LLM noise (quotes/spaces) from digest ids for lookup."""
    s = "" if raw is None else str(raw).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'”“":
        s = s[1:-1].strip()
    return s


def _digests_from_curator_picks(digests: list[dict], ranked_articles: list, limit: int) -> list[dict]:
    """
    Top `limit` distinct digests in curator rank order.

    Curator ids arrive with stray quotes and whitespace, so ids are matched exactly
    first and then with whitespace collapsed. Tops up with the newest unposted
    digests when the curator returns fewer usable ids than we need.
    """
    by_exact = {str(d["id"]).strip(): d for d in digests}
    collapsed = {"".join(str(d["id"]).split()): d for d in digests}

    def sort_key(art: object):
        try:
            r_val = int(getattr(art, "rank", 999))
        except (TypeError, ValueError):
            r_val = 999
        try:
            sc = float(getattr(art, "relevance_score", 0.0))
        except (TypeError, ValueError):
            sc = 0.0
        return (r_val, -sc)

    picked: list[dict] = []
    seen: set[str] = set()
    for art in sorted(ranked_articles, key=sort_key):
        if len(picked) >= limit:
            break
        nid = _normalize_curator_digest_id(getattr(art, "digest_id", None))
        if not nid:
            continue
        row = by_exact.get(nid) or collapsed.get("".join(nid.split()))
        if row is None or str(row["id"]) in seen:
            continue
        seen.add(str(row["id"]))
        picked.append(row)

    for row in digests:  # newest-first top-up
        if len(picked) >= limit:
            break
        if str(row["id"]) not in seen:
            seen.add(str(row["id"]))
            picked.append(row)

    if not picked:
        logger.warning("Curator returned no usable digest ids; falling back to newest digests")
        picked = digests[:limit]
    return picked[:limit]


def _story_topic_label(article_type: str) -> str:
    """Chip text for a slide, e.g. `topic_startup_ychn` → `Startups`."""
    from app.topic_packs.registry import TOPIC_LABELS, _topic_from_article_type

    topic = _topic_from_article_type(article_type or "")
    if not topic:
        return "Briefing"
    label = TOPIC_LABELS.get(topic, topic)
    return label.split("&")[0].strip().split(",")[0].strip()


def _story_topic_id(article_type: str) -> str:
    from app.topic_packs.registry import _topic_from_article_type

    return _topic_from_article_type(article_type or "") or ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Breaking-news style Instagram card + optional publish")
    ap.add_argument("--email", default=DEFAULT_USER, help="User for curator profile (must exist in DB)")
    ap.add_argument(
        "--hours",
        type=int,
        default=72,
        help="Digest lookback window (keep modest — Groq curator pays per-token on the stacked prompt)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Only write JPEGs; skip Meta/third-party uploads")
    ap.add_argument(
        "--reel",
        action="store_true",
        help="Build and publish a 9:16 Reel video instead of the carousel (needs ffmpeg)",
    )
    ap.add_argument(
        "--single",
        action="store_true",
        help="Post one breaking-news card instead of the multi-story carousel",
    )
    ap.add_argument(
        "--slides",
        type=int,
        default=int(os.getenv("INSTAGRAM_CAROUSEL_STORIES", "5")),
        help="Story slides in the carousel (cover + stories + CTA must stay ≤10)",
    )
    ap.add_argument("--publish", action="store_true", help="Publish via Instagram Graph (needs env tokens)")
    ap.add_argument("--main", type=str, default="", help="Override red headline")
    ap.add_argument("--detail", type=str, default="", help="Override white detail block")
    ap.add_argument("--bg-url", type=str, default="", help="Override background image URL")
    ap.add_argument("--instagram-diagnose", action="store_true", help="Check Meta token + resolve Page id (no DB)")
    ap.add_argument(
        "--test-upload",
        action="store_true",
        help="Upload a synthetic JPEG via public hosts (META_PUBLIC_IMAGE_UPLOAD)",
    )
    ap.add_argument(
        "--test-imgur",
        action="store_true",
        help="Alias for --test-upload (hosts are not Imgur-only)",
    )
    ap.add_argument(
        "--imgur-file",
        type=str,
        default="",
        help="JPEG path for --test-upload (omit for synthetic Pillow image)",
    )
    args = ap.parse_args()

    if args.test_upload or args.test_imgur:
        return test_public_image_upload(args.imgur_file)

    if args.instagram_diagnose:
        return instagram_diagnose()

    from app.database.connection import engine
    from app.database.models import Base
    from app.database.schema_migrations import ensure_image_url_columns, ensure_instagram_posted_column, ensure_plan_column, ensure_pro_request_column
    from app.database.repository import Repository
    from app.services.user_service import UserService
    from app.agent.curator_agent import CuratorAgent
    from app.services.process_email import _resolve_thumbnail_for_digest
    from app.services.news_graphic import BreakingGraphicSpec, render_breaking_news_card, save_card
    from app.services.carousel_graphic import CarouselSpec, Story, render_carousel, save_slides
    from app.services.social_copy import CaptionStory, build_carousel_caption, build_single_caption
    from app.services.mail_links import instagram_handle_for_display, website_url
    from app.services.reel_video import ReelSpec, build_reel, total_seconds
    from app.services.instagram_publish import (
        publish_jpeg_carousel_post,
        publish_jpeg_feed_post,
        publish_video_reel,
    )

    Base.metadata.create_all(engine)
    ensure_image_url_columns()
    ensure_instagram_posted_column()
    ensure_plan_column()
    ensure_pro_request_column()

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

    # Skip stories already posted to Instagram (for 2-posts-per-day dedup)
    before = len(digests)
    digests = [d for d in digests if str(d.get("posted_to_instagram", "")).lower() != "true"]
    if before != len(digests):
        logger.info("Filtered %d already-posted digests → %d remaining", before - len(digests), len(digests))
    if not digests:
        logger.error("All recent digests already posted to Instagram.")
        return 1

    cap = max(12, min(240, int(os.getenv("INSTAGRAM_CURATOR_DIGEST_CAP", "40"))))
    if len(digests) > cap:
        logger.info(
            "Instagram curator: trimming %s digests → newest %s (env INSTAGRAM_CURATOR_DIGEST_CAP)",
            len(digests),
            cap,
        )
        digests = digests[:cap]

    profile = user_svc.get_user_profile(user)
    ranked = CuratorAgent(profile).rank_digests(digests)
    if not ranked:
        logger.error("Curator returned empty.")
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    og_cache: dict = {}
    site = website_url() or DEFAULT_SITE_URL
    handle = instagram_handle_for_display() or DEFAULT_IG_HANDLE

    # A carousel is cover + N stories + CTA, and Instagram allows at most 10 images.
    story_budget = max(1, min(8, args.slides))
    fmt = (os.getenv("INSTAGRAM_POST_FORMAT", "carousel") or "carousel").strip().lower()
    if args.reel:
        fmt = "reel"
    elif args.single:
        fmt = "single"
    if fmt not in ("carousel", "reel", "single"):
        logger.warning("Unknown INSTAGRAM_POST_FORMAT=%r — falling back to carousel", fmt)
        fmt = "carousel"

    want = 1 if fmt == "single" else story_budget
    picks = _digests_from_curator_picks(digests, ranked, want)
    # A one-slide carousel is rejected by the API; fall back to the single card.
    if fmt == "carousel" and len(picks) < 2:
        logger.info("Only %d unposted story available — posting a single card instead", len(picks))
        fmt = "single"

    def _stories() -> list:
        return [
            Story(
                title=row["title"],
                summary=row.get("summary", "") or "",
                url=row.get("url", "") or "",
                image_url=_resolve_thumbnail_for_digest(row, og_cache),
                topic_label=_story_topic_label(row.get("article_type", "")),
            )
            for row in picks
        ]

    def _caption() -> str:
        return build_carousel_caption(
            [
                CaptionStory(
                    title=row["title"],
                    summary=row.get("summary", "") or "",
                    url=row.get("url", "") or "",
                    topic=_story_topic_id(row.get("article_type", "")),
                )
                for row in picks
            ],
            site_url=site,
            handle=handle,
        )

    jpeg_paths: list[Path] = []
    reel_path: Path | None = None

    if fmt == "reel":
        stories = _stories()
        reel_spec = ReelSpec(
            stories=stories, site_url=site, handle=handle, max_stories=story_budget
        )
        reel_path = build_reel(reel_spec, OUT_DIR / f"{ts}-reel.mp4")
        caption = _caption()
        logger.info(
            "Wrote reel: %s (%.1fs, %d stories)",
            reel_path.resolve(),
            total_seconds(reel_spec, len(stories)),
            len(stories),
        )
    elif fmt == "carousel":
        stories = _stories()
        slides = render_carousel(
            CarouselSpec(
                stories=stories,
                site_url=site,
                handle=handle,
                max_story_slides=story_budget,
            )
        )
        jpeg_paths = save_slides(slides, OUT_DIR, f"{ts}-carousel")
        caption = _caption()
        logger.info(
            "Wrote %d carousel slides (%d stories) → %s",
            len(jpeg_paths),
            len(stories),
            OUT_DIR.resolve(),
        )
    else:
        d = picks[0]
        thumb_url = _resolve_thumbnail_for_digest(d, og_cache)
        spec = BreakingGraphicSpec(
            main_headline=args.main.strip() or _main_headline_from_title(d["title"]),
            detail_text=args.detail.strip() or _detail_from_summary(d["summary"], d["title"]),
            background_image_url=args.bg_url.strip() or thumb_url,
            ticker_text=os.getenv("NEWS_GRAPHIC_TICKER", "BREAKING NEWS"),
            logo_path=logo_png,
        )
        outfile = OUT_DIR / f"{ts}-{_slug(d['title'])}.jpg"
        save_card(render_breaking_news_card(spec), outfile)
        jpeg_paths = [outfile]
        caption = build_single_caption(
            CaptionStory(
                title=d["title"],
                summary=d.get("summary", "") or "",
                url=d.get("url", "") or "",
                topic=_story_topic_id(d.get("article_type", "")),
            ),
            site_url=site,
            handle=handle,
        )
        logger.info("Wrote card: %s", outfile.resolve())

    if not args.publish:
        if args.dry_run:
            logger.info("Dry-run: no Meta calls.")
        else:
            logger.info("Saved locally. Pass --publish to post (needs tokens).")
        print("\n----- caption -----\n" + caption + "\n-------------------\n")
        return 0

    token = sanitize_meta_access_token(os.getenv("META_ACCESS_TOKEN", ""))
    ig_id = os.getenv("INSTAGRAM_BUSINESS_ID", "").strip()
    imgur_id = os.getenv("IMGUR_CLIENT_ID", "").strip()
    bypass_url = os.getenv("INSTAGRAM_SOURCE_IMAGE_URL", "").strip()
    fb_page = os.getenv("META_FACEBOOK_PAGE_ID", "").strip()

    if not token or not ig_id:
        logger.error("META_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ID are required for --publish.")
        return 1

    # Image staging: unpublished FB Page upload (facebook Graph) then public uploads unless bypass URL set.
    if fmt != "reel" and not bypass_url and not fb_page:
        mode = (os.getenv("META_PUBLIC_IMAGE_UPLOAD", "auto") or "auto").strip()
        logger.info(
            "No INSTAGRAM_SOURCE_IMAGE_URL — will derive public JPEG URL "
            "(META_PUBLIC_IMAGE_UPLOAD=%s; facebook Graph may use Page-photo staging instead).",
            mode,
        )

    try:
        if fmt == "reel":
            assert reel_path is not None
            result = publish_video_reel(
                video_path=reel_path,
                video_url=os.getenv("INSTAGRAM_SOURCE_VIDEO_URL", "").strip() or None,
                caption=caption,
                access_token=token,
                instagram_business_id=ig_id,
            )
        elif fmt == "carousel":
            if bypass_url:
                # One fixed URL cannot represent several different slides.
                logger.warning("INSTAGRAM_SOURCE_IMAGE_URL is ignored for carousels; staging each slide.")
            result = publish_jpeg_carousel_post(
                jpeg_paths=jpeg_paths,
                caption=caption,
                access_token=token,
                instagram_business_id=ig_id,
                imgur_client_id=imgur_id or None,
                facebook_page_id=fb_page or None,
            )
        else:
            result = publish_jpeg_feed_post(
                jpeg_path=jpeg_paths[0] if not bypass_url else None,
                caption=caption,
                access_token=token,
                instagram_business_id=ig_id,
                imgur_client_id=imgur_id or None,
                image_url=bypass_url or None,
                facebook_page_id=fb_page or None,
            )
        logger.info("Published Instagram media id: %s", result.get("instagram_media_id"))
        # Mark every story used so the next run picks different ones
        for row in picks:
            repo.mark_digest_posted_instagram(row["id"])
        logger.info("Marked %d digest(s) as posted to Instagram", len(picks))
        return 0
    except Exception as e:
        logger.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
