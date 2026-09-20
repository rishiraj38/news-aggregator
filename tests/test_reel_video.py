"""Reel timing and filter construction. No ffmpeg run, no network."""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.services import reel_video as rv
from app.services.carousel_graphic import Story
from app.services.reel_video import REEL_H, REEL_W, XFADE, ReelSpec, total_seconds

STORIES = [Story(f"Story number {i}", "A summary sentence.", "https://bbc.com/x") for i in range(3)]


def test_runtime_accounts_for_every_crossfade():
    spec = ReelSpec(stories=STORIES, hook_seconds=2.6, story_seconds=5.4, cta_seconds=3.0)
    # 5 segments (hook + 3 stories + cta) means 4 joins, each shortening the timeline.
    assert total_seconds(spec, 3) == pytest.approx(2.6 + 3 * 5.4 + 3.0 - 4 * XFADE)


def test_runtime_stays_in_instagram_reel_territory():
    spec = ReelSpec(stories=STORIES)
    assert 15 <= total_seconds(spec, 5) <= 60


def test_crossfade_offsets_increase_and_leave_no_gap():
    durations = [2.6, 5.4, 5.4, 3.0]
    chain, last = rv._crossfade_filter(durations)
    assert last == f"x{len(durations) - 1}"
    offsets = [float(part.split("offset=")[1].split("[")[0]) for part in chain.split(";")]
    assert offsets == sorted(offsets)
    assert offsets[0] == pytest.approx(durations[0] - XFADE)
    assert offsets[-1] == pytest.approx(sum(durations[:-1]) - XFADE * len(offsets))


def test_segment_filter_animates_the_progress_bar_by_overlay_not_drawbox():
    f = rv._segment_filter(5.0, 0.2, 0.5)
    # drawbox's `t` is thickness, not time — a width expression there never moves.
    assert "drawbox" not in f
    assert "overlay=x='-1080+1080*(0.20000+(0.50000-0.20000)*t/5.000)'" in f
    assert f"s={REEL_W}x{REEL_H}" in f
    assert "zoompan" in f


def test_single_frame_background_keeps_zoompan_from_exploding(monkeypatch):
    seg = rv._Segment(Path("bg.jpg"), Path("fg.png"), 5.0)
    calls: list[list[str]] = []
    # Stub both: the suite must run with no ffmpeg installed.
    monkeypatch.setattr(rv, "ffmpeg_binary", lambda: "ffmpeg")
    monkeypatch.setattr(rv, "_run", lambda cmd: calls.append(cmd))
    rv._render_segment(seg, Path("out.mp4"), Path("bar.png"), 0.0, 0.5)
    cmd = calls[0]
    bg_flag = cmd[cmd.index(str(seg.background)) - 1]
    assert bg_flag == "-i", "the photo must be one frame; looping it multiplies zoompan output"
    assert cmd[cmd.index(str(seg.overlay)) - 1] == "-i"
    assert "-loop" in cmd  # the overlay and bar are still looped


def test_story_text_is_trimmed_to_fit_above_the_source_rule():
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    long_headline = "A genuinely very long headline about artificial intelligence policy " * 2
    long_summary = "Summary sentence that keeps going and going. " * 12
    lines, font, size, body, body_font, body_lh = rv._fit_story_text(draw, long_headline, long_summary, 420)
    height = len(lines) * int(size * 1.08) + (6 + 28 + 38 + len(body) * body_lh if body else 0)
    assert height <= 420
    assert len(lines) <= 4


def test_build_reel_rejects_empty_input(monkeypatch):
    monkeypatch.setattr(rv, "ffmpeg_binary", lambda: "ffmpeg")
    with pytest.raises(ValueError):
        rv.build_reel(ReelSpec(stories=[]), Path("/tmp/x.mp4"))


def test_missing_ffmpeg_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(rv.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="ffmpeg not found"):
        rv.ffmpeg_binary()
