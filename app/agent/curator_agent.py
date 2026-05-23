from typing import List
from pydantic import BaseModel, Field
from .base import BaseAgent


class RankedArticle(BaseModel):
    digest_id: str = Field(description="The ID of the digest (article_type:article_id)")
    relevance_score: float = Field(description="Relevance score from 0.0 to 10.0", ge=0.0, le=10.0)
    rank: int = Field(description="Rank position (1 = most relevant)", ge=1)
    reasoning: str = Field(description="Brief explanation of why this article is ranked here")


class RankedDigestList(BaseModel):
    articles: List[RankedArticle] = Field(description="List of ranked articles")


CURATOR_PROMPT = """You are an expert news curator for busy professionals across technology, politics, and sports domains.

Digests arrive from multiple publishers (labs, transcripts, curated RSS bundles). Rank them by how well each story earns the subscriber's scarce attention—not by hype.

Ranking criteria (combined):
• Fit to the subscriber's topic bundles plus keyword cues below
• Source credibility and specificity (named facts > vague punditry when tie-breaking)
• Actionability and depth appropriate to stated expertise level
• Novelty versus obvious rehash headlines

Scores 9–10: must-read aligned with bundles or keywords • 7–8.9 strong match • 5–6.9 useful context • Below 5: diminishing returns.

Produce a strict total order (unique ranks 1 … N).
"""

USER_PROFILE_SECTION = """

User Profile:
Name: {name}
Background: {background}
Expertise Level: {expertise_level}

Subscriber topic bundles:
{topics}

Keywords & fine-grained cues (prioritize overlap when breaking ties):
{interests}

Preferences / profile notes:
{pref_text}
"""


class CuratorAgent(BaseAgent):
    def __init__(self, user_profile: dict):
        super().__init__("llama-3.3-70b-versatile")
        self.user_profile = user_profile
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        interests = "\n".join(f"- {interest}" for interest in self.user_profile["interests"])
        preferences = self.user_profile["preferences"]
        pref_text = "\n".join(f"- {k}: {v}" for k, v in preferences.items())
        topics = "\n".join(
            f"- {lbl}" for lbl in self.user_profile.get("topic_labels") or []
        )

        return (
            CURATOR_PROMPT
            + USER_PROFILE_SECTION.format(
                name=self.user_profile["name"],
                background=self.user_profile["background"],
                expertise_level=self.user_profile["expertise_level"],
                topics=topics or "- General briefing",
                interests=interests or "- Broad reader",
                pref_text=pref_text or "(none)",
            )
        )

    def rank_digests(self, digests: List[dict]) -> List[RankedArticle]:
        if not digests:
            return []
        
        digest_list = "\n\n".join([
            f"ID: {d['id']}\nTitle: {d['title']}\nSummary: {d['summary']}\nType: {d['article_type']}"
            for d in digests
        ])
        
        user_prompt = f"""Rank these {len(digests)} news digests for this subscriber profile:

{digest_list}

Provide a relevance score (0.0-10.0) and rank (1-{len(digests)}) for each item.

CRITICAL rules:
• For every object, set `"digest_id"` to the EXACT string shown on the `ID:` line for that digest (character-for-character, including colons).
• Include every digest exactly once — do not invent, merge, shorten, or reformat ids.
• In the `"articles"` array, list entries in ascending `"rank"` (rank 1 first, then rank 2, …).

Output strictly valid JSON matching this schema:
{{
  "articles": [
    {{
      "digest_id": "string",
      "relevance_score": float,
      "rank": int,
      "reasoning": "string"
    }}
  ]
}}"""

        try:
            response = self.get_completion(
                messages=[
                    {"role": "system", "content": self.system_prompt + "\n\nYou must output valid JSON."},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            ranked_list = RankedDigestList.model_validate_json(content)
            return ranked_list.articles
        except Exception as e:
            print(f"Error ranking digests: {e}")
            return []
