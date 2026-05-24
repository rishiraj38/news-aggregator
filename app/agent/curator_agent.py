import logging
import os
import time
from typing import List

from pydantic import BaseModel, Field

from .base import BaseAgent

logger = logging.getLogger(__name__)

# Groq on-demand tier can reject a single request whose token estimate exceeds TPM (~12k).
# Chunking + truncation keeps each curator call small; cross-chunk scores merged by sorting.
CURATOR_CHUNK_SIZE = max(1, int(os.getenv("CURATOR_CHUNK_SIZE", "10")))
CURATOR_DIGEST_SUMMARY_CHARS = max(80, int(os.getenv("CURATOR_DIGEST_SUMMARY_CHARS", "420")))
GROQ_CHUNK_SLEEP_SECONDS = float(os.getenv("GROQ_CHUNK_SLEEP_SECONDS", "10") or 0)


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

Produce a strict total order (unique ranks 1 … N within this batch).
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


def _clip_summary(text: str, limit: int) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1].rsplit(" ", 1)[0] + "…"


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

    def _format_digest_block(self, d: dict) -> str:
        summ = _clip_summary(str(d.get("summary") or ""), CURATOR_DIGEST_SUMMARY_CHARS)
        return (
            f"ID: {d['id']}\n"
            f"Title: {d.get('title') or '(untitled)'}\n"
            f"Summary: {summ}\n"
            f"Type: {d.get('article_type') or ''}"
        )

    def _rank_digest_chunk(self, chunk: List[dict]) -> List[RankedArticle]:
        """Single Groq call for up to CURATOR_CHUNK_SIZE digests."""
        digest_list = "\n\n".join([self._format_digest_block(d) for d in chunk])
        n = len(chunk)

        user_prompt = f"""Rank these {n} news digests for this subscriber profile:

{digest_list}

Provide a relevance score (0.0-10.0) and rank (1-{n}) for each item.

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

        response = self.get_completion(
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt + "\n\nYou must output valid JSON.",
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        ranked_list = RankedDigestList.model_validate_json(content)
        return ranked_list.articles

    def rank_digests(self, digests: List[dict]) -> List[RankedArticle]:
        if not digests:
            return []

        order_ix = {d["id"]: i for i, d in enumerate(digests)}
        chunks: List[List[dict]] = [
            digests[i : i + CURATOR_CHUNK_SIZE]
            for i in range(0, len(digests), CURATOR_CHUNK_SIZE)
        ]

        if len(chunks) > 1:
            logger.info(
                "Curator chunking: %s digests → %s Groq requests (≤%s items each)",
                len(digests),
                len(chunks),
                CURATOR_CHUNK_SIZE,
            )

        per_chunk: List[RankedArticle] = []
        for ci, chunk in enumerate(chunks):
            try:
                part = self._rank_digest_chunk(chunk)
                per_chunk.extend(self._finalize_chunk_results(part, chunk))
            except Exception as e:
                logger.error(
                    "Curator chunk %s/%s failed: %s", ci + 1, len(chunks), e, exc_info=True
                )
                return []

            if ci + 1 < len(chunks) and GROQ_CHUNK_SLEEP_SECONDS > 0:
                logger.info(
                    "Sleeping %.1fs between curator chunks (Groq TPM / RPM pacing)",
                    GROQ_CHUNK_SLEEP_SECONDS,
                )
                time.sleep(GROQ_CHUNK_SLEEP_SECONDS)

        merged = sorted(
            per_chunk,
            key=lambda a: (-float(a.relevance_score), order_ix[a.digest_id]),
        )
        return [a.model_copy(update={"rank": i + 1}) for i, a in enumerate(merged)]

    @staticmethod
    def _finalize_chunk_results(
        articles: List[RankedArticle], chunk: List[dict]
    ) -> List[RankedArticle]:
        """Ensure each digest appears once before global merge."""
        expected = {d["id"] for d in chunk}
        by_id = {a.digest_id: a for a in articles}
        for did in expected - by_id.keys():
            logger.warning(
                "Curator omitted digest_id=%s — applying neutral fallback score", did
            )
            by_id[did] = RankedArticle(
                digest_id=did,
                relevance_score=5.0,
                rank=999,
                reasoning="Included automatically — model omitted this item from JSON.",
            )
        # Drop extra IDs hallucinated outside this chunk if any (should not happen)
        out = [by_id[did] for did in [d["id"] for d in chunk] if did in by_id]
        return out
