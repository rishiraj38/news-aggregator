"""Carousel rendering. Offline: stories carry no image URL, so nothing is fetched."""

import pytest
from PIL import Image, ImageDraw

from app.services import carousel_graphic as cg
from app.services.carousel_graphic import (
    CANVAS_H,
    CANVAS_W,
    CarouselSpec,
    Story,
    fit_headline,
    render_carousel,
    source_from_url,
    truncate_to_width,
)

STORIES = [
    Story("First story about models", "A summary.", "https://www.bbc.com/news/x", topic_label="Technology"),
    Story("Second story about startups", "Another summary.", "https://news.ycombinator.com/x", topic_label="Startups"),
    Story("Third story", "", "", topic_label=""),
]


def test_render_carousel_returns_cover_stories_and_cta():
    slides = render_carousel(CarouselSpec(stories=STORIES, site_url="https://helix.app", handle="@helix"))
    assert len(slides) == len(STORIES) + 2
    for img in slides:
        assert img.size == (CANVAS_W, CANVAS_H)
        assert img.mode == "RGB"  # Instagram rejects alpha


def test_story_cap_keeps_the_set_within_instagram_ten_image_limit():
    many = [Story(f"Story {i}", "s") for i in range(12)]
    slides = render_carousel(CarouselSpec(stories=many, max_story_slides=8))
    assert len(slides) == 10


def test_no_stories_is_an_error_not_a_blank_post():
    with pytest.raises(ValueError):
        render_carousel(CarouselSpec(stories=[]))


def test_missing_image_never_triggers_a_fetch(monkeypatch):
    def explode(*a, **k):  # pragma: no cover - fails the test if reached
        raise AssertionError("fetch_background_rgba called for a story with no image")

    monkeypatch.setattr(cg, "fetch_background_rgba", explode)
    slides = render_carousel(CarouselSpec(stories=[Story("Only story", "summary")]))
    assert len(slides) == 3


def test_source_label_strips_scheme_and_www():
    assert source_from_url("https://www.bbc.com/news/x") == "bbc.com"
    assert source_from_url("http://m.theverge.com/a") == "theverge.com"
    assert source_from_url("") == ""
    assert source_from_url("not a url") == ""


def test_headline_fitting_shrinks_then_truncates():
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    short, _, big = fit_headline(draw, "Short one", 900, 4, 70, 46)
    assert len(short) == 1 and big == 70

    lines, _, size = fit_headline(draw, "word " * 200, 900, 4, 70, 46)
    assert len(lines) == 4
    assert size == 46
    assert lines[-1].endswith("…")


def test_truncate_to_width_breaks_on_a_word():
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font = cg.load_font("semibold", 29)
    out = truncate_to_width(draw, "an unusually long teaser line that will not fit on one row", font, 300)
    assert out.endswith("…")
    assert draw.textlength(out, font=font) <= 300
    assert "  " not in out
