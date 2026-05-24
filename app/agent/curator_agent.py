import logging
import os
import time
from typing import List, Sequence

from openai import APIStatusError
from pydantic import BaseModel, Field
from tenacity import RetryError

from .base import BaseAgent

logger = logging.getLogger(__name__)

# Groq on-demand tier TPM can reject a single giant completion; tune via env / split below.
CURATOR_CHUNK_SIZE = max(1, int(os.getenv("CURATOR_CHUNK_SIZE", "6")))
CURATOR_DIGEST_SUMMARY_CHARS = max(80, int(os.getenv("CURATOR_DIGEST_SUMMARY_CHARS", "260")))
CURATOR_DIGEST_TITLE_CHARS = max(80, int(os.getenv("CURATOR_DIGEST_TITLE_CHARS", "200")))
GROQ_CHUNK_SLEEP_SECONDS = float(os.getenv("GROQ_CHUNK_SLEEP_SECONDS", "10") or 0)

CURATOR_MAX_INTEREST_LINES = max(10, int(os.getenv("CURATOR_MAX_INTEREST_LINES", "40")))
CURATOR_INTEREST_LINE_CHARS = max(40, int(os.getenv("CURATOR_INTEREST_LINE_CHARS", "260")))
CURATOR_PREF_TEXT_CHARS = max(200, int(os.getenv("CURATOR_PREF_TEXT_CHARS", "2800")))
CURATOR_BACKGROUND_CHARS = max(40, int(os.getenv("CURATOR_BACKGROUND_CHARS", "520")))


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


def _clip(text: str, limit: int) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 1].rsplit(" ", 1)[0] + "…"


def _clip_words(text: str, limit: int) -> str:
    return _clip(text, limit)


def _groq_prompt_tpm_reject(exc: BaseException) -> bool:
    raw = str(exc).lower()
    if isinstance(exc, APIStatusError) and getattr(exc, "status_code", None) == 413:
        return True
    if "reduce your message size" in raw:
        return True
    if "tokens per minute" in raw or " tpm " in raw:
        return True
    if "requested" in raw and ("12000" in raw or "tpm" in raw):
        return True
    return False


class CuratorAgent(BaseAgent):
    def __init__(self, user_profile: dict):
        super().__init__("llama-3.3-70b-versatile")
        self.user_profile = user_profile
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        raw_interests = self.user_profile.get("interests") or []
        if not isinstance(raw_interests, list):
            raw_interests = [str(raw_interests)] if raw_interests else []

        clipped_lines = []
        for line in raw_interests[:CURATOR_MAX_INTEREST_LINES]:
            clipped_lines.append(
                "- " + _clip_words(str(line), CURATOR_INTEREST_LINE_CHARS)
            )
        if len(raw_interests) > CURATOR_MAX_INTEREST_LINES:
            clipped_lines.append(
                f"- … (+{len(raw_interests) - CURATOR_MAX_INTEREST_LINES} more cues omitted)"
            )
        interests = "\n".join(clipped_lines) if clipped_lines else ""

        preferences = self.user_profile.get("preferences") or {}
        pref_text = ""
        if isinstance(preferences, dict):
            pref_text = "\n".join(f"- {k}: {v}" for k, v in preferences.items())

        pref_text = _clip_words(pref_text, CURATOR_PREF_TEXT_CHARS) if pref_text else ""

        topics = "\n".join(
            f"- {lbl}" for lbl in self.user_profile.get("topic_labels") or []
        )

        name = _clip_words(str(self.user_profile.get("name") or ""), 120)
        background = _clip_words(
            str(self.user_profile.get("background") or ""), CURATOR_BACKGROUND_CHARS
        )

        return (
            CURATOR_PROMPT
            + USER_PROFILE_SECTION.format(
                name=name or "Subscriber",
                background=background or "—",
                expertise_level=str(self.user_profile.get("expertise_level") or ""),
                topics=topics or "- General briefing",
                interests=interests or "- Broad reader",
                pref_text=pref_text or "(none)",
            )
        )

    def _format_digest_block(self, d: dict) -> str:
        summ = _clip_words(str(d.get("summary") or ""), CURATOR_DIGEST_SUMMARY_CHARS)
        tit = _clip_words(str(d.get("title") or "(untitled)"), CURATOR_DIGEST_TITLE_CHARS)
        return (
            f"ID: {d['id']}\nTitle: {tit}\nSummary: {summ}\nType: {d.get('article_type') or ''}"
        )

    def _llm_rank_list(self, chunk: List[dict]) -> List[RankedArticle]:
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
        ranked_list = RankedDigestList.model_validate_json(content or "{}")
        return ranked_list.articles

    def _rank_digest_recursive(self, chunk: List[dict]) -> List[RankedArticle]:
        """Groq ranks `chunk`; on TPM/size rejection split in half."""
        try:
            return self._llm_rank_list(chunk)
        except APIStatusError as e:
            if not _groq_prompt_tpm_reject(e) or len(chunk) <= 1:
                raise
            mid = len(chunk) // 2 or 1
            logger.warning(
                "Groq TPM / oversize for batch of %s digests → split %s | %s: %s",
                len(chunk),
                mid,
                len(chunk) - mid,
                str(e).replace("\n", " ")[:220],
            )
            idle = (
                float(GROQ_CHUNK_SLEEP_SECONDS) / 2.0
                if GROQ_CHUNK_SLEEP_SECONDS > 0
                else 2.0
            )
            time.sleep(min(30.0, idle))
            left = self._rank_digest_recursive(chunk[:mid])
            right = self._rank_digest_recursive(chunk[mid:])
            return [*left, *right]
        except RetryError as re:
            le = None
            try:
                att = getattr(re, "last_attempt", None)
                le = att.exception() if att is not None else None  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                le = None
            if le and _groq_prompt_tpm_reject(le) and len(chunk) > 1:
                mid = len(chunk) // 2 or 1
                logger.warning("Curator TPM pattern inside RetryError; splitting batch.")
                idle = (
                    float(GROQ_CHUNK_SLEEP_SECONDS) / 2.0
                    if GROQ_CHUNK_SLEEP_SECONDS > 0
                    else 2.0
                )
                time.sleep(min(30.0, idle))
                left = self._rank_digest_recursive(chunk[:mid])
                right = self._rank_digest_recursive(chunk[mid:])
                return [*left, *right]
            raise re
        except Exception as e:
            if _groq_prompt_tpm_reject(e) and len(chunk) > 1:
                mid = len(chunk) // 2 or 1
                logger.warning("Curator split after non-typed TPM error: %s", type(e).__name__)
                left = self._rank_digest_recursive(chunk[:mid])
                right = self._rank_digest_recursive(chunk[mid:])
                return [*left, *right]
            raise

    def rank_digests(self, digests: List[dict]) -> List[RankedArticle]:
        if not digests:
            return []

        order_ix = {d["id"]: i for i, d in enumerate(digests)}
        chunks: List[List[dict]] = [
            digests[i : i + CURATOR_CHUNK_SIZE]
            for i in range(0, len(digests), CURATOR_CHUNK_SIZE)
        ]

        if len(chunks) > 1 or len(digests) > CURATOR_CHUNK_SIZE:
            logger.info(
                "Curator batches: %s digests → %s primary Groq batches (≤%s items)",
                len(digests),
                len(chunks),
                CURATOR_CHUNK_SIZE,
            )

        per_piece: List[RankedArticle] = []
        for ci, chunk in enumerate(chunks):
            try:
                raw = self._rank_digest_recursive(chunk)
                per_piece.extend(self._finalize_chunk_results(raw, chunk))
            except Exception as e:
                logger.error(
                    "Curator chunk %s/%s failed: %s", ci + 1, len(chunks), e, exc_info=True
                )
                return []

            if ci + 1 < len(chunks) and GROQ_CHUNK_SLEEP_SECONDS > 0:
                logger.info(
                    "Sleeping %.1fs between curator batches",
                    GROQ_CHUNK_SLEEP_SECONDS,
                )
                time.sleep(GROQ_CHUNK_SLEEP_SECONDS)

        merged = sorted(
            per_piece,
            key=lambda a: (-float(a.relevance_score), order_ix[a.digest_id]),
        )
        return [a.model_copy(update={"rank": i + 1}) for i, a in enumerate(merged)]

    @staticmethod
    def _finalize_chunk_results(
        articles: Sequence[RankedArticle], chunk: List[dict]
    ) -> List[RankedArticle]:
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
        return [by_id[did] for did in [d["id"] for d in chunk] if did in by_id]
