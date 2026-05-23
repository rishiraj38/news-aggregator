#!/usr/bin/env python3
"""
Merge topic bundle ids into a user's preferences JSON (same DB as Python pipeline).

  python scripts/set_user_topics.py you@example.com politics,sports,cricket
  python scripts/set_user_topics.py you@example.com politics,sports,cricket,technology
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
load_dotenv(_ROOT / "app" / ".env")
load_dotenv(_ROOT / ".env")

from app.topic_packs.registry import ALLOWED_TOPIC_IDS  # noqa: E402
from app.services.user_service import UserService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Set preferences['topics'] for one user.")
    parser.add_argument("email", help="User email (existing row)")
    parser.add_argument(
        "topics_csv",
        help=f"Comma-separated subset of: {','.join(ALLOWED_TOPIC_IDS)}",
    )
    args = parser.parse_args()
    desired = [t.strip() for t in args.topics_csv.split(",") if t.strip()]
    allowed = set(ALLOWED_TOPIC_IDS)
    bad = [t for t in desired if t not in allowed]
    if bad:
        print("Unknown topic ids:", bad, file=sys.stderr)
        return 1
    if not desired:
        print("Provide at least one topic.", file=sys.stderr)
        return 1

    svc = UserService()
    user = svc.get_user_by_email(args.email.strip())
    if not user:
        print("No user for that email.", file=sys.stderr)
        return 1

    prefs = svc.get_prefs_dict(user)
    prefs["topics"] = desired
    if not svc.update_preferences(user.id, prefs):
        print("Failed to update preferences.", file=sys.stderr)
        return 1

    print(f"Updated {args.email}: topics={desired}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
