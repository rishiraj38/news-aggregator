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
        
        body_html = f"""
        <h1>Welcome to Helix Admin, {user.name}!</h1>
        <p>You have been upgraded to <strong>Administrator</strong> status.</p>
        <p><strong>Your Privileges:</strong></p>
        <ul>
            <li>Unlimited Access (No 30-day trial expiry)</li>
            <li>Priority Delivery</li>
            <li>Access to all experimental features</li>
        </ul>
        <p>Thank you for leading the way.</p>
        <p>Best,<br>The Helix Team</p>
        """
        
        body_text = f"""
        Welcome to Helix Admin, {user.name}!
        
        You have been upgraded to Administrator status.
        
        Your Privileges:
        - Unlimited Access (No 30-day trial expiry)
        - Priority Delivery
        - Access to all experimental features
        
        Thank you for leading the way.
        
        Best,
        The Helix Team
        """
        
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
