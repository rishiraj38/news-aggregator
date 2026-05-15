#!/usr/bin/env python3
"""Send a digest preview with thumbnails to one inbox (defaults to owner test address)."""

import argparse
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_EMAIL = "rishiraj438gt@gmail.com"


def main() -> int:
    parser = argparse.ArgumentParser(description="Send digest HTML email with thumbnails (test)")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Recipient (must exist in users table)")
    parser.add_argument("--hours", type=int, default=168, help="Lookback for digests")
    parser.add_argument("--top-n", type=int, default=5, dest="top_n")
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
    ranked = CuratorAgent(profile).rank_digests(digests)
    if not ranked:
        logger.error("Curator returned no ranked articles.")
        return 1

    top = ranked[: args.top_n]
    result = send_personalized_email(user, profile, top)
    if result.get("success"):
        logger.info("Sent digest with %s stories to %s", result.get("articles_count"), args.email)
        return 0
    logger.error("Send failed: %s", result.get("error"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
