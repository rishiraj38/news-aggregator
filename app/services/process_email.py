import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app.agent.email_agent import EmailAgent, RankedArticleDetail, EmailDigestResponse
from app.agent.curator_agent import CuratorAgent
from app.profiles.user_profile import USER_PROFILE
from app.database.repository import Repository
from app.services.email_sender import send_email, digest_to_html
from app.services.mail_links import social_footer_markdown
from app.services.thumbnail_resolve import fetch_og_or_twitter_image


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _resolve_thumbnail_for_digest(d: dict, og_cache: dict) -> str | None:
    """Stored thumb, YouTube default, then one-page OG/Twitter image fetch per article URL."""
    img = d.get("image_url")
    if img:
        return img
    if d.get("article_type") == "youtube" and d.get("article_id"):
        return f"https://i.ytimg.com/vi/{d['article_id']}/hqdefault.jpg"
    url = (d.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return None
    if url not in og_cache:
        og_cache[url] = fetch_og_or_twitter_image(url)
        got = og_cache[url]
        if got:
            logger.info(
                "Resolved thumbnail via OG for %s",
                url[:120] + ("…" if len(url) > 120 else ""),
            )
        else:
            logger.debug("No OG thumbnail for digest %s", d.get("id"))
    return og_cache[url]


def generate_email_digest(hours: int = 24, top_n: int = 10) -> EmailDigestResponse:
    curator = CuratorAgent(USER_PROFILE)
    email_agent = EmailAgent(USER_PROFILE)
    repo = Repository()

    digests = repo.get_recent_digests(hours=hours)
    total = len(digests)

    if total == 0:
        raise ValueError("No digests available")

    logger.info(f"Ranking {total} digests for email generation")
    ranked_articles = curator.rank_digests(digests)

    if not ranked_articles:
        logger.error("Failed to rank digests")
        raise ValueError("Failed to rank articles")

    logger.info(f"Generating email digest with top {top_n} articles")

    og_cache: dict = {}
    article_details = [
        RankedArticleDetail(
            digest_id=a.digest_id,
            rank=a.rank,
            relevance_score=a.relevance_score,
            reasoning=a.reasoning,
            title=next((d["title"] for d in digests if d["id"] == a.digest_id), ""),
            summary=next((d["summary"] for d in digests if d["id"] == a.digest_id), ""),
            url=next((d["url"] for d in digests if d["id"] == a.digest_id), ""),
            article_type=next(
                (d["article_type"] for d in digests if d["id"] == a.digest_id), ""
            ),
            image_url=_resolve_thumbnail_for_digest(
                next((d for d in digests if d["id"] == a.digest_id), {}),
                og_cache,
            ),
        )
        for a in ranked_articles
    ]

    email_digest = email_agent.create_email_digest_response(
        ranked_articles=article_details, total_ranked=len(ranked_articles), limit=top_n
    )

    logger.info("Email digest generated successfully")
    logger.info("\n=== Email Introduction ===")
    logger.info(email_digest.introduction.greeting)
    logger.info(f"\n{email_digest.introduction.introduction}")

    return email_digest


def send_digest_email(hours: int = 24, top_n: int = 10) -> dict:
    repo = Repository()
    digests = repo.get_recent_digests(hours=hours)

    if len(digests) == 0:
        logger.info("No new digests to send. Nothing to send.")
        return {
            "success": True,
            "skipped": True,
            "message": "No new digests available",
            "articles_count": 0,
        }

    try:
        result = generate_email_digest(hours=hours, top_n=top_n)
        markdown_content = result.to_markdown() + "\n\n" + social_footer_markdown()
        html_content = digest_to_html(result)

        subject = f"Daily AI News Digest - {result.introduction.greeting.split('for ')[-1] if 'for ' in result.introduction.greeting else 'Today'}"

        send_email(subject=subject, body_text=markdown_content, body_html=html_content)

        digest_ids = [article.digest_id for article in result.articles]
        marked_count = repo.mark_digests_as_sent(digest_ids)

        logger.info(f"Email sent successfully! Marked {marked_count} digests as sent.")
        return {
            "success": True,
            "subject": subject,
            "articles_count": len(result.articles),
            "marked_as_sent": marked_count,
        }
    except ValueError as e:
        logger.error(f"Error sending email: {e}")
        return {"success": False, "error": str(e)}


def send_personalized_email(
    user, user_profile: dict, top_articles: list, *, is_first_delivery: bool = False
) -> dict:
    """
    Sends a personalized email to a specific user based on pre-ranked articles.
    """
    email_agent = EmailAgent(user_profile)
    repo = Repository()
    
    try:
        # Curator returns RankedArticle (ids + scores); hydrate titles/summaries from Digest rows.
        digest_ids = [a.digest_id for a in top_articles]
        digests_map = {d['id']: d for d in repo.get_digests_by_ids(digest_ids)}
        
        hydrated_articles = []
        og_cache: dict = {}
        for a in top_articles:
            if a.digest_id in digests_map:
                d = digests_map[a.digest_id]
                hydrated_articles.append(
                    RankedArticleDetail(
                        digest_id=a.digest_id,
                        rank=a.rank,
                        relevance_score=a.relevance_score,
                        reasoning=a.reasoning,
                        title=d["title"],
                        summary=d["summary"],
                        url=d["url"],
                        article_type=d["article_type"],
                        image_url=_resolve_thumbnail_for_digest(d, og_cache),
                    )
                )
        
        if not hydrated_articles:
            return {"success": False, "error": "No valid articles found after hydration"}

        email_digest = email_agent.create_email_digest_response(
            ranked_articles=hydrated_articles,
            total_ranked=len(hydrated_articles),
            limit=len(hydrated_articles),
            is_first_delivery=is_first_delivery,
        )

        markdown_content = email_digest.to_markdown() + "\n\n" + social_footer_markdown()
        html_content = digest_to_html(email_digest, is_first_delivery=is_first_delivery)

        current_date_str = datetime.now().strftime("%B %d")
        subject = (
            f"You're in · Your first Helix digest · {current_date_str}"
            if is_first_delivery
            else f"Your Daily AI Digest - {current_date_str}"
        )

        # Send to the specific user's email
        # We temporarily override the env var or modify send_email to take an address
        # But send_email currently uses MY_EMAIL. We need to update send_email to take recipient.
        
        from app.services.email_sender import send_email_to_recipient
        send_email_to_recipient(
            to_email=user.email, 
            subject=subject, 
            body_text=markdown_content, 
            body_html=html_content
        )

        return {
            "success": True, 
            "articles_count": len(hydrated_articles)
        }

    except Exception as e:
        logger.error(f"Error sending personalized email: {e}")
        return {"success": False, "error": str(e)}


def send_admin_welcome_email(user) -> bool:
    """
    Sends a polished welcome email to a newly promoted admin (Instagram + working site links via env).
    """
    try:
        import html as html_mod

        from app.services.email_sender import send_email_to_recipient
        from app.services.mail_links import (
            instagram_handle_for_display,
            instagram_url,
            social_footer_html,
            social_footer_markdown,
            website_url,
        )

        nm = html_mod.escape((user.name or "there").strip() or "there")
        nm_plain = (user.name or "there").strip() or "there"
        subject = "You're in · Helix administrator access unlocked"

        site = website_url()
        ig_url = instagram_url()
        ig_h = instagram_handle_for_display()

        site_cta = ""
        if site:
            ss = html_mod.escape(site, quote=True)
            site_cta = (
                f'<a href="{ss}" '
                'style="display:inline-block;margin-top:12px;color:#eef2ff;font-size:13px;font-weight:600;text-decoration:underline;">'
                "Open the product →</a>"
            )

        ig_parts: list[str] = []
        if ig_url:
            iuq = html_mod.escape(ig_url, quote=True)
            ig_parts.append(
                '<p style="margin:14px 0 0;">'
                f'<a href="{iuq}" style="display:inline-block;background:#fafafa;color:#3730a3;'
                'padding:11px 20px;border-radius:8px;font-weight:700;text-decoration:none;">Follow on Instagram →</a>'
                "</p>"
            )
            if ig_h:
                tip_txt = html_mod.escape("Breaking visuals publish here first · " + ig_h)
                ig_parts.append(
                    f'<p style="margin:8px 0 0;color:#c7d2fe;font-size:13px;line-height:1.4;">{tip_txt}</p>'
                )
        ig_block_html = "".join(ig_parts)

        body_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:620px;margin:0 auto;padding:24px;">
    <table role="presentation" width="100%" style="margin-bottom:20px;background:linear-gradient(135deg,#1e1b4b,#4338ca);border-radius:14px;">
      <tr><td style="padding:32px 28px;color:#f8fafc;">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:#a5b4fc;margin-bottom:6px;">Privileges</div>
        <h1 style="margin:0;font-size:26px;line-height:1.2;color:#ffffff;">Administrator access is live, {nm}.</h1>
        <p style="margin:14px 0 0;color:#e0e7ff;font-size:15px;line-height:1.6;max-width:480px;">
          Uninterrupted curator delivery, personalization priority, and experiments before they graduate to GA.
          Use the taps below whenever you steer from ship.
        </p>
        {ig_block_html}
        {site_cta}
      </td></tr>
    </table>
    <table role="presentation" width="100%" style="background:#fff;border-radius:12px;border:1px solid #e2e8f0;">
      <tr><td style="padding:28px;color:#334155;line-height:1.65;font-size:15px;">
        <p style="margin:0;"><strong>Unlocked straight away</strong></p>
        <ul style="margin:12px 0 0;padding-left:22px;color:#475569;">
          <li>No countdown — admins skip trial limits entirely.</li>
          <li>Same hyper-contextual briefing loop every reader trusts.</li>
          <li>Fast lane whenever curator prompts shift overnight.</li>
        </ul>
        <p style="margin:20px 0 0;color:#475569;font-size:14px;">If a tap fails, reply to this email — founders read threads line-by-line.</p>
      </td></tr>
    </table>
    {social_footer_html()}
    <p style="text-align:center;margin-top:20px;color:#94a3b8;font-size:12px;">
      © Helix AI · Editorial intelligence layer
    </p>
  </div>
</body>
</html>"""

        body_plain = (
            f"Administrator access unlocked, {nm_plain}.\n\n"
            "Unlimited delivery · personalization priority · lab features ahead of GA.\n"
        )
        if site:
            body_plain += f"\nDashboard: {site}\n"
        if ig_url:
            body_plain += f"Instagram: {ig_url}\n"
        if ig_h:
            body_plain += f"Handle for briefing visuals: {ig_h}\n"
        body_plain += "\n— Helix Crew\n\n" + social_footer_markdown()

        send_email_to_recipient(
            to_email=user.email,
            subject=subject,
            body_text=body_plain,
            body_html=body_html,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send admin welcome email to {user.email}: {e}")
        return False


def send_trial_warning_email(user, days_left: int) -> bool:
    """
    Sends a warning email when a user's trial is about to expire (pricing links from HELIX_* env).
    """
    try:
        import html as html_mod

        from app.services.email_sender import send_email_to_recipient
        from app.services.mail_links import (
            pricing_url,
            social_footer_html,
            social_footer_markdown,
            website_url,
        )

        href = pricing_url() or website_url()
        nm = html_mod.escape((user.name or "there").strip() or "there")
        subject = f"Action Required: {days_left} Day{'s' if days_left > 1 else ''} Left in Your Helix Trial ⏳"

        if href:
            h = html_mod.escape(href, quote=True)
            pricing_block = (
                '<div style="text-align:center;margin:35px 0;">'
                f'<a href="{h}" style="background-color:#4F46E5;color:white;padding:14px 28px;'
                'text-decoration:none;border-radius:8px;font-weight:600;font-size:16px;display:inline-block;">'
                "Upgrade my subscription →</a></div>"
                f'<p style="text-align:center;color:#64748b;font-size:13px;margin-top:-12px;">'
                f'<a href="{h}" style="color:#4338CA;">Open pricing in browser</a></p>'
            )
        else:
            pricing_block = (
                '<p style="color:#374151;text-align:center;line-height:1.5;">Reply to this email for a billing link. '
                "(Set HELIX_WEBSITE_URL or HELIX_PRICING_URL in your environment so this button resolves automatically.)</p>"
            )

        body_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px;background-color:#f9fafb;">
    <div style="text-align:center;padding-bottom:20px;"><h2 style="color:#4F46E5;margin-bottom:5px;font-size:28px;">Helix AI News</h2></div>
    <div style="background:#ffffff;padding:40px;border-radius:12px;border:1px solid #e5e7eb;">
        <h1 style="color:#111827;font-size:24px;margin-top:0;font-weight:700;">Hi {nm},</h1>
        <p style="color:#4b5563;font-size:16px;line-height:1.8;">Your curator trial ends in <strong style="color:#dc2626;">{days_left} day{'s' if days_left > 1 else ''}</strong>. Keep the nightly briefing wired to how you actually work.</p>
        <div style="background:#FEF3C7;color:#92400E;padding:20px;border-radius:8px;margin:26px 0;border-left:4px solid #F59E0B;">
            <strong style="display:block;font-size:18px;margin-bottom:6px;">Hang on to the streak</strong>
            Personalized signal is expensive to recreate by hand — don't drop it now.
        </div>
        {pricing_block}
        <p style="color:#64748b;font-size:13px;line-height:1.5;margin-top:20px;">We also summarize the day visually on Instagram (see footer) if you skim faster than you read.</p>
        <p style="color:#4b5563;font-size:15px;margin-bottom:0;">Need help deciding? Reply to this email.</p>
        <p style="color:#4b5563;font-size:15px;margin-top:12px;">Best,<br><strong>The Helix Team</strong></p>
    </div>
    {social_footer_html()}
    <p style="text-align:center;margin-top:20px;color:#9ca3af;font-size:13px;">© Helix AI</p>
</body>
</html>"""

        lines = (
            f"Hi {user.name},\n\n"
            f"Your Helix trial ends in {days_left} day{'s' if days_left > 1 else ''}. "
            "Upgrade to stay on curated AI digests.\n\n"
        )
        lines += (f"Upgrade link: {href}\n\n" if href else "Reply for a Stripe / billing link.\n\n")
        lines += social_footer_markdown() + "\nBest,\nHelix Crew\n"
        send_email_to_recipient(user.email, subject, lines, body_html)
        return True
    except Exception as e:
        logger.error(f"Failed to send trial warning email to {user.email}: {e}")
        return False


def send_trial_expired_email(user) -> bool:
    """
    Sends an email when a user's trial has expired (pricing URLs from HELIX_* env).
    """
    try:
        import html as html_mod

        from app.services.email_sender import send_email_to_recipient
        from app.services.mail_links import (
            pricing_url,
            social_footer_html,
            social_footer_markdown,
            website_url,
        )

        href = pricing_url() or website_url()
        nm = html_mod.escape((user.name or "there").strip() or "there")

        subject = "Your Helix Trial Has Expired 🛑"

        if href:
            h = html_mod.escape(href, quote=True)
            pricing_block = (
                '<div style="text-align:center;margin:35px 0;">'
                f'<a href="{h}" style="background-color:#4F46E5;color:white;padding:14px 28px;'
                'text-decoration:none;border-radius:8px;font-weight:600;font-size:16px;display:inline-block;">'
                "Reactivate my account →</a></div>"
            )
        else:
            pricing_block = (
                '<p style="text-align:center;color:#374151;line-height:1.5;">'
                "Trial paused — reply to this email for a comeback link "
                "(or set HELIX_PRICING_URL / HELIX_WEBSITE_URL for autopilot).</p>"
            )

        body_html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px;background:#f9fafb;">
    <div style="text-align:center;padding-bottom:18px;"><h2 style="color:#4F46E5;font-size:28px;margin:0;">Helix AI News</h2></div>
    <div style="background:#fff;padding:40px;border-radius:12px;border:1px solid #e5e7eb;">
        <h1 style="color:#111827;font-size:24px;margin-top:0;">Hi {nm},</h1>
        <p style="color:#4b5563;font-size:16px;line-height:1.8;">Your curator window closed today — no judgment, calendars move fast.</p>
        <p style="color:#4b5563;font-size:16px;line-height:1.8;">Flip it back on in one gesture; rankings + taste graph stay vaulted.</p>
        {pricing_block}
        <div style="background:#F3F4F6;padding:15px;border-radius:8px;text-align:center;margin-top:24px;">
            <p style="color:#4b5563;font-size:14px;margin:0;">Your profile survives offline — reconnecting restores it verbatim.</p>
        </div>
        <p style="color:#4b5563;font-size:15px;margin-top:22px;">Warmly,<br><strong>The Helix Team</strong></p>
    </div>
    {social_footer_html()}
    <p style="text-align:center;margin-top:20px;color:#9ca3af;font-size:13px;">© Helix AI</p>
</body>
</html>"""

        bt = (
            f"Hi {user.name},\n\nYour Helix trial ended. Restart whenever you're ready.\n\n"
            + (
                f"Pricing / checkout: {href}\n\n"
                if href
                else "Reply for a Stripe / comeback link.\n\n"
            )
            + social_footer_markdown()
            + "\n— Helix Crew\n"
        )

        send_email_to_recipient(user.email, subject, bt, body_html)
        return True
    except Exception as e:
        logger.error(f"Failed to send trial expired email to {user.email}: {e}")
        return False
