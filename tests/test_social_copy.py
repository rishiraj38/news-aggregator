"""Caption + hashtag rules. Pure functions — no network, no DB."""

from datetime import datetime, timezone

from app.services.social_copy import (
    CAPTION_LIMIT,
    MAX_HASHTAGS,
    CaptionStory,
    build_carousel_caption,
    build_single_caption,
    hashtags_for,
)

DAY = datetime(2026, 9, 20, tzinfo=timezone.utc)
OTHER_DAY = datetime(2026, 9, 21, tzinfo=timezone.utc)

STORIES = [
    CaptionStory("OpenAI ships a smaller reasoning model", "It is cheaper per token.", "https://a.com", "technology"),
    CaptionStory("YC batch is two-thirds AI", "Investors are picky.", "https://b.com", "startups"),
]


def test_caption_lists_every_story_and_the_cta():
    caption = build_carousel_caption(STORIES, site_url="https://helix.app", handle="@helix", date=DAY)
    for story in STORIES:
        assert story.title in caption
    assert "1." in caption and "2." in caption
    assert "https://helix.app" in caption
    assert "@helix" in caption


def test_caption_stays_within_instagram_limit():
    fat = [CaptionStory("T" * 400, "S" * 900, "https://x.com", "technology") for _ in range(8)]
    caption = build_carousel_caption(fat, site_url="https://helix.app", handle="@helix", date=DAY)
    assert len(caption) <= CAPTION_LIMIT
    # The hashtag block must survive truncation — it is the reach mechanism.
    assert caption.rstrip().endswith(hashtags_for(["technology"], date=DAY)[-1])


def test_hashtags_are_unique_well_formed_and_capped():
    tags = hashtags_for(["technology", "startups"], date=DAY, limit=24)
    assert len(tags) == 24
    assert len(set(tags)) == len(tags)
    assert all(t.startswith("#") and t == t.lower() and " " not in t for t in tags)
    assert len(hashtags_for(["technology"], date=DAY, limit=99)) <= MAX_HASHTAGS


def test_hashtags_rotate_between_days_but_are_stable_within_one():
    a = hashtags_for(["technology"], date=DAY)
    b = hashtags_for(["technology"], date=DAY)
    c = hashtags_for(["technology"], date=OTHER_DAY)
    assert a == b
    assert a != c, "consecutive posts should not carry an identical hashtag block"


def test_topic_pools_drive_the_niche_tags():
    cricket = hashtags_for(["cricket"], date=DAY, limit=12)
    assert any("cricket" in t for t in cricket)
    startups = hashtags_for(["startups"], date=DAY, limit=12)
    assert any(t in {"#startup", "#startups", "#ycombinator", "#founders"} for t in startups)


def test_unknown_topics_fall_back_to_technology():
    tags = hashtags_for(["gardening"], date=DAY, limit=10)
    assert "#ainews" in tags
    assert len(tags) == 10


def test_single_caption_carries_source_and_tags():
    caption = build_single_caption(STORIES[0], site_url="https://helix.app", handle="@helix", date=DAY)
    assert STORIES[0].title in caption
    assert "https://a.com" in caption
    assert "#ainews" in caption
    assert len(caption) <= CAPTION_LIMIT
