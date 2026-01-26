import logging
from datetime import datetime
from dotenv import load_dotenv

from app.runner import run_scrapers
from app.services.process_anthropic import process_anthropic_markdown
from app.services.process_youtube import process_youtube_transcripts
from app.services.process_digest import process_digests
from app.services.process_email import send_digest_email
from app.database.models import Base
from app.database.connection import engine
from app.database.repository import Repository

load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _is_scrape_recent():
    try:
        with open(".last_scrape", "r") as f:
            last_scrape_ts = float(f.read().strip())
        last_scrape = datetime.fromtimestamp(last_scrape_ts)
        # 60 minutes cooldown
        return (datetime.now() - last_scrape).total_seconds() < 3600
    except Exception:
        return False

def _update_last_scrape():
    try:
        with open(".last_scrape", "w") as f:
            f.write(str(datetime.now().timestamp()))
    except Exception as e:
        logger.warning(f"Failed to update scrape cache timestamp: {e}")


def run_daily_pipeline(hours: int = 24, top_n: int = 10, force_scrape: bool = False) -> dict:
    from datetime import timezone
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("Starting Daily AI News Aggregator Pipeline")
    logger.info("=" * 60)

    results = {
        "start_time": start_time.isoformat(),
        "scraping": {},
        "processing": {},
        "digests": {},
        "email": {},
        "email": {},
        "success": False,
    }

    # Initialize Repository and logging
    repo = Repository()
    try:
        pipeline_run = repo.create_pipeline_run()
        run_id = pipeline_run.id
    except Exception as e:
        logger.error(f"Failed to create pipeline run record: {e}")
        run_id = None

    def log_progress(msg: str):
        logger.info(msg)
        if run_id:
            try:
                repo.update_pipeline_run(run_id, log_entry=msg)
            except Exception:
                pass


    try:
        logger.info("\n[0/5] Ensuring database tables exist...")
        try:
            with engine.connect() as conn:
                Base.metadata.create_all(engine)
                log_progress("✓ Database tables verified/created")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise

        if not force_scrape and _is_scrape_recent():
            logger.info("\n[1/5] Using cached scrape data (Last scrape < 60 mins ago). Skipping new checks.")
            results["scraping"] = {"status": "cached"}
            log_progress("Using cached scrape data.")
        else:
            log_progress("\n[1/5] Scraping articles from sources...")
            scraping_results = run_scrapers(hours=hours)
            results["scraping"] = {
                "youtube": len(scraping_results.get("youtube", [])),
                "openai": len(scraping_results.get("openai", [])),
                "anthropic": len(scraping_results.get("anthropic", [])),
            }
            logger.info(
                f"✓ Scraped {results['scraping']['youtube']} YouTube videos, "
                f"{results['scraping']['openai']} OpenAI articles, "
                f"{results['scraping']['anthropic']} Anthropic articles"
            )
            _update_last_scrape()


        log_progress("\n[2/5] Processing Anthropic markdown...")
        anthropic_result = process_anthropic_markdown()
        results["processing"]["anthropic"] = anthropic_result
        logger.info(
            f"✓ Processed {anthropic_result['processed']} Anthropic articles "
            f"({anthropic_result['failed']} failed)"
        )

        log_progress("\n[3/5] Processing YouTube transcripts...")
        youtube_result = process_youtube_transcripts()
        results["processing"]["youtube"] = youtube_result
        logger.info(
            f"✓ Processed {youtube_result['processed']} transcripts "
            f"({youtube_result['unavailable']} unavailable)"
        )

        log_progress("\n[4/5] Creating digests for articles...")
        digest_result = process_digests()
        results["digests"] = digest_result
        logger.info(
            f"✓ Created {digest_result['processed']} digests "
            f"({digest_result['failed']} failed out of {digest_result['total']} total)"
        )

        log_progress("\n[5/5] Generating personalized digests for users...")
        
        # repo already initialized above
        active_users = repo.get_active_users()
        log_progress(f"Found {len(active_users)} active users")

        if not active_users:
            logger.info("No active users found. Skipping personalization.")
        
        from app.agent.curator_agent import CuratorAgent
        from app.services.process_email import send_personalized_email
        from app.services.user_service import UserService
        
        user_service = UserService()
        
        # Get all recent digests once
        recent_digests = repo.get_recent_digests(hours=hours, exclude_sent=False)
        if not recent_digests:
             logger.info("No digests available to rank.")
             results["user_digests"] = 0
             return results

        user_count = 0
        email_count = 0
        
        for user in active_users:
            try:
                user_count += 1
                if run_id:
                     repo.update_pipeline_run(run_id, users_processed=user_count)
                
                msg = f"--- Processing for user: {user.name} ({user.email}) ---"
                logger.info(msg)
                log_progress(msg)

                # Refresh user from DB to get latest flags (prevents stale data)
                repo.session.refresh(user)

                # 0. Check for New Admin Promotion - ROBUST CHECK
                # Handle "True", "true", True (bool), etc.
                admin_flag = str(user.admin_welcome_sent).lower()
                
                if user.role == "admin" and admin_flag != "true":
                    from app.services.process_email import send_admin_welcome_email
                    logger.info(f"User {user.email} is a new admin. Sending welcome email...")
                    if send_admin_welcome_email(user):
                        repo.update_user_admin_welcome(user.id)
                        repo.session.refresh(user)  # Refresh to get updated flag
                        logger.info(f"✓ Admin welcome email sent and flagged (flag now: {user.admin_welcome_sent}).")
                    else:
                        logger.error("✗ Failed to send admin welcome email.")
                user_profile = user_service.get_user_profile(user)
                
                # 1.5 Filter out already seen digests
                seen_digest_ids = set(repo.get_user_recommended_digest_ids(user.id))
                logger.info(f"User {user.name} has {len(seen_digest_ids)} previously recommended digests")
                logger.debug(f"Seen IDs sample: {list(seen_digest_ids)[:5] if seen_digest_ids else []}")
                
                unseen_digests = [d for d in recent_digests if d['id'] not in seen_digest_ids]
                
                if not unseen_digests:
                    msg = f"No new digests for {user.name} (All {len(recent_digests)} recent items already recommended). Skipping."
                    logger.info(msg)
                    log_progress(msg)
                    import time; time.sleep(0.5) # Small sleep to avoid instant loops looking like bugs
                    continue
                
                logger.info(f"Ranking {len(unseen_digests)} new digests for {user.name} (out of {len(recent_digests)} total recent)...")

                # 2. Rank Content
                curator = CuratorAgent(user_profile)
                ranked_articles = curator.rank_digests(unseen_digests)
                
                if not ranked_articles:
                    msg = f"No relevant articles found for {user.name} in new batch. Skipping."
                    logger.info(msg)
                    log_progress(msg)
                    continue

                # 3. Save Recommendations
                top_articles = ranked_articles[:top_n]
                new_recommendations = []
                final_articles_to_send = []

                for article in top_articles:
                    # Check if already recommended *before* creating call to avoid DB hit?
                    # Repo handle check inside. We need to know if it was created NOW or existed.
                    # Let's modify logic: check existence first? 
                    # Simpler: Repo returns the object. We can assume if we are running daily, we only want to notify about stuff created in this run?
                    # Or we check if the recommendation is 'fresh'.
                    
                    # Workaround: Check repo for existence manually or modify repo. 
                    # Let's rely on exclude_sent=False fetching OLD digests, so existing recs exist.
                    
                    rec = repo.create_recommendation(
                        user_id=user.id,
                        digest_id=article.digest_id,
                        relevance_score=article.relevance_score,
                        rank=article.rank,
                        reasoning=article.reasoning
                    )
                    
                    # If the recommendation was just created, its created_at would be very close to now.
                    # But reliable way: repo.create_recommendation could return a flag?
                    # Let's assume for this fix: We only send articles if they haven't been recommended before.
                    # Since create_recommendation handles idempotency, we can check if it was 'newly' made.
                    # Hack: Check if rec.created_at > start_time
                    
                    if not rec:
                        logger.warning(f"Skipping invalid digest recommendation: {article.digest_id}")
                        continue

                    if rec.created_at >= start_time.replace(tzinfo=rec.created_at.tzinfo):
                        new_recommendations.append(rec)
                        final_articles_to_send.append(article)
                
                logger.info(f"Saved {len(new_recommendations)} NEW recommendations for {user.name}")

                if not final_articles_to_send:
                     msg = f"No new recommendations for {user.name}. Skipping email."
                     logger.info(msg)
                     log_progress(msg)
                     continue

                # 4. Send Email
                # We need to adapt send_digest_email to take a user object and list of recommendations
                email_result = send_personalized_email(user, user_profile, final_articles_to_send)
                
                if email_result["success"]:
                    email_count += 1
                if email_result["success"]:
                    email_count += 1
                    log_progress(f"✓ Email sent to {user.email}")
                else:
                    logger.error(f"✗ Failed to send email to {user.email}: {email_result.get('error')}")

            except Exception as e:
                logger.error(f"Error processing for user {user.email}: {e}")
            
            # Rate Limit Protection (Groq has RPM limits)
            # Increased to 10s to stay safely below 30 RPM (approx 6 RPM)
            import time
            logger.info("Sleeping 10s to respect Groq Rate Limits...")
            time.sleep(10)
        
        results["user_digests"] = user_count
        results["emails_sent"] = email_count
        results["success"] = True
        
        if run_id:
            repo.update_pipeline_run(run_id, status="SUCCESS", log_entry="Pipeline finished successfully.")

    except Exception as e:
        logger.error(f"Pipeline failed with error: {e}", exc_info=True)
        if run_id:
            repo.update_pipeline_run(run_id, status="FAILED", log_entry=f"Error: {str(e)}")
        results["error"] = str(e)

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    results["end_time"] = end_time.isoformat()
    results["duration_seconds"] = duration

    logger.info("\n" + "=" * 60)
    logger.info("Pipeline Summary")
    logger.info("=" * 60)
    logger.info(f"Duration: {duration:.1f} seconds")
    logger.info(f"Scraped: {results['scraping']}")
    logger.info(f"Processed: {results['processing']}")
    logger.info(f"Digests: {results['digests']}")
    logger.info(f"Users Processed: {results.get('user_digests', 0)}")
    logger.info(f"Emails Sent: {results.get('emails_sent', 0)}")
    logger.info("=" * 60)

    return results


if __name__ == "__main__":
    # Ensure tables exists
    from app.database.models import Base
    from app.database.connection import engine
    Base.metadata.create_all(engine)
    
    result = run_daily_pipeline(hours=72, top_n=10) # 72 hours for demo
    exit(0 if result.get("success", True) else 1)
