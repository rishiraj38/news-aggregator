"""Digest candidate selection: recency ordering and per-source fairness.

Regression cover for the run where a stale BBC Sport backlog took 49 of 50
digest slots and every ``['technology']`` subscriber matched zero digests.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from app.database.repository import Repository

NOW = datetime.now(timezone.utc)


def _bucket(source, n, *, hours_apart=1):
    return [
        {"type": source, "id": f"{source}-{i}", "published_at": NOW - timedelta(hours=i * hours_apart)}
        for i in range(n)
    ]


def test_one_source_cannot_monopolise_the_batch():
    buckets = {
        "topic_sport_bbcsport": _bucket("topic_sport_bbcsport", 300),
        "techcrunch": _bucket("techcrunch", 20),
        "openai": _bucket("openai", 8),
    }
    picked = Repository._interleave_by_source(buckets, 50)
    counts = Counter(p["type"] for p in picked)

    assert len(picked) == 50
    assert counts["topic_sport_bbcsport"] < 30, "backlog still dominating"
    assert counts["openai"] == 8, "small source should be fully drained"
    assert counts["techcrunch"] == 20


def test_interleave_drains_everything_when_unlimited():
    buckets = {"a": _bucket("a", 5), "b": _bucket("b", 3)}
    assert len(Repository._interleave_by_source(buckets, None)) == 8


def test_interleave_handles_empty_input():
    assert Repository._interleave_by_source({}, 50) == []


def test_limit_larger_than_supply_returns_all():
    buckets = {"a": _bucket("a", 2)}
    assert len(Repository._interleave_by_source(buckets, 99)) == 2


def test_recency_key_orders_newest_first_with_undated_last():
    items = [
        {"published_at": NOW - timedelta(days=5)},
        {"published_at": None},
        {"published_at": NOW},
    ]
    items.sort(key=lambda a: Repository._recency_key(a["published_at"]), reverse=True)
    assert items[0]["published_at"] == NOW
    assert items[-1]["published_at"] is None


def test_recency_key_mixes_naive_and_aware_without_raising():
    """RSS rows land naive; DB rows come back aware. Sorting must not explode."""
    naive = datetime(2020, 1, 1)
    key_naive = Repository._recency_key(naive)
    key_aware = Repository._recency_key(NOW)
    assert key_naive.tzinfo is not None
    assert key_aware > key_naive
