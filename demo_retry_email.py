import logging
import sys
from datetime import datetime, timezone
from app.database.repository import Repository
from app.services.user_service import UserService
from app.agent.curator_agent import CuratorAgent
from app.services.process_email import send_personalized_email
from app.profiles.user_profile import USER_PROFILE

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def retry_email_only(email: str):
    print(f"🚀 Starting CACHED Email Retry for: {email}")
    
    repo = Repository()
    user_service = UserService()
    
    # 1. Get User
    user = user_service.get_user_by_email(email)
    if not user:
        print("❌ User not found.")
        return

    # 2. Get Cached Digests (Last 7 days)
    print("   📦 Fetching cached digests from DB...")
    digests = repo.get_recent_digests(hours=168, exclude_sent=False)
    if not digests:
        print("❌ No digests found in cache. Cannot send email.")
        return
    print(f"   ✓ Found {len(digests)} cached items.")

    # 3. Rank Content
    print("   🧠 Ranking content for user...")
    # Map dictionary back to objects/dicts expected by Curator
    # Curator expects list of dicts or objects with 'id', 'summary', etc.
    # repo.get_recent_digests returns list of dicts.
    
    curator = CuratorAgent(USER_PROFILE) # Ideally use user specific profile if available
    ranked_articles = curator.rank_digests(digests)
    
    top_n = 5
    top_articles = ranked_articles[:top_n]
    
    # 4. Save Recommendations (Force "New" timestamp)
    print("   💾 Saving recommendations...")
    final_articles_to_send = []
    
    for article in top_articles:
        # We force create a NEW recommendation to ensure it's picked up
        # By adding a random uuid or just relying on the fact that we are running this script manually
        # to test the email function.
        
        # ACTUALLY: The email function takes the list of articles directly!
        # We don't strictly need to save to DB to send the email in this manual script.
        # But let's save for record keeping.
        
        rec = repo.create_recommendation(
            user_id=user.id,
            digest_id=article.digest_id,
            relevance_score=article.relevance_score,
            rank=article.rank,
            reasoning=article.reasoning,
            # Explicitly set correct UTC time
        )
        final_articles_to_send.append(article)

    # 5. Send Email
    print(f"   📧 Sending email with {len(final_articles_to_send)} articles...")
    try:
        # We need to construct a user profile dict for the email agent
        # user.preferences is a JSON string, need to parse if needed, 
        # but process_email might handle it or just use generic profile.
        # Let's use the standard flow.
        
        import json
        try:
            prefs = json.loads(user.preferences)
        except:
            prefs = {}
            
        profile_dict = {
            "name": user.name,
            "interests": prefs.get("interests", []),
            "technical_level": user.expertise_level
        }
        
        result = send_personalized_email(user, profile_dict, final_articles_to_send)
        
        if result["success"]:
             print(f"\n✅ Email Sent Successfully to {user.email}!")
             print(f"   - Articles: {result['articles_count']}")
        else:
             print(f"\n❌ Email Failed: {result.get('error')}")

    except Exception as e:
        print(f"\n❌ Critical Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    retry_email_only("rishiraj438gt@gmail.com")
