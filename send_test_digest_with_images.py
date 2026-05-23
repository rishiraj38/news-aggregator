#!/usr/bin/env python3
"""Send a digest preview with thumbnails to one inbox (defaults to owner test address)."""

import argparse
import logging
import sys

from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / "app" / ".env")
load_dotenv(_ROOT / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_EMAIL = "rishiraj438gt@gmail.com"


def main() -> int:
    parser = argparse.ArgumentParser(description="Send digest HTML email with thumbnails (test)")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Recipient (must exist in users table)")
    parser.add_argument("--hours", type=int, default=168, help="Lookback for digests")
    parser.add_argument("--top-n", type=int, default=5, dest="top_n")
    parser.add_argument(
        "--first",
        action="store_true",
        help="Use first-digest subject + hero strip (otherwise regular daily template)",
    )
    args = parser.parse_args()

    from app.database.connection import engine
    from app.database.models import Base
    from app.database.schema_migrations import ensure_image_url_columns

    Base.metadata.create_all(engine)
    ensure_image_url_columns()

    from app.database.repository import Repository
    from app.services.user_service import UserService
    from app.agent.curator_agent import CuratorAgent
    from app.services.process_email import send_personalized_email
    from app.topic_packs.registry import digest_matches_topics
    from app.topic_packs.diversify import diversify_curated_pick

    repo = Repository()
    user_svc = UserService()
    user = user_svc.get_user_by_email(args.email)
    if not user:
        logger.error("No user row for %s — sign up in the app first.", args.email)
        return 1

    digests = repo.get_recent_digests(hours=args.hours, exclude_sent=False)
    if not digests:
        logger.error("No digests in DB. Run scrapers + process_digests first.")
        return 1

    profile = user_svc.get_user_profile(user)
    topic_set = set(profile["topics"])
    before = len(digests)
    digests = [d for d in digests if digest_matches_topics(d["article_type"], topic_set)]
    logger.info(
        "Topic bundles %s → %s / %s digests eligible for routing",
        sorted(topic_set),
        len(digests),
        before,
    )
    if not digests:
        logger.error(
            "Nothing matched your bundles. Widen preferences.topics JSON for this user or ingest more feeds."
        )
        return 1

    ranked = CuratorAgent(profile).rank_digests(digests)
    if not ranked:
        logger.error("Curator returned no ranked articles.")
        return 1

    dm = {d["id"]: d for d in digests}
    picked = diversify_curated_pick(ranked, dm, topic_set, args.top_n)
    top = [a.model_copy(update={"rank": i}) for i, a in enumerate(picked, start=1)]
    result = send_personalized_email(
        user,
        profile,
        top,
        is_first_delivery=bool(args.first),
    )
    if result.get("success"):
        logger.info("Sent digest with %s stories to %s", result.get("articles_count"), args.email)
        return 0
    logger.error("Send failed: %s", result.get("error"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
