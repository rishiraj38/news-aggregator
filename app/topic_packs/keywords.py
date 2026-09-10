"""Per-subscriber keyword lanes.

Topic packs are a fixed, shared set of bundles. Keywords are the opposite: each
subscriber supplies their own terms ("agentic RAG", "Nvidia earnings") and gets
stories fetched specifically for them.

A keyword becomes an ingest source key of the form ``kw_<slug>_<hash>``, which
is stored in ``general_rss_articles.source`` and therefore ends up as the
digest's ``article_type``. Personalization then routes a ``kw_*`` digest only to
subscribers who actually asked for that term — see
:func:`app.topic_packs.registry.digest_matches_topics`.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, FrozenSet, Iterable, List, Mapping

KEYWORD_SOURCE_PREFIX = "kw_"

# Bounds: keywords drive live network calls per term per run, so both the
# per-user count and the global distinct count are capped by callers.
MAX_KEYWORDS_PER_USER = 10
MIN_KEYWORD_CHARS = 2
MAX_KEYWORD_CHARS = 60

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")


def normalize_keyword(raw: Any) -> str | None:
    """Canonical display form: trimmed, collapsed whitespace, lowercased.

    Returns ``None`` for anything too short, too long, or with no usable
    alphanumeric content, so junk never becomes an ingest source.
    """
    if not isinstance(raw, str):
        return None
    cleaned = _WS.sub(" ", raw.strip().lower())
    if len(cleaned) < MIN_KEYWORD_CHARS or len(cleaned) > MAX_KEYWORD_CHARS:
        return None
    if not _NON_ALNUM.sub("", cleaned):
        return None
    return cleaned


def keyword_source_key(keyword: str) -> str:
    """Stable ingest source key for a normalized keyword.

    The slug is for human readability in logs and DB rows; the hash suffix
    keeps terms that flatten to the same slug ("c++" and "c#") distinct.
    """
    slug = _NON_ALNUM.sub("_", keyword).strip("_")[:40] or "term"
    digest = hashlib.blake2s(keyword.encode("utf-8"), digest_size=4).hexdigest()[:6]
    return f"{KEYWORD_SOURCE_PREFIX}{slug}_{digest}"


def is_keyword_source(article_type: str) -> bool:
    return str(article_type or "").startswith(KEYWORD_SOURCE_PREFIX)


def normalize_keyword_list(raw: Any, *, limit: int = MAX_KEYWORDS_PER_USER) -> List[str]:
    """Clean, de-duplicate and cap a user-supplied keyword list."""
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, Iterable):
        return []

    out: List[str] = []
    for item in raw:
        kw = normalize_keyword(item)
        if kw and kw not in out:
            out.append(kw)
        if len(out) >= limit:
            break
    return out


def user_keywords(prefs: Mapping[str, Any]) -> List[str]:
    """Keywords a subscriber explicitly asked to track.

    Only ``preferences['keywords']`` counts. ``interests`` stays a soft signal
    for curator ranking and topic derivation — promoting it here would spawn an
    ingest lane per default interest for every user.
    """
    if not isinstance(prefs, Mapping):
        return []
    return normalize_keyword_list(prefs.get("keywords"))


def user_keyword_source_keys(prefs: Mapping[str, Any]) -> FrozenSet[str]:
    return frozenset(keyword_source_key(kw) for kw in user_keywords(prefs))
