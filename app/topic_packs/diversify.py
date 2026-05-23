"""Interleave curator picks across topic bundles when the subscriber enables multiple lanes."""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Set

from app.topic_packs.registry import (
    ALLOWED_TOPIC_IDS,
    _topic_from_article_type,
)


def diversify_curated_pick(
    ranked: List[Any],
    digest_by_id: Dict[str, Dict[str, Any]],
    user_topics: Set[str],
    top_n: int,
) -> List[Any]:
    """
    One digest per sweep from each subscribed lane (cycle repeats until top_n is filled).
    When a lane dries up earlier, leftover slots are filled via global curator ordering.
    """
    if top_n <= 0 or not ranked:
        return []
    topics_sorted = sorted(t for t in user_topics if t in ALLOWED_TOPIC_IDS)
    if len(topics_sorted) < 2:
        return list(ranked)[:top_n]

    ordered = sorted(ranked, key=lambda a: a.rank)
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

    return picked[:top_n]
