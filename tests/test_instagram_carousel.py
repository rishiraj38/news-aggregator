"""Story selection for the carousel, and the Graph API child-count guard."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from app.services.instagram_publish import publish_jpeg_carousel_post
from publish_instagram_card import _digests_from_curator_picks, _story_topic_label


@dataclass
class Ranked:
    digest_id: str
    rank: int = 1
    relevance_score: float = 5.0


DIGESTS = [
    {"id": "youtube:a", "title": "A", "article_type": "youtube"},
    {"id": "openai:b", "title": "B", "article_type": "openai"},
    {"id": "topic_startup_ychn:c", "title": "C", "article_type": "topic_startup_ychn"},
    {"id": "topic_sport_bbcsport:d", "title": "D", "article_type": "topic_sport_bbcsport"},
]


def test_picks_follow_curator_rank_order():
    ranked = [Ranked("topic_startup_ychn:c", rank=1), Ranked("openai:b", rank=2), Ranked("youtube:a", rank=3)]
    picks = _digests_from_curator_picks(DIGESTS, ranked, 3)
    assert [p["id"] for p in picks] == ["topic_startup_ychn:c", "openai:b", "youtube:a"]


def test_duplicate_ids_are_not_posted_twice_in_one_carousel():
    ranked = [Ranked("openai:b", rank=1), Ranked("openai:b", rank=2), Ranked("youtube:a", rank=3)]
    picks = _digests_from_curator_picks(DIGESTS, ranked, 3)
    ids = [p["id"] for p in picks]
    assert len(ids) == len(set(ids))
    assert ids[:2] == ["openai:b", "youtube:a"]


def test_short_curator_output_is_topped_up_with_newest_digests():
    picks = _digests_from_curator_picks(DIGESTS, [Ranked("openai:b")], 3)
    assert picks[0]["id"] == "openai:b"
    assert len(picks) == 3


def test_unusable_curator_ids_fall_back_to_newest():
    picks = _digests_from_curator_picks(DIGESTS, [Ranked("nonsense-id")], 2)
    assert [p["id"] for p in picks] == ["youtube:a", "openai:b"]


def test_whitespace_in_curator_ids_still_matches():
    picks = _digests_from_curator_picks(DIGESTS, [Ranked(" openai: b ")], 1)
    assert picks[0]["id"] == "openai:b"


def test_topic_label_is_short_enough_for_a_chip():
    assert _story_topic_label("topic_startup_ychn") == "Startups"
    assert _story_topic_label("topic_sport_bbcsport") == "Sports"
    assert _story_topic_label("openai") == "Technology"
    assert _story_topic_label("unknown_source") == "Briefing"


@pytest.mark.parametrize("count", [0, 1, 11])
def test_carousel_rejects_illegal_child_counts(count):
    with pytest.raises(ValueError):
        publish_jpeg_carousel_post(
            jpeg_paths=[Path(f"/tmp/{i}.jpg") for i in range(count)],
            caption="c",
            access_token="t",
            instagram_business_id="1",
        )
