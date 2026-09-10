import logging
import os
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / "app" / ".env")
load_dotenv(_REPO_ROOT / ".env")


from app.runner import run_scrapers
from app.services.process_anthropic import process_anthropic_markdown
from app.services.process_youtube import process_youtube_transcripts
from app.services.process_digest import process_digests
from app.services.process_email import send_digest_email
from app.database.models import Base
from app.database.connection import engine
from app.database.repository import Repository
from app.topic_packs.registry import digest_matches_topics


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
            from app.database.schema_migrations import ensure_image_url_columns

            ensure_image_url_columns()
            log_progress("✓ Schema migrations applied (image_url columns)")
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
                k: len(v) if isinstance(v, list) else 0 for k, v in scraping_results.items()
            }
            logger.info("✓ Scrape summary: %s", ", ".join(f"{k}={results['scraping'][k]}" for k in sorted(results["scraping"].keys())))
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
        digest_batch_limit = int(os.getenv("DIGEST_BATCH_LIMIT", "50") or 50)
        logger.info("Digest batch limit: %s (set DIGEST_BATCH_LIMIT to override)", digest_batch_limit)
        digest_result = process_digests(limit=digest_batch_limit)
        results["digests"] = digest_result
        logger.info(
            f"✓ Created {digest_result['processed']} digests "
            f"({digest_result['failed']} failed out of {digest_result['total']} total)"
        )

        log_progress("\n[5/5] Generating personalized digests for users...")
        
        # repo already initialized above
        # Snapshots, not ORM rows: a mid-run SSL reconnect swaps the session and
        # detaches live User objects, which previously made every downstream
        # `user.email` raise and dropped the whole send to zero emails.
        active_users = repo.get_active_user_snapshots()
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
            # Fall through instead of returning early, so the run still records
            # its duration and prints the summary block.
            logger.warning(
                "No digests available to rank (window=%dh). Nothing to personalize.",
                hours,
            )
            active_users = []

        user_count = 0
        email_count = 0
        digest_email_test_only = os.getenv("DIGEST_EMAIL_TEST_ONLY", "").strip().lower()
        if digest_email_test_only:
            log_progress(f"⚠ DIGEST_EMAIL_TEST_ONLY set — personalization runs only for {digest_email_test_only}")

        for user in active_users:
            user_email = user.email
            user_name = user.name
            user_id = user.id
            user_role = user.role
            ranked_this_user = False

            try:
                if digest_email_test_only and user_email.strip().lower() != digest_email_test_only:
                    continue
                # --- Trial Expiration Check (27 Days) ---
                if user_role != "admin": # Admins are immune
                    # Ensure timezone awareness compatibility
                    created_at = user.created_at
                    
                    if created_at is None:
                        logger.warning(f"User {user_email} has NULL created_at. defaulting to 0 days active.")
                        days_active = 0
                    else:
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)
                        days_active = (start_time - created_at).days
                    
                    trial_limit = 27
                    days_left = trial_limit - days_active
                    
                    if days_left == 2 and str(user.trial_warning_2_sent).lower() != "true":
                        from app.services.process_email import send_trial_warning_email
                        logger.info(f"User {user_email} has 2 days left on trial. Sending warning email.")
                        if send_trial_warning_email(user, days_left):
                            user.trial_warning_2_sent = "true"
                            repo.set_user_flag(user_id, "trial_warning_2_sent")

                    elif days_left == 1 and str(user.trial_warning_1_sent).lower() != "true":
                        from app.services.process_email import send_trial_warning_email
                        logger.info(f"User {user_email} has 1 day left on trial. Sending warning email.")
                        if send_trial_warning_email(user, days_left):
                            user.trial_warning_1_sent = "true"
                            repo.set_user_flag(user_id, "trial_warning_1_sent")

                    # STRICT 27-day limit
                    if days_active >= trial_limit:
                         if str(user.trial_expired_sent).lower() != "true":
                             from app.services.process_email import send_trial_expired_email
                             logger.info(f"User {user_email} trial expired. Sending expiration email.")
                             if send_trial_expired_email(user):
                                 user.trial_expired_sent = "true"
                                 repo.set_user_flag(user_id, "trial_expired_sent")

                         msg = f"User {user_email} trial expired ({days_active} days >= {trial_limit}). Marking expired & skipping."
                         logger.info(msg)
                         log_progress(msg)

                         # Update DB status
                         repo.update_user_status(user_id, "expired")
                         continue
                # ----------------------------------------

                user_count += 1
                if run_id:
                     repo.update_pipeline_run(run_id, users_processed=user_count)
                
                msg = f"--- Processing for user: {user_name} ({user_email}) ---"
                logger.info(msg)
                log_progress(msg)

                # 0. Check for New Admin Promotion - ROBUST CHECK
                # Handle "True", "true", True (bool), etc.
                admin_flag = str(user.admin_welcome_sent).lower()

                if user_role == "admin" and admin_flag != "true":
                    from app.services.process_email import send_admin_welcome_email
                    logger.info(f"User {user_email} is a new admin. Sending welcome email...")
                    if send_admin_welcome_email(user):
                        repo.update_user_admin_welcome(user_id)
                        user.admin_welcome_sent = "true"
                        logger.info("✓ Admin welcome email sent and flagged.")
                    else:
                        logger.error("✗ Failed to send admin welcome email.")
                user_profile = user_service.get_user_profile(user)
                
                # 1.5 Filter out already seen digests
                seen_digest_ids = set(repo.get_user_recommended_digest_ids(user_id))
                logger.info(f"User {user_name} has {len(seen_digest_ids)} previously recommended digests")
                logger.debug(f"Seen IDs sample: {list(seen_digest_ids)[:5] if seen_digest_ids else []}")
                
                unseen_digests = [d for d in recent_digests if d['id'] not in seen_digest_ids]
                if not unseen_digests:
                    msg = f"No new digests for {user_name} (All {len(recent_digests)} recent items already recommended). Skipping."
                    logger.info(msg)
                    log_progress(msg)
                    time.sleep(0.5)  # Small sleep to avoid instant loops looking like bugs
                    continue

                topic_set = set(user_profile["topics"])
                keyword_keys = user_profile.get("keyword_source_keys") or frozenset()
                if keyword_keys:
                    logger.info(
                        "Tracking %d keyword(s) for %s: %s",
                        len(keyword_keys), user_name,
                        ", ".join(user_profile.get("keywords") or []),
                    )
                before_topics = len(unseen_digests)
                unseen_digests = [
                    d
                    for d in unseen_digests
                    if digest_matches_topics(d["article_type"], topic_set, keyword_keys)
                ]
                if before_topics != len(unseen_digests):
                    log_progress(
                        f"Topic bundles {sorted(topic_set)} → "
                        f"{len(unseen_digests)} / {before_topics} new digests after filter"
                    )

                if not unseen_digests:
                    msg = (
                        f"No digest candidates matched topic bundles {sorted(topic_set)} for {user_name} "
                        "(new items existed but none in your bundles — expand topics or wait for matching coverage)."
                    )
                    logger.info(msg)
                    log_progress(msg)
                    time.sleep(0.5)
                    continue
                
                # Bound the per-user Groq spend. recent_digests is already
                # newest-first, so this keeps the freshest candidates.
                max_candidates = int(os.getenv("CURATOR_MAX_CANDIDATES", "60") or 60)
                if max_candidates > 0 and len(unseen_digests) > max_candidates:
                    # Keyword matches are the whole point of a subscriber's opt-in,
                    # so they survive the trim ahead of generic bundle items.
                    from app.topic_packs.keywords import is_keyword_source

                    kw_hits = [d for d in unseen_digests if is_keyword_source(d["article_type"])]
                    others = [d for d in unseen_digests if not is_keyword_source(d["article_type"])]
                    trimmed = (kw_hits + others)[:max_candidates]
                    logger.info(
                        "Trimming ranking pool for %s: %d → %d (%d keyword hit(s) kept)",
                        user_name, len(unseen_digests), len(trimmed), len(kw_hits),
                    )
                    unseen_digests = trimmed

                logger.info(f"Ranking {len(unseen_digests)} new digests for {user_name} (out of {len(recent_digests)} total recent)...")
                ranked_this_user = True

                # 2. Rank Content
                curator = CuratorAgent(user_profile)
                digest_by_id = {d["id"]: d for d in unseen_digests}
                ranked_articles = curator.rank_digests(unseen_digests)
                
                if not ranked_articles:
                    msg = f"No relevant articles found for {user_name} in new batch. Skipping."
                    logger.info(msg)
                    log_progress(msg)
                    continue

                from app.topic_packs.diversify import diversify_curated_pick

                diversified = diversify_curated_pick(
                    ranked_articles,
                    digest_by_id,
                    topic_set,
                    top_n,
                )
                ranked_ordered = []
                for idx, article in enumerate(diversified, start=1):
                    ranked_ordered.append(article.model_copy(update={"rank": idx}))

                # 3. Save Recommendations
                top_articles = ranked_ordered
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
                        user_id=user_id,
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
                
                logger.info(f"Saved {len(new_recommendations)} NEW recommendations for {user_name}")

                if not final_articles_to_send:
                     msg = f"No new recommendations for {user_name}. Skipping email."
                     logger.info(msg)
                     log_progress(msg)
                     continue

                # 4. Send Email — editorial upgrade on very first curated send (Instagram + hero in digest)
                first_helix_digest = len(seen_digest_ids) == 0
                email_result = send_personalized_email(
                    user,
                    user_profile,
                    final_articles_to_send,
                    is_first_delivery=first_helix_digest,
                )
                
                if email_result["success"]:
                    email_count += 1
                    log_progress(f"✓ Email sent to {user_email}")
                else:
                    logger.error(f"✗ Failed to send email to {user_email}: {email_result.get('error')}")

            except Exception as e:
                logger.error(f"Error processing for user {user_email}: {e}")
                # Roll back the broken transaction so the session can be reused
                try:
                    repo.session.rollback()
                except Exception as rb_err:
                    logger.warning(f"Rollback also failed: {rb_err}")
            
            # Rate Limit Protection (Groq has RPM limits). Only pay this when the
            # user actually reached the API — skipped users used to cost 10s each.
            if ranked_this_user:
                logger.info("Sleeping 10s to respect Groq Rate Limits...")
                time.sleep(10)
        
        results["user_digests"] = user_count
        results["emails_sent"] = email_count
        results["success"] = True

        if run_id:
            repo.update_pipeline_run(run_id, status="SUCCESS", log_entry="Pipeline finished successfully.")

    except Exception as e:
        logger.error(f"Pipeline failed with error: {e}", exc_info=True)
        # Roll back any broken transaction before attempting the status update
        try:
            repo.session.rollback()
        except Exception:
            pass
        if run_id:
            try:
                repo.update_pipeline_run(run_id, status="FAILED", log_entry=f"Error: {str(e)}")
            except Exception as update_err:
                logger.error(f"Could not update pipeline run status: {update_err}")
        results["error"] = str(e)

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    results["end_time"] = end_time.isoformat()
    results["duration_seconds"] = duration

    # Tell someone when the run is broken. Silence used to look exactly like
    # success, which is how weeks of zero-email runs went unnoticed.
    from app.services.alerts import send_pipeline_alert

    send_pipeline_alert(results)

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


def _env_flag(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def _write_ci_summary(result: dict) -> None:
    """Emit a GitHub Actions job summary + annotations.

    Without this the job stayed green while scraping nothing and emailing
    nobody, which is exactly how the zero-email runs went unnoticed.
    """
    scraped = result.get("scraping") or {}
    scraped_total = sum(v for v in scraped.values() if isinstance(v, int))
    emails = result.get("emails_sent", 0)
    users = result.get("user_digests", 0)

    if scraped_total == 0:
        print("::warning title=No articles scraped::Every source returned 0 items.")
    if users > 0 and emails == 0:
        print(
            f"::warning title=No emails sent::{users} user(s) processed but 0 emails "
            "were delivered."
        )

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "## Helix daily digest",
        "",
        f"- **Duration**: {result.get('duration_seconds', 0):.0f}s",
        f"- **Articles scraped**: {scraped_total}",
        f"- **Digests created**: {(result.get('digests') or {}).get('processed', 0)}",
        f"- **Users processed**: {users}",
        f"- **Emails sent**: {emails}",
        "",
        "### Per-source scrape counts",
        "",
        "| Source | Items |",
        "| --- | --- |",
    ]
    for key in sorted(scraped):
        lines.append(f"| {key} | {scraped[key]} |")
    if result.get("error"):
        lines += ["", f"### Error", "", f"```\n{result['error']}\n```"]
    try:
        with open(summary_path, "a") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not write CI summary: %s", exc)


if __name__ == "__main__":
    # Ensure tables exists
    from app.database.models import Base
    from app.database.connection import engine
    from app.database.schema_migrations import ensure_image_url_columns

    Base.metadata.create_all(engine)
    ensure_image_url_columns()

    hours = int(os.getenv("PIPELINE_HOURS", "72") or 72)
    top_n = int(os.getenv("PIPELINE_TOP_N", "10") or 10)
    force_scrape = _env_flag("PIPELINE_FORCE_SCRAPE")

    result = run_daily_pipeline(hours=hours, top_n=top_n, force_scrape=force_scrape)
    _write_ci_summary(result)

    ok = bool(result.get("success", False))

    # Surface the silent-failure mode: a run that reaches subscribers but sends
    # nothing is a bug, not a quiet day. Set FAIL_ON_ZERO_EMAILS=false to opt out.
    if ok and _env_flag("FAIL_ON_ZERO_EMAILS", "true"):
        if result.get("user_digests", 0) > 0 and result.get("emails_sent", 0) == 0:
            logger.error(
                "Pipeline processed %s user(s) but sent 0 emails — failing the run.",
                result.get("user_digests", 0),
            )
            ok = False

    exit(0 if ok else 1)
