import json
from typing import Any, Mapping, Optional, Dict
from app.database.repository import Repository
from app.database.models import User
from app.topic_packs.registry import TOPIC_LABELS, normalize_user_topics

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

    def get_prefs_dict(self, user: User) -> Dict[str, Any]:
        try:
            return dict(json.loads(user.preferences))
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}

    def get_user_profile(self, user: User) -> Dict:
        """
        Reconstructs the full user profile dictionary expected by agents.
        """
        prefs: Mapping[str, Any] = self.get_prefs_dict(user)

        interests = prefs.get("interests") or prefs.get("keywords") or []
        if not isinstance(interests, list):
            interests = [str(interests)] if interests else []

        topics_norm = normalize_user_topics(prefs)
        topic_labels = [TOPIC_LABELS[t] for t in topics_norm if t in TOPIC_LABELS]

        return {
            "name": user.name,
            "title": user.title,
            "background": f"{user.title} - {user.expertise_level}", # Synthesized background
            "expertise_level": user.expertise_level,
            "interests": interests,
            "topics": topics_norm,
            "topic_labels": topic_labels,
            "preferences": prefs.get("config", {})
            if isinstance(prefs.get("config"), dict)
            else {},
        }
