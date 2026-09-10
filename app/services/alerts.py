"""Operational alerts for the daily pipeline.

The September 2026 incident ran for weeks: the workflow stayed green while
scraping one source and emailing nobody, and it was only caught by reading logs
by hand. Silence was indistinguishable from success.

This module makes the pipeline report its own failures over the SMTP account it
already uses for digests, so no extra service or credential is needed. Alerts
are strictly best-effort — a failure to send one must never take down the run
that is already having a bad day.
"""

from __future__ import annotations

import html as html_mod
import logging
import os
import socket
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def alerts_enabled() -> bool:
    return str(os.getenv("PIPELINE_ALERTS_ENABLED", "true")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def alert_recipients() -> List[str]:
    """Where alerts go: PIPELINE_ALERT_EMAIL (comma-separated), else MY_EMAIL."""
    raw = os.getenv("PIPELINE_ALERT_EMAIL") or os.getenv("MY_EMAIL") or ""
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def detect_pipeline_problems(results: Dict[str, Any]) -> List[str]:
    """Return human-readable problems worth waking someone up for.

    Deliberately narrow: a quiet news day is not an incident, but a run that
    reached subscribers and delivered nothing definitely is.
    """
    problems: List[str] = []

    if results.get("error"):
        problems.append(f"Pipeline raised an error: {results['error']}")

    scraping = results.get("scraping") or {}
    counts = {k: v for k, v in scraping.items() if isinstance(v, int)}
    total_scraped = sum(counts.values())

    if counts and total_scraped == 0:
        problems.append(
            f"Every one of the {len(counts)} sources returned 0 articles — "
            "ingestion is broken, not merely quiet."
        )
    elif counts:
        dead = sorted(k for k, v in counts.items() if v == 0)
        # One or two quiet feeds is normal; most of them failing is not.
        if len(dead) >= max(3, len(counts) // 2):
            problems.append(
                f"{len(dead)} of {len(counts)} sources returned nothing: {', '.join(dead)}"
            )

    users = results.get("user_digests", 0) or 0
    emails = results.get("emails_sent", 0) or 0
    if users > 0 and emails == 0:
        problems.append(
            f"{users} subscriber(s) were processed but 0 emails were delivered."
        )

    digests = results.get("digests") or {}
    if digests.get("total", 0) and digests.get("processed", 0) == 0:
        problems.append(
            f"All {digests['total']} digest generations failed — check the LLM provider."
        )

    return problems


def _build_bodies(problems: List[str], results: Dict[str, Any]) -> tuple[str, str]:
    scraping = results.get("scraping") or {}
    counts = {k: v for k, v in scraping.items() if isinstance(v, int)}
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    where = os.getenv("GITHUB_REPOSITORY") or socket.gethostname()
    run_url = ""
    if os.getenv("GITHUB_RUN_ID") and os.getenv("GITHUB_REPOSITORY"):
        run_url = (
            f"https://github.com/{os.environ['GITHUB_REPOSITORY']}"
            f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
        )

    lines = [
        f"Helix pipeline needs attention — {when} ({where})",
        "",
        "Problems:",
    ]
    lines += [f"  - {p}" for p in problems]
    lines += [
        "",
        "Run summary:",
        f"  duration:        {results.get('duration_seconds', 0):.0f}s",
        f"  articles scraped:{sum(counts.values())}",
        f"  digests created: {(results.get('digests') or {}).get('processed', 0)}",
        f"  users processed: {results.get('user_digests', 0)}",
        f"  emails sent:     {results.get('emails_sent', 0)}",
        "",
        "Per-source scrape counts:",
    ]
    lines += [f"  {k}: {counts[k]}" for k in sorted(counts)] or ["  (none)"]
    if run_url:
        lines += ["", f"Workflow run: {run_url}"]

    text = "\n".join(lines)

    rows = "".join(
        f"<tr><td style='padding:4px 12px 4px 0;color:#475569'>{html_mod.escape(k)}</td>"
        f"<td style='padding:4px 0;font-weight:600;color:{'#b91c1c' if counts[k] == 0 else '#0f172a'}'>"
        f"{counts[k]}</td></tr>"
        for k in sorted(counts)
    )
    problem_items = "".join(f"<li>{html_mod.escape(p)}</li>" for p in problems)
    run_link = (
        f"<p style='margin:16px 0 0'><a href='{run_url}' "
        "style='color:#4f46e5'>Open the workflow run</a></p>"
        if run_url
        else ""
    )

    html = f"""<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;color:#0f172a">
  <h2 style="margin:0 0 4px;font-size:18px">Helix pipeline needs attention</h2>
  <p style="margin:0 0 16px;color:#64748b;font-size:13px">{html_mod.escape(when)} · {html_mod.escape(where)}</p>
  <ul style="margin:0 0 20px;padding-left:20px;color:#b91c1c">{problem_items}</ul>
  <table style="border-collapse:collapse;font-size:13px;margin-bottom:18px">
    <tr><td style="padding:4px 12px 4px 0;color:#475569">Duration</td><td style="padding:4px 0;font-weight:600">{results.get('duration_seconds', 0):.0f}s</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#475569">Articles scraped</td><td style="padding:4px 0;font-weight:600">{sum(counts.values())}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#475569">Digests created</td><td style="padding:4px 0;font-weight:600">{(results.get('digests') or {}).get('processed', 0)}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#475569">Users processed</td><td style="padding:4px 0;font-weight:600">{results.get('user_digests', 0)}</td></tr>
    <tr><td style="padding:4px 12px 4px 0;color:#475569">Emails sent</td><td style="padding:4px 0;font-weight:600">{results.get('emails_sent', 0)}</td></tr>
  </table>
  <h3 style="margin:0 0 6px;font-size:14px">Per-source scrape counts</h3>
  <table style="border-collapse:collapse;font-size:13px">{rows}</table>
  {run_link}
</div>"""

    return text, html


def send_pipeline_alert(results: Dict[str, Any]) -> Optional[bool]:
    """Email an alert if this run looks broken. Returns True when one was sent.

    Never raises: an alert failing is not a reason to fail the pipeline.
    """
    try:
        if not alerts_enabled():
            return None

        problems = detect_pipeline_problems(results)
        if not problems:
            return None

        recipients = alert_recipients()
        if not recipients:
            logger.warning(
                "Pipeline problems detected but no alert recipient configured "
                "(set PIPELINE_ALERT_EMAIL or MY_EMAIL): %s",
                "; ".join(problems),
            )
            return None

        text, html = _build_bodies(problems, results)
        subject = f"⚠️ Helix pipeline: {problems[0][:80]}"

        from app.services.email_sender import send_email

        send_email(subject, text, html, recipients=recipients)
        logger.info("Sent pipeline alert to %s", ", ".join(recipients))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not send pipeline alert: %s", exc)
        return False
