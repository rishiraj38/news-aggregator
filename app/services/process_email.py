import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app.agent.email_agent import EmailAgent, RankedArticleDetail, EmailDigestResponse
from app.agent.curator_agent import CuratorAgent
from app.profiles.user_profile import USER_PROFILE
from app.database.repository import Repository
from app.services.email_sender import send_email, digest_to_html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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
        markdown_content = result.to_markdown()
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


def send_personalized_email(user, user_profile: dict, top_articles: list) -> dict:
    """
    Sends a personalized email to a specific user based on pre-ranked articles.
    """
    email_agent = EmailAgent(user_profile)
    repo = Repository()
    
    try:
        # Convert RankedArticle objects to RankedArticleDetail objects expected by EmailAgent
        article_details = [
            RankedArticleDetail(
                digest_id=a.digest_id,
                rank=a.rank,
                relevance_score=a.relevance_score,
                reasoning=a.reasoning,
                title=getattr(a, 'title', "Unknown"), # Curator might return objects with title
                summary=getattr(a, 'summary', "No summary"),
                url=getattr(a, 'url', "#"),
                article_type=getattr(a, 'article_type', "article"),
            )
            for a in top_articles
        ]
        
        # Hydrate missing details if needed (in case Curator returned minimal objects)
        # Note: In the current flow, Curator returns fully hydrated objects, 
        # but if we needed to fetch from DB, we would do it here using digest_id.
        # For this implementation, we assume top_articles has what we need 
        # (which is true if CuratorAgent.rank_digests returns rich objects).
        
        # Actually, CuratorAgent returns RankedArticle which only has ID/Score/Reasoning.
        # We need to fetch the actual Digest details!
        
        # Let's fix the hydration:
        digest_ids = [a.digest_id for a in top_articles]
        digests_map = {d['id']: d for d in repo.get_digests_by_ids(digest_ids)}
        
        hydrated_articles = []
        for a in top_articles:
            if a.digest_id in digests_map:
                d = digests_map[a.digest_id]
                hydrated_articles.append(
                    RankedArticleDetail(
                        digest_id=a.digest_id,
                        rank=a.rank,
                        relevance_score=a.relevance_score,
                        reasoning=a.reasoning,
                        title=d['title'],
                        summary=d['summary'],
                        url=d['url'],
                        article_type=d['article_type']
                    )
                )
        
        if not hydrated_articles:
            return {"success": False, "error": "No valid articles found after hydration"}

        email_digest = email_agent.create_email_digest_response(
            ranked_articles=hydrated_articles, 
            total_ranked=len(hydrated_articles), 
            limit=len(hydrated_articles)
        )

        markdown_content = email_digest.to_markdown()
        html_content = digest_to_html(email_digest)

        current_date_str = datetime.now().strftime("%B %d")
        subject = f"Your Daily AI Digest - {current_date_str}"

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
    Sends a welcome email to a newly promoted admin.
    """
    try:
        from app.services.email_sender import send_email_to_recipient
        
        subject = "Welcome to Helix Admin Access 🚀"
        
        body_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Welcome to Helix Admin</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #4F46E5;">Welcome to Helix Admin, {user.name}!</h1>
    <p>You have been upgraded to <strong>Administrator</strong> status.</p>
    <div style="background-color: #F3F4F6; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <p style="margin-top: 0;"><strong>Your Privileges:</strong></p>
        <ul style="margin-bottom: 0;">
            <li>Unlimited Access (No 30-day trial expiry)</li>
            <li>Priority Delivery</li>
            <li>Access to all experimental features</li>
        </ul>
    </div>
    <p>Thank you for leading the way.</p>
    <p>Best,<br>The Helix Team</p>
</body>
</html>"""
        
        body_text = f"""Welcome to Helix Admin, {user.name}!

You have been upgraded to Administrator status.

Your Privileges:
- Unlimited Access (No 30-day trial expiry)
- Priority Delivery
- Access to all experimental features

Thank you for leading the way.

Best,
The Helix Team"""
        
        send_email_to_recipient(
            to_email=user.email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send admin welcome email to {user.email}: {e}")
        return False

def send_trial_warning_email(user, days_left: int) -> bool:
    """
    Sends a warning email to a user when their trial is about to expire.
    """
    try:
        from app.services.email_sender import send_email_to_recipient
        
        subject = f"Action Required: {days_left} Day{'s' if days_left > 1 else ''} Left in Your Helix Trial ⏳"
        
        body_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Trial Expiring Soon</title>
</head>
<body style="font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9fafb;">
    <div style="text-align: center; padding-bottom: 20px;">
        <h2 style="color: #4F46E5; margin-bottom: 5px; font-size: 28px;">Helix AI News</h2>
    </div>
    <div style="background-color: #ffffff; padding: 40px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);">
        <h1 style="color: #111827; font-size: 24px; margin-top: 0; font-weight: 700;">Hi {user.name},</h1>
        <p style="color: #4b5563; font-size: 16px; line-height: 1.8;">We hope you're enjoying your curated tech insights. This is a quick reminder that your free trial will expire in <strong style="color: #dc2626; font-size: 18px;">{days_left} day{'s' if days_left > 1 else ''}</strong>.</p>
        
        <div style="background-color: #FEF3C7; color: #92400E; padding: 20px; border-radius: 8px; margin: 30px 0; border-left: 4px solid #F59E0B;">
            <strong style="display: block; font-size: 18px; margin-bottom: 5px;">Don't lose access!</strong> You'll miss out on personalized AI news and curated insights. Upgrade now to keep your edge in tech.
        </div>
        
        <div style="text-align: center; margin: 35px 0;">
            <a href="https://helix.news/pricing" style="background-color: #4F46E5; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; transition: all 0.2s;">Upgrade My Subscription</a>
        </div>
        
        <p style="color: #4b5563; font-size: 15px; margin-bottom: 0;">If you have any questions or need help, just reply to this email.</p>
        <p style="color: #4b5563; font-size: 15px; margin-top: 10px;">Best,<br><strong>The Helix Team</strong></p>
    </div>
    <div style="text-align: center; margin-top: 25px; color: #9ca3af; font-size: 13px;">
        <p>&copy; 2024 Helix AI. All rights reserved.</p>
    </div>
</body>
</html>"""
        
        body_text = f"Hi {user.name},\n\nYour Helix trial expires in {days_left} day{'s' if days_left > 1 else ''}. Upgrade your subscription to keep receiving your daily personalized AI digests.\n\nUpgrade here: https://helix.news/pricing\n\nBest,\nThe Helix Team"
        
        send_email_to_recipient(user.email, subject, body_text, body_html)
        return True
    except Exception as e:
        logger.error(f"Failed to send trial warning email to {user.email}: {e}")
        return False

def send_trial_expired_email(user) -> bool:
    """
    Sends an email to a user when their trial has expired.
    """
    try:
        from app.services.email_sender import send_email_to_recipient
        
        subject = "Your Helix Trial Has Expired 🛑"
        
        body_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Trial Expired</title>
</head>
<body style="font-family: 'Inter', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9fafb;">
    <div style="text-align: center; padding-bottom: 20px;">
        <h2 style="color: #4F46E5; margin-bottom: 5px; font-size: 28px;">Helix AI News</h2>
    </div>
    <div style="background-color: #ffffff; padding: 40px; border-radius: 12px; border: 1px solid #e5e7eb; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);">
        <h1 style="color: #111827; font-size: 24px; margin-top: 0; font-weight: 700;">Hi {user.name},</h1>
        <p style="color: #4b5563; font-size: 16px; line-height: 1.8;">Your free trial of Helix AI News has officially expired. We hope you discovered some incredible insights and enjoyed having a personal AI curator!</p>
        
        <p style="color: #4b5563; font-size: 16px; line-height: 1.8;">To reactivate your personalized daily digests and continue staying ahead of the tech curve without the noise, please subscribe to one of our premium plans.</p>
        
        <div style="text-align: center; margin: 35px 0;">
            <a href="https://helix.news/pricing" style="background-color: #4F46E5; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; display: inline-block; transition: all 0.2s;">Reactivate My Account</a>
        </div>
        
        <div style="background-color: #F3F4F6; padding: 15px; border-radius: 8px; text-align: center;">
            <p style="color: #4b5563; font-size: 14px; margin: 0;">We have securely saved your custom curator profile, so you can pick up right where you left off!</p>
        </div>
        <p style="color: #4b5563; font-size: 15px; margin-top: 20px;">Best,<br><strong>The Helix Team</strong></p>
    </div>
    <div style="text-align: center; margin-top: 25px; color: #9ca3af; font-size: 13px;">
        <p>&copy; 2024 Helix AI. All rights reserved.</p>
    </div>
</body>
</html>"""
        
        body_text = f"Hi {user.name},\n\nYour free trial of Helix has expired. To reactivate your daily digests, please subscribe to one of our premium plans.\n\nSubscribe here: https://helix.news/pricing\n\nBest,\nThe Helix Team"
        
        send_email_to_recipient(user.email, subject, body_text, body_html)
        return True
    except Exception as e:
        logger.error(f"Failed to send trial expired email to {user.email}: {e}")
        return False
