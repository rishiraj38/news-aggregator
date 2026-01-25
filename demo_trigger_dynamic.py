import sys
import logging
from app.services.user_service import UserService
from app.daily_runner import run_daily_pipeline
from app.database.repository import Repository
from app.database.models import Recommendation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def trigger_demo(email: str):
    print(f"🚀 Starting FRESH Dynamic Demo for: {email}")
    
    repo = Repository()
    user_service = UserService()
    
    # 1. Ensure User Exists
    existing = user_service.get_user_by_email(email)
    if not existing:
        print("   Creating user...")
        user = user_service.create_user(
            email=email,
            name="Rishiraj (Fresh Test)",
            preferences={
                "interests": ["AI Agents", "LLM", "Robotics", "Generative AI"],
                "config": {"prefer_technical_depth": True}
            },
            title="Founder"
        )
    else:
        print(f"   ✓ User found: {existing.id}")
        user = existing

    # 2. CLEANUP: Delete old recommendations to force a fresh email
    print("   🧹 Cleaning up old recommendations to ensure full email generation...")
    repo.session.query(Recommendation).filter_by(user_id=user.id).delete()
    repo.session.commit()
    print("   ✓ Cleaned.")

    # 3. Run Pipeline (Lookback 7 days to catch 'Search' results)
    print("\n2. Running Pipeline (Hours=168)...")
    # Top N = 5 to ensure we get a nice list
    result = run_daily_pipeline(hours=168, top_n=5)
    
    if result.get('success'):
        print(f"\n✅ Demo Complete!")
        print(f"   - Email Sent: {result.get('emails_sent')}")
    else:
        print("\n❌ Pipeline Failed")
        print(result)

if __name__ == "__main__":
    trigger_demo("rishiraj438gt@gmail.com")
