#!/usr/bin/env python3
"""
One-time broadcast to every user row in the DB: Helix v1 + Instagram + web app.
Hardcoded URLs by request — not wired into daily_runner.

  python send_helix_v1_broadcast_once.py          # send
  python send_helix_v1_broadcast_once.py --dry-run  # list recipients only
"""

from __future__ import annotations

import html
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / "app" / ".env")
load_dotenv(_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("helix_v1_broadcast")

# --- One-shot constants (do not reuse for ongoing product; use env in app code) ---
HELIX_WEBSITE = "https://helix-seven-eta.vercel.app/"
INSTAGRAM_URL = "https://www.instagram.com/formula1_boys_69/"
INSTAGRAM_HANDLE = "@formula1_boys_69"


def _build_bodies(name: str) -> tuple[str, str]:
    display = (name or "there").strip() or "there"
    safe_name = html.escape(display)
    w_raw = HELIX_WEBSITE.rstrip("/")
    ig_raw = INSTAGRAM_URL.rstrip("/")
    w_attr = html.escape(w_raw + "/", quote=True)
    ig_attr = html.escape(ig_raw + "/", quote=True)

    plain = (
        f"Hey {display},\n\n"
        "Quick note from Helix: we shipped v1 of the curator experience.\n\n"
        f"Browse the product anytime: {w_raw}/\n\n"
        "For quicker visual news hits between digests, follow us on Instagram:\n"
        f"{INSTAGRAM_HANDLE}\n"
        f"{ig_raw}/\n\n"
        "Thanks for being an early reader — we couldn't build this quietly without you.\n\n"
        "— Team Helix\n"
    )

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:560px;margin:0 auto;padding:28px 20px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-radius:14px;overflow:hidden;background:linear-gradient(145deg,#1e1b4b 0%,#4338ca 100%);">
      <tr><td style="padding:26px 24px;color:#eef2ff;">
        <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#a5b4fc;">Helix v1</div>
        <h1 style="margin:8px 0 0;font-size:22px;line-height:1.3;color:#fff;">We're live — thanks for being here, {safe_name}</h1>
        <p style="margin:14px 0 0;font-size:15px;line-height:1.55;color:#e0e7ff;">
          Your daily curator is settling into v1. Between emails, we'll drop visual breakdowns on Instagram —
          tap follow if headlines move faster than your inbox allows.
        </p>
      </td></tr>
    </table>
    <table role="presentation" width="100%" style="margin-top:18px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;">
      <tr><td style="padding:22px;color:#334155;line-height:1.6;font-size:15px;">
        <p style="margin:0;"><strong>Open Helix</strong></p>
        <p style="margin:10px 0 0;"><a href="{w_attr}" style="color:#4338CA;font-weight:600;font-size:15px;">helix-seven-eta.vercel.app →</a></p>
        <p style="margin:18px 0 0;"><strong>Follow for news updates</strong></p>
        <p style="margin:10px 0 0;">
          <a href="{ig_attr}" style="display:inline-block;background:#4338CA;color:#fff;text-decoration:none;
            padding:10px 18px;border-radius:8px;font-weight:700;">Instagram ({html.escape(INSTAGRAM_HANDLE)})</a>
        </p>
        <p style="margin:22px 0 0;color:#64748b;font-size:13px;">No billing pitch here — just a thank-you and fresher lanes to the same intel.</p>
        <p style="margin:14px 0 0;color:#475569;font-size:14px;">Warmly,<br><strong>Team Helix</strong></p>
      </td></tr>
    </table>
    <p style="text-align:center;margin-top:20px;color:#94a3b8;font-size:12px;">You received this as a Helix subscriber.</p>
  </div>
</body>
</html>"""
    return plain, html_body


def main() -> int:
    dry = "--dry-run" in sys.argv

    from app.database.connection import engine, get_session
    from app.database.models import Base, User

    Base.metadata.create_all(engine)
    session = get_session()
    try:
        users = session.query(User).order_by(User.email).all()
    finally:
        session.close()

    if not users:
        logger.error("No users in database — nothing to send.")
        return 1

    subject = "Helix v1 · Thanks — follow us on Instagram for news updates"

    from app.services.email_sender import send_email_to_recipient

    ok = 0
    failures: list[tuple[str, str]] = []
    logger.info("%d recipient(s)%s", len(users), " (dry-run)" if dry else "")

    for i, u in enumerate(users):
        text, ht = _build_bodies(u.name)
        logger.info("[%s/%s] %s <%s>", i + 1, len(users), (u.name or "").strip(), u.email)
        if dry:
            ok += 1
            continue
        try:
            send_email_to_recipient(to_email=u.email, subject=subject, body_text=text, body_html=ht)
            ok += 1
            time.sleep(1.2)
        except Exception as e:
            failures.append((u.email, str(e)))
            logger.error("Failed %s: %s", u.email, e)

    logger.info("Done: %s ok, %s failed.", ok, len(failures))
    if failures:
        for em, err in failures:
            logger.error("  %s: %s", em, err)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
