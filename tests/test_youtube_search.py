"""YouTube Data API search: filtering and ordering of candidates.

Ordering purely by upload date returned near-zero-view auto-generated bulletins
and unrelated talk-show clips for "AI News today". These lock in the filtering
that keeps low-value videos out of the digest pipeline.
"""

import pytest

from app.services import search_agent as sa
from app.services.search_agent import SearchAgent, _parse_iso_duration


def _search_payload(items):
    return {
        "items": [
            {
                "id": {"videoId": vid},
                "snippet": {
                    "title": title,
                    "channelTitle": "Chan",
                    "channelId": "c1",
                    "publishedAt": "2026-09-09T00:00:00Z",
                    "description": "d",
                },
            }
            for vid, title, *_ in items
        ]
    }


def _videos_payload(items):
    return {
        "items": [
            {
                "id": vid,
                "contentDetails": {"duration": duration},
                "statistics": {"viewCount": str(views)},
            }
            for vid, _title, views, duration in items
        ]
    }


@pytest.fixture()
def stub_api(monkeypatch):
    """Serve canned search + videos responses without touching the network."""

    def install(items):
        monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")

        class _Resp:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        def fake_get(url, params=None, timeout=None):
            if url == sa._YT_SEARCH_URL:
                return _Resp(_search_payload(items))
            return _Resp(_videos_payload(items))

        monkeypatch.setattr(sa.requests, "get", fake_get)

    return install


def test_low_view_videos_are_dropped(stub_api, monkeypatch):
    monkeypatch.setattr(sa, "YOUTUBE_MIN_VIEWS", 500)
    stub_api(
        [
            ("a", "Real AI news", 250_000, "PT10M"),
            ("b", "Auto-generated bulletin", 3, "PT8M"),
            ("c", "Another good one", 40_000, "PT12M"),
        ]
    )
    got = SearchAgent(top_n=5)._search_via_api("ai news")
    assert [c["video_id"] for c in got] == ["a", "c"]


def test_results_are_ordered_by_views(stub_api, monkeypatch):
    monkeypatch.setattr(sa, "YOUTUBE_MIN_VIEWS", 0)
    stub_api(
        [
            ("low", "Low", 1_000, "PT10M"),
            ("high", "High", 900_000, "PT10M"),
            ("mid", "Mid", 50_000, "PT10M"),
        ]
    )
    got = SearchAgent(top_n=5)._search_via_api("ai news")
    assert [c["video_id"] for c in got] == ["high", "mid", "low"]


def test_top_n_keeps_the_strongest_candidates(stub_api, monkeypatch):
    """The cut happens after sorting, so top_n takes the best, not the newest."""
    monkeypatch.setattr(sa, "YOUTUBE_MIN_VIEWS", 0)
    stub_api([(f"v{i}", f"T{i}", i * 1000, "PT10M") for i in range(1, 11)])
    got = SearchAgent(top_n=3)._search_via_api("ai news")
    assert [c["video_id"] for c in got] == ["v10", "v9", "v8"]


def test_shorts_are_skipped(stub_api, monkeypatch):
    monkeypatch.setattr(sa, "YOUTUBE_MIN_VIEWS", 0)
    stub_api(
        [
            ("short", "A short", 999_999, "PT45S"),
            ("full", "Full video", 1_000, "PT9M"),
        ]
    )
    got = SearchAgent(top_n=5)._search_via_api("ai news")
    assert [c["video_id"] for c in got] == ["full"]


def test_search_is_skipped_without_a_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    assert SearchAgent(top_n=5)._search_via_api("ai news") == []


def test_api_failure_returns_empty_rather_than_raising(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")

    def boom(*a, **k):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(sa.requests, "get", boom)
    assert SearchAgent(top_n=5)._search_via_api("ai news") == []


@pytest.mark.parametrize(
    "iso,seconds",
    [("PT1H2M30S", 3750), ("PT10M", 600), ("PT45S", 45), ("", 0), ("garbage", 0)],
)
def test_iso_duration_parsing(iso, seconds):
    assert _parse_iso_duration(iso) == seconds
