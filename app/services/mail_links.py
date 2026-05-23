"""Public links for transactional and digest emails (override via env; never invent URLs in LLM prompts)."""

from __future__ import annotations

import os
import urllib.parse


def _strip_base(url: str) -> str:
    u = (url or "").strip()
    return u[:-1] if u.endswith("/") else u


def website_url() -> str:
    """
    Canonical public app / marketing site URL.
    Prefer HELIX_WEBSITE_URL (or legacy HELIX_PUBLIC_SITE_URL).
    Ensures scheme so mail clients open it first tap.
    """
    raw = (os.getenv("HELIX_WEBSITE_URL") or os.getenv("HELIX_PUBLIC_SITE_URL") or "").strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw.lstrip("/")
    return _strip_base(raw)


def pricing_url() -> str:
    explicit = (os.getenv("HELIX_PRICING_URL") or "").strip()
    if explicit:
        if not explicit.startswith(("http://", "https://")):
            explicit = "https://" + explicit.lstrip("/")
        return _strip_base(explicit)
    base = website_url()
    return f"{base}/pricing" if base else ""


def instagram_url() -> str:
    raw = (os.getenv("HELIX_INSTAGRAM_URL") or "").strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw.lstrip("/")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme and parsed.netloc:
        return _strip_base(urllib.parse.urlunsplit(parsed))
    return _strip_base(raw)


def instagram_handle_for_display() -> str:
    h = (os.getenv("HELIX_INSTAGRAM_HANDLE") or "").strip()
    if not h:
        u = instagram_url()
        if "instagram.com/" in u:
            tail = u.split("instagram.com/", 1)[-1].strip("/ ").split("/", 1)[0]
            if tail and tail not in ("", "accounts"):
                h = tail if tail.startswith("@") else f"@{tail}"
    if not h:
        return ""
    return h if h.startswith("@") else f"@{h}"


def social_footer_markdown() -> str:
    """Append to plain-text digest for parity with HTML footer."""
    lines = ["---", "**Stay connected**"]
    ig = instagram_url()
    ig_h = instagram_handle_for_display()
    if ig:
        label = f"Follow us on Instagram ({ig_h})" if ig_h else "Follow us on Instagram"
        lines.append(f"- {label}: {ig}")
    site = website_url()
    if site:
        lines.append(f"- Manage your tastes & newsletter: {site}")
    if len(lines) <= 2:
        return ""
    return "\n".join(lines) + "\n"


def social_footer_html() -> str:
    """Muted footer row for transactional + digest templates."""
    import html as html_module

    ig = instagram_url()
    ig_h = instagram_handle_for_display()
    site = website_url()
    chunks: list[str] = []

    if ig:
        safe_ig = html_module.escape(ig, quote=True)
        ih = html_module.escape(ig_h) if ig_h else ""
        chunks.append(
            '<p style="margin:8px 0 0;"><a href="'
            + safe_ig
            + '" style="color:#4338CA;font-weight:600;">Follow us on Instagram</a>'
            + (f'<span style="color:#64748b;"> · {ih}</span>' if ih else "")
            + "</p>"
        )
    if site:
        safe = html_module.escape(site, quote=True)
        chunks.append(
            f'<p style="margin:8px 0 0;"><a href="{safe}" '
            'style="color:#4338CA;font-weight:500;">Website &amp; newsletter settings</a></p>'
        )
    if not chunks:
        return ""
    inner = "".join(chunks)
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:28px;">
      <tr><td style="border-top:1px solid #e2e8f0;padding-top:18px;color:#64748b;font-size:13px;line-height:1.5;">
        {inner}
      </td></tr>
    </table>"""


def first_digest_hero_html() -> str:
    """Editorial onboarding strip for HTML digests — only when it's the subscriber's first send."""
    import html as html_module

    site = website_url()
    ig = instagram_url()
    ig_h = instagram_handle_for_display()
    cta_visit = ""
    if site:
        su = html_module.escape(site, quote=True)
        cta_visit = (
            f'<a href="{su}" style="display:inline-block;margin-top:10px;color:#eef2ff;'
            f'font-size:13px;font-weight:600;text-decoration:underline;">Open your dashboard →</a>'
        )

    tagline_parts: list[str] = []
    if ig_h:
        tagline_parts.append(html_module.escape(ig_h))
    if ig:
        tagline_parts.append(html_module.escape("Daily briefing visuals"))
    tagline_line = ""
    if tagline_parts:
        tagline_line = " · ".join(tagline_parts)

    subtitle_html = ""
    if tagline_line:
        subtitle_html = f'<p style="margin:14px 0 0;color:#c7d2fe;font-size:14px;">{tagline_line}</p>'
    ig_cta = ""
    if ig:
        iu = html_module.escape(ig, quote=True)
        ig_cta = (
            f'<a href="{iu}" style="display:inline-block;margin-top:14px;background:#fff;color:#312e81;'
            'padding:10px 18px;border-radius:8px;font-size:14px;font-weight:700;text-decoration:none;">'
            "Follow on Instagram</a>"
        )

    return f'''
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;background:linear-gradient(135deg,#1e1b4b 0%,#4338ca 55%,#6366f1 100%);border-radius:12px;">
      <tr><td style="padding:26px 24px;color:#eef2ff;">
        <p style="margin:0;font-size:12px;text-transform:uppercase;letter-spacing:0.12em;color:#a5b4fc;">You're in.</p>
        <h2 style="margin:8px 0 0;font-size:22px;font-weight:700;line-height:1.25;color:#f8fafc;">
          Welcome to Helix — your personal AI curator
        </h2>
        <p style="margin:12px 0 0;color:#e0e7ff;font-size:15px;line-height:1.55;max-width:520px;">
          This is your first personalized roundup. Tomorrow's note will arrive on the same schedule — built from your interests, not algorithms alone.
          Open any story below when you want the full picture.
        </p>
        {subtitle_html}
        <p style="margin:14px 0 0;display:flex;flex-wrap:wrap;gap:10px;align-items:center;">
          {ig_cta}
        </p>
        {cta_visit}
      </td></tr>
    </table>'''
