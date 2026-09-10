"""Keyword lane normalization, source keys and per-subscriber routing."""

import pytest

from app.topic_packs.keywords import (
    MAX_KEYWORDS_PER_USER,
    is_keyword_source,
    keyword_source_key,
    normalize_keyword,
    normalize_keyword_list,
    user_keyword_source_keys,
    user_keywords,
)
from app.topic_packs.registry import digest_matches_topics


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  AI   Agents  ", "ai agents"),
        ("AI AGENTS", "ai agents"),
        ("ai\tagents", "ai agents"),
        ("Nvidia Earnings", "nvidia earnings"),
    ],
)
def test_normalize_collapses_case_and_whitespace(raw, expected):
    assert normalize_keyword(raw) == expected


@pytest.mark.parametrize("raw", ["", " ", "a", "!!!", "   ---  ", None, 42, ["x"], "x" * 61])
def test_normalize_rejects_unusable_input(raw):
    assert normalize_keyword(raw) is None


def test_normalize_list_dedupes_and_caps():
    raw = ["AI Agents", "ai agents", " AI  AGENTS "] + [f"term {i}" for i in range(20)]
    out = normalize_keyword_list(raw)
    assert out[0] == "ai agents"
    assert len(out) == len(set(out)) == MAX_KEYWORDS_PER_USER


def test_source_key_is_stable_and_prefixed():
    a = keyword_source_key("ai agents")
    assert a == keyword_source_key("ai agents"), "source key must be deterministic"
    assert is_keyword_source(a)
    assert a.startswith("kw_")


def test_source_key_separates_terms_that_share_a_slug():
    # Both flatten to the slug "c"; the hash suffix keeps the lanes distinct.
    assert keyword_source_key("c++") != keyword_source_key("c#")


def test_user_keywords_ignores_interests():
    """`interests` is a soft ranking signal, not an ingest lane.

    Promoting it would spawn a network lane per default interest for every
    subscriber, which is exactly the cost blow-up the cap exists to prevent.
    """
    prefs = {"interests": ["World news", "Cricket"], "keywords": ["ai agents"]}
    assert user_keywords(prefs) == ["ai agents"]


def test_keyword_digests_are_private_to_their_owner():
    alice = user_keyword_source_keys({"keywords": ["ai agents"]})
    bob = user_keyword_source_keys({"keywords": ["nvidia earnings"]})
    alice_lane = keyword_source_key("ai agents")

    assert digest_matches_topics(alice_lane, {"technology"}, alice) is True
    assert digest_matches_topics(alice_lane, {"technology"}, bob) is False


def test_keyword_digests_hidden_from_callers_without_keywords():
    """Instagram publishing calls the 2-arg form; it must never leak a term."""
    assert digest_matches_topics(keyword_source_key("ai agents"), {"technology"}) is False


def test_topic_routing_is_unaffected_by_keyword_support():
    assert digest_matches_topics("topic_startup_ychn", {"startups"}) is True
    assert digest_matches_topics("topic_startup_ychn", {"cricket"}) is False
    assert digest_matches_topics("techcrunch", {"technology"}) is True
    # Unknown sources stay eligible so migrations never empty the funnel.
    assert digest_matches_topics("brand_new_source", {"cricket"}) is True
