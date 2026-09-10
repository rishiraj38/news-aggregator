"""Interleave curator picks across topic bundles when the subscriber enables multiple lanes."""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Set

from app.topic_packs.keywords import is_keyword_source
from app.topic_packs.registry import (
    ALLOWED_TOPIC_IDS,
    _topic_from_article_type,
)

# Share of the email reserved for stories matched by the subscriber's own
# keywords. Without a reserve, keyword hits land in the leftover "misc" lane and
# a subscriber who explicitly asked to track a term could go days without seeing
# one — the opposite of what they signed up for.
KEYWORD_RESERVE_RATIO = 0.4


def _split_keyword_hits(
    ordered: List[Any], digest_by_id: Dict[str, Dict[str, Any]], top_n: int
) -> tuple[List[Any], List[Any]]:
    """Pull the best keyword-matched items out, up to the reserved share."""
    reserve = max(1, int(round(top_n * KEYWORD_RESERVE_RATIO)))
    hits, rest = [], []
    for art in ordered:
        d = digest_by_id.get(art.digest_id) or {}
        if is_keyword_source(str(d.get("article_type") or "")) and len(hits) < reserve:
            hits.append(art)
        else:
            rest.append(art)
    return hits, rest


def diversify_curated_pick(
    ranked: List[Any],
    digest_by_id: Dict[str, Dict[str, Any]],
    user_topics: Set[str],
    top_n: int,
) -> List[Any]:
    """
    One digest per sweep from each subscribed lane (cycle repeats until top_n is filled).
    When a lane dries up earlier, leftover slots are filled via global curator ordering.

    Keyword matches get first claim on a reserved share of the slots, then the
    remaining slots are diversified across topic bundles as usual.
    """
    if top_n <= 0 or not ranked:
        return []

    all_ordered = sorted(ranked, key=lambda a: a.rank)
    keyword_hits, remainder = _split_keyword_hits(all_ordered, digest_by_id, top_n)
    slots_left = top_n - len(keyword_hits)
    if slots_left <= 0:
        return keyword_hits[:top_n]

    topics_sorted = sorted(t for t in user_topics if t in ALLOWED_TOPIC_IDS)
    if len(topics_sorted) < 2:
        return keyword_hits + remainder[:slots_left]

    top_n = slots_left
    ranked = remainder
    ordered = remainder
    buckets: Dict[str, deque[Any]] = {t: deque() for t in topics_sorted}
    misc: deque[Any] = deque()

    for art in ordered:
        d = digest_by_id.get(art.digest_id)
        at = (d or {}).get("article_type") or ""
        lane = _topic_from_article_type(str(at))
        if lane and lane in buckets:
            buckets[lane].append(art)
        else:
            misc.append(art)

    picked: List[Any] = []
    seen: Set[str] = set()
    stale_guard = max(top_n, len(ranked)) * len(topics_sorted) + len(misc) + 40
    rotations = stale_guard

    while len(picked) < top_n and rotations > 0:
        rotations -= 1
        progressed = False
        for lane in topics_sorted:
            if len(picked) >= top_n:
                break
            q = buckets[lane]
            while q and q[0].digest_id in seen:
                q.popleft()
            if q:
                x = q.popleft()
                picked.append(x)
                seen.add(x.digest_id)
                progressed = True
        if not progressed:
            while misc and misc[0].digest_id in seen:
                misc.popleft()
            if len(picked) >= top_n:
                break
            if misc:
                x = misc.popleft()
                if x.digest_id not in seen:
                    picked.append(x)
                    seen.add(x.digest_id)
                    progressed = True
            if not progressed:
                break

    if len(picked) < top_n:
        for art in ordered:
            if len(picked) >= top_n:
                break
            if art.digest_id not in seen:
                picked.append(art)
                seen.add(art.digest_id)

    return keyword_hits + picked[:top_n]
