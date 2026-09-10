#!/usr/bin/env python3
"""
Set preferences['keywords'] for one user (same DB as the Python pipeline).

Each keyword becomes its own ingest lane (Google News search + Hacker News),
and matching stories are routed only to subscribers tracking that term.

  python scripts/set_user_keywords.py you@example.com "ai agents,nvidia earnings"
  python scripts/set_user_keywords.py you@example.com --clear
  python scripts/set_user_keywords.py you@example.com --show
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

from app.services.user_service import UserService  # noqa: E402
from app.topic_packs.keywords import (  # noqa: E402
    MAX_KEYWORDS_PER_USER,
    keyword_source_key,
    normalize_keyword_list,
    user_keywords,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Set preferences['keywords'] for one user.")
    parser.add_argument("email", help="User email (existing row)")
    parser.add_argument(
        "keywords_csv",
        nargs="?",
        default="",
        help=f"Comma-separated terms (max {MAX_KEYWORDS_PER_USER})",
    )
    parser.add_argument("--clear", action="store_true", help="Remove all keywords")
    parser.add_argument("--show", action="store_true", help="Print current keywords and exit")
    args = parser.parse_args()

    svc = UserService()
    user = svc.get_user_by_email(args.email.strip())
    if not user:
        print("No user for that email.", file=sys.stderr)
        return 1

    prefs = svc.get_prefs_dict(user)

    if args.show:
        current = user_keywords(prefs)
        print(f"{args.email}: {current or '(none)'}")
        for kw in current:
            print(f"  {kw} → {keyword_source_key(kw)}")
        return 0

    if args.clear:
        desired: list[str] = []
    else:
        if not args.keywords_csv.strip():
            print("Provide keywords, or pass --clear / --show.", file=sys.stderr)
            return 1
        desired = normalize_keyword_list(args.keywords_csv.split(","))
        if not desired:
            print("No usable keywords after normalization.", file=sys.stderr)
            return 1

    prefs["keywords"] = desired
    if not svc.update_preferences(user.id, prefs):
        print("Failed to update preferences.", file=sys.stderr)
        return 1

    print(f"Updated {args.email}: keywords={desired or '(cleared)'}")
    for kw in desired:
        print(f"  {kw} → {keyword_source_key(kw)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
