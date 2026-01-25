import json
from typing import Optional, Dict
from app.database.repository import Repository
from app.database.models import User

class UserService:
    def __init__(self):
        self.repo = Repository()

    def create_user(self, email: str, name: str, preferences: Dict, title: str = "", expertise_level: str = "Intermediate") -> User:
        # Convert preferences to JSON string
        pref_json = json.dumps(preferences)
        return self.repo.create_user(email, name, pref_json, title, expertise_level)

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.repo.get_user_by_email(email)

    def update_preferences(self, user_id: str, preferences: Dict) -> bool:
        pref_json = json.dumps(preferences)
        return self.repo.update_user_preferences(user_id, pref_json)

    def get_user_profile(self, user: User) -> Dict:
        """
        Reconstructs the full user profile dictionary expected by agents.
        """
        try:
            prefs = json.loads(user.preferences)
        except json.JSONDecodeError:
            prefs = {}
            
        return {
            "name": user.name,
            "title": user.title,
            "background": f"{user.title} - {user.expertise_level}", # Synthesized background
            "expertise_level": user.expertise_level,
            "interests": prefs.get("interests", []),
            "preferences": prefs.get("config", {})
        }
