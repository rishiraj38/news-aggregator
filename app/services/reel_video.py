"""
Instagram Reel renderer: the daily stories as a 9:16 video.

Same design language as the carousel — this module deliberately imports the
primitives from `carousel_graphic` (fonts, theme, scrims, photo blocks) so the
two formats can never drift apart. What changes is the canvas (1080x1920) and
that motion is added afterwards by ffmpeg:

  * every segment is two Pillow layers, a background photo and a transparent
    text overlay, so type stays perfectly sharp while the photo moves
  * `zoompan` gives the photo a slow push-in, `overlay` slides + fades the text
  * `drawbox` draws a progress bar that fills across each segment
  * segments are joined with `xfade` crossfades

Audio is optional: set HELIX_REEL_AUDIO (or pass `audio_path`) to a music file
you have the rights to. Instagram's own licensed audio cannot be attached over
the API, so a silent reel is the default rather than a broken one.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence, Tuple

from PIL import Image, ImageDraw

from app.services.carousel_graphic import (
    Story,
    Theme,
    _accent_rule,
    _chip,
    _grain,
    _photo_block,
    _vertical_scrim,
    clean_text,
    draw_tracked,
    fit_headline,
    load_font,
    truncate_to_width,
    wrap_to_width,
)

logger = logging.getLogger(__name__)

REEL_W = 1080
REEL_H = 1920
GUTTER = 88
CONTENT_W = REEL_W - GUTTER * 2
FPS = 30
XFADE = 0.35  # seconds of crossfade between segments
PROGRESS_H = 10  # progress bar height in px


@dataclass
class ReelSpec:
    stories: Sequence[Story]
    site_url: str = ""
    handle: str = ""
    date: Optional[datetime] = None
    theme: Theme = field(default_factory=Theme)
    max_stories: int = 5
    hook_seconds: float = 2.6
    story_seconds: float = 5.4
    cta_seconds: float = 3.0
    audio_path: Optional[str] = None
    cover_title: str = "TODAY IN AI & TECH"


@dataclass
class _Segment:
    background: Path
    overlay: Path
    seconds: float


def ffmpeg_binary() -> str:
    exe = os.getenv("HELIX_FFMPEG", "").strip() or "ffmpeg"
    found = shutil.which(exe)
    if not found:
        raise RuntimeError(
            "ffmpeg not found. Install it (brew install ffmpeg / apt-get install ffmpeg) "
            "or set HELIX_FFMPEG to its path."
        )
    return found


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-12:])
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}):\n{tail}")


def _top_bar(canvas: Image.Image, theme: Theme, index_label: str = "") -> None:
    canvas.alpha_composite(_vertical_scrim((REEL_W, 320), 215, 0, ease=1.6, color=theme.ink[:3]), (0, 0))
    draw = ImageDraw.Draw(canvas)
    y = 92
    r = 10
    draw.ellipse([(GUTTER, y + 9), (GUTTER + r * 2, y + 9 + r * 2)], fill=theme.accent)
    x = GUTTER + r * 2 + 20
    w = draw_tracked(draw, (x, y), theme.brand_name, load_font("black", 38), theme.text, tracking=2.6)
    draw_tracked(
        draw, (x + w + 18, y + 12), theme.brand_tag, load_font("semibold", 23), theme.text_muted, tracking=3.4
    )
    if index_label:
        font = load_font("semibold", 26)
        tw = draw.textlength(index_label, font=font) + 2.2 * (len(index_label) - 1)
        draw_tracked(draw, (int(REEL_W - GUTTER - tw), y + 10), index_label, font, theme.text_muted, tracking=2.2)


def _blank(theme: Theme) -> Image.Image:
    return Image.new("RGBA", (REEL_W, REEL_H), theme.ink)


def _hook_layers(spec: ReelSpec, stories: Sequence[Story]) -> Tuple[Image.Image, Image.Image]:
    theme = spec.theme
    bg = _blank(theme)
    photo, _ = _photo_block(stories[0].image_url if stories else None, REEL_W, REEL_H, theme)
    bg.alpha_composite(photo, (0, 0))
    bg.alpha_composite(_vertical_scrim((REEL_W, REEL_H), 120, 250, ease=1.5, color=theme.ink[:3]))
    bg.alpha_composite(_grain((REEL_W, REEL_H)))

    fg = Image.new("RGBA", (REEL_W, REEL_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg)

    date = (spec.date or datetime.now(timezone.utc)).strftime("%d %B").upper()
    count_label = f"{len(stories)} STORIES  ·  {date}"

    lines, font, size = fit_headline(draw, spec.cover_title.upper(), CONTENT_W, 3, 116, 82, weight="black")
    block_h = len(lines) * int(size * 1.03)
    y = (REEL_H - block_h) // 2 - 40

    _accent_rule(draw, GUTTER, y - 78, theme, w=96)
    draw_tracked(
        draw, (GUTTER + 118, y - 88), count_label, load_font("semibold", 27), theme.text_muted, tracking=3.6
    )
    for line in lines:
        draw.text((GUTTER, y), line, font=font, fill=theme.text)
        y += int(size * 1.03)

    y += 34
    teaser_font = load_font("semibold", 31)
    for i, story in enumerate(stories[:3], start=1):
        draw.rounded_rectangle([(GUTTER, y), (GUTTER + 42, y + 42)], radius=13, fill=(*theme.accent[:3], 56))
        num_font = load_font("black", 23)
        nw = draw.textlength(str(i), font=num_font)
        draw.text((GUTTER + 21 - nw / 2, y + 9), str(i), font=num_font, fill=theme.text)
        draw.text(
            (GUTTER + 70, y + 5),
            truncate_to_width(draw, story.title, teaser_font, CONTENT_W - 70),
            font=teaser_font,
            fill=theme.text,
        )
        y += 66

    tip_font = load_font("semibold", 26)
    draw_tracked(draw, (GUTTER, REEL_H - 210), "WATCH TILL THE END", tip_font, theme.accent, tracking=4.0)

    _top_bar(fg, theme)
    return bg.convert("RGB"), fg


def _fit_story_text(
    draw: ImageDraw.ImageDraw, headline: str, summary: str, available_h: int
) -> tuple[list[str], object, int, list[str], object, int]:
    """
    Shrink the block until it fits the space between the photo and the source rule.

    Order of sacrifice: summary lines first (the headline is the story), then the
    headline's type size. Without this a four-line headline plus a long summary
    printed straight over the source line.
    """
    lines, font, size = fit_headline(draw, headline, CONTENT_W, 4, 78, 52, weight="black")
    body_font = load_font("regular", 33)
    body_lh = int(body_font.size * 1.4)
    rule_block = 6 + 28 + 38  # accent rule plus the air around it

    body_lines = wrap_to_width(draw, summary, body_font, CONTENT_W) if summary else []
    full_len = len(body_lines)

    def block_h() -> int:
        head = len(lines) * int(size * 1.08)
        body = (rule_block + len(body_lines) * body_lh) if body_lines else 0
        return head + body

    while body_lines and block_h() > available_h:
        body_lines.pop()
    while block_h() > available_h and size > 46:
        size -= 3
        font = load_font("black", size)
        lines = wrap_to_width(draw, headline, font, CONTENT_W)[:4]

    if body_lines and len(body_lines) < full_len:
        body_lines[-1] = body_lines[-1].rstrip(",.;:— ") + "…"
    if lines and len(wrap_to_width(draw, headline, font, CONTENT_W)) > len(lines):
        lines[-1] = lines[-1].rstrip(",.;:— ") + "…"
    return lines, font, size, body_lines, body_font, body_lh


def _story_layers(
    spec: ReelSpec, story: Story, number: int, of_stories: int
) -> Tuple[Image.Image, Image.Image]:
    theme = spec.theme
    bg = _blank(theme)
    photo_h = int(REEL_H * 0.52)
    photo, had_photo = _photo_block(story.image_url, REEL_W, photo_h, theme, ghost=f"{number:02d}")
    bg.alpha_composite(photo, (0, 0))
    bg.alpha_composite(
        _vertical_scrim((REEL_W, photo_h), 60 if had_photo else 20, 250, ease=2.3, color=theme.ink[:3]), (0, 0)
    )
    bg.alpha_composite(_grain((REEL_W, REEL_H)))

    fg = Image.new("RGBA", (REEL_W, REEL_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg)

    meta_y = photo_h - 108
    if story.topic_label:
        _chip(draw, (GUTTER, meta_y), story.topic_label.upper()[:22], theme)
    counter = f"{number:02d} / {of_stories:02d}"
    cfont = load_font("semibold", 26)
    cw = draw.textlength(counter, font=cfont) + 2.4 * (len(counter) - 1)
    draw_tracked(draw, (int(REEL_W - GUTTER - cw), meta_y + 14), counter, cfont, theme.text_muted, tracking=2.4)

    source_y = REEL_H - 190
    hairline_y = source_y - 34
    content_top = photo_h + 64
    lines, font, size, body_lines, body_font, body_lh = _fit_story_text(
        draw, clean_text(story.title), clean_text(story.summary), hairline_y - 46 - content_top
    )

    y = content_top
    for line in lines:
        draw.text((GUTTER, y), line, font=font, fill=theme.text)
        y += int(size * 1.08)

    if body_lines:
        y += 28
        draw.rounded_rectangle([(GUTTER, y), (GUTTER + 70, y + 6)], radius=3, fill=theme.accent)
        y += 38
        for line in body_lines:
            draw.text((GUTTER, y), line, font=body_font, fill=theme.text_muted)
            y += body_lh

    if story.source_label:
        draw.line([(GUTTER, hairline_y), (REEL_W - GUTTER, hairline_y)], fill=theme.hairline, width=2)
        sfont = load_font("semibold", 26)
        draw_tracked(draw, (GUTTER, source_y), "SOURCE", sfont, theme.text_muted, tracking=3.2)
        draw.text((GUTTER + 132, source_y), story.source_label, font=sfont, fill=theme.text)

    _top_bar(fg, theme, index_label=f"{number:02d}")
    return bg.convert("RGB"), fg


def _cta_layers(spec: ReelSpec) -> Tuple[Image.Image, Image.Image]:
    theme = spec.theme
    bg = _blank(theme)
    photo, _ = _photo_block(None, REEL_W, REEL_H, theme)
    bg.alpha_composite(photo, (0, 0))
    bg.alpha_composite(_vertical_scrim((REEL_W, REEL_H), 40, 225, ease=1.2, color=theme.ink[:3]))
    bg.alpha_composite(_grain((REEL_W, REEL_H)))

    fg = Image.new("RGBA", (REEL_W, REEL_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(fg)

    lines, font, size = fit_headline(
        draw, "GET THIS IN YOUR INBOX EVERY MORNING", CONTENT_W, 3, 96, 66, weight="black"
    )
    block_h = len(lines) * int(size * 1.05)
    y = (REEL_H - block_h) // 2 - 70
    _accent_rule(draw, GUTTER, y - 76, theme, w=96)
    draw_tracked(
        draw, (GUTTER + 118, y - 86), "FREE TO START", load_font("semibold", 27), theme.text_muted, tracking=3.6
    )
    for line in lines:
        draw.text((GUTTER, y), line, font=font, fill=theme.text)
        y += int(size * 1.05)

    y += 40
    body_font = load_font("medium", 33)
    body = "Your topics, your keywords, one short email. No doomscrolling."
    for line in wrap_to_width(draw, body, body_font, CONTENT_W)[:2]:
        draw.text((GUTTER, y), line, font=body_font, fill=theme.text_muted)
        y += int(body_font.size * 1.36)

    y += 44
    if spec.site_url:
        label = spec.site_url.replace("https://", "").replace("http://", "").rstrip("/").upper()
        _chip(draw, (GUTTER, y), label[:34], theme)
        y += 92
    if spec.handle:
        draw_tracked(
            draw,
            (GUTTER, y),
            f"FOLLOW {spec.handle.upper()}",
            load_font("semibold", 27),
            theme.text_muted,
            tracking=2.8,
        )

    _top_bar(fg, theme)
    return bg.convert("RGB"), fg


def _segment_filter(seconds: float, progress_from: float, progress_to: float) -> str:
    """
    Slow push-in on the photo, text sliding up as it fades in, progress bar filling.

    The background is pre-scaled larger than the canvas so `zoompan` crops into real
    pixels instead of upscaling a 1080-wide still. The progress bar is a full-width
    strip slid in from the left — `drawbox`'s `t` is its thickness, not the timestamp,
    so a width expression there never animates.
    """
    frames = max(1, int(round(seconds * FPS)))
    span = f"({progress_from:.5f}+({progress_to:.5f}-{progress_from:.5f})*t/{seconds:.3f})"
    return (
        f"[0:v]scale=1350:2400,zoompan=z='min(zoom+0.00045,1.10)':d={frames}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={REEL_W}x{REEL_H}:fps={FPS},setsar=1[bgv];"
        f"[1:v]format=rgba,fade=in:st=0.15:d=0.45:alpha=1[fgv];"
        f"[bgv][fgv]overlay=x=0:y='-18*max(0\,1-t/0.55)':format=auto[base];"
        f"[base][2:v]overlay=x='-{REEL_W}+{REEL_W}*{span}':y={REEL_H - PROGRESS_H}:format=auto,"
        f"format=yuv420p[v]"
    )


def _render_segment(seg: _Segment, out: Path, bar: Path, p_from: float, p_to: float) -> None:
    # The background is a SINGLE frame on purpose: zoompan emits `d` frames per input
    # frame, so looping the still first makes it render frames*frames frames and the
    # job never finishes. Only the overlay and the progress bar are looped.
    dur = f"{seg.seconds:.3f}"
    _run(
        [
            ffmpeg_binary(), "-y", "-loglevel", "error",
            "-i", str(seg.background),
            "-loop", "1", "-t", dur, "-i", str(seg.overlay),
            "-loop", "1", "-t", dur, "-i", str(bar),
            "-filter_complex", _segment_filter(seg.seconds, p_from, p_to),
            "-map", "[v]", "-t", dur, "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(out),
        ]
    )


def _crossfade_filter(durations: Sequence[float]) -> tuple[str, str]:
    """xfade chain across N segments. Each join shortens the timeline by XFADE."""
    label = "0:v"
    offset = 0.0
    parts: list[str] = []
    for i in range(1, len(durations)):
        offset += durations[i - 1] - XFADE
        out = f"x{i}"
        parts.append(
            f"[{label}][{i}:v]xfade=transition=fade:duration={XFADE}:offset={offset:.3f}[{out}]"
        )
        label = out
    return ";".join(parts), label


def total_seconds(spec: ReelSpec, story_count: int) -> float:
    """Final runtime after crossfades — what Instagram will show as the duration."""
    segments = 2 + story_count
    raw = spec.hook_seconds + story_count * spec.story_seconds + spec.cta_seconds
    return round(raw - XFADE * (segments - 1), 2)


def build_reel(spec: ReelSpec, out_path: Path, work_dir: Optional[Path] = None) -> Path:
    stories = [s for s in spec.stories if (s.title or "").strip()][: max(1, spec.max_stories)]
    if not stories:
        raise ValueError("build_reel needs at least one story with a title")

    ffmpeg_binary()  # fail fast with a clear message before rendering anything
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_holder = None
    if work_dir is None:
        tmp_holder = tempfile.TemporaryDirectory(prefix="helix-reel-")
        work_dir = Path(tmp_holder.name)
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        layers: list[_Segment] = []
        specs = (
            [(_hook_layers(spec, stories), spec.hook_seconds)]
            + [
                (_story_layers(spec, s, i, len(stories)), spec.story_seconds)
                for i, s in enumerate(stories, start=1)
            ]
            + [(_cta_layers(spec), spec.cta_seconds)]
        )
        for i, ((bg, fg), seconds) in enumerate(specs):
            bg_path = work_dir / f"bg-{i:02d}.jpg"
            fg_path = work_dir / f"fg-{i:02d}.png"
            bg.save(bg_path, format="JPEG", quality=95, subsampling=0)
            fg.save(fg_path, format="PNG")
            layers.append(_Segment(bg_path, fg_path, seconds))

        bar_path = work_dir / "progress-bar.png"
        Image.new("RGBA", (REEL_W, PROGRESS_H), spec.theme.accent).save(bar_path, format="PNG")

        clips: list[Path] = []
        elapsed = 0.0
        raw_total = sum(s.seconds for s in layers)
        for i, seg in enumerate(layers):
            clip = work_dir / f"seg-{i:02d}.mp4"
            _render_segment(
                seg, clip, bar_path, elapsed / raw_total, (elapsed + seg.seconds) / raw_total
            )
            elapsed += seg.seconds
            clips.append(clip)
            logger.info("Reel segment %d/%d rendered (%.1fs)", i + 1, len(layers), seg.seconds)

        chain, last = _crossfade_filter([s.seconds for s in layers])
        cmd = [ffmpeg_binary(), "-y", "-loglevel", "error"]
        for clip in clips:
            cmd += ["-i", str(clip)]

        audio = (spec.audio_path or os.getenv("HELIX_REEL_AUDIO", "")).strip()
        runtime = total_seconds(spec, len(stories))
        if audio and Path(audio).is_file():
            cmd += ["-i", audio]
            audio_idx = len(clips)
            filt = f"{chain};[{audio_idx}:a]afade=t=out:st={max(0.0, runtime - 1.2):.2f}:d=1.2[a]"
            cmd += [
                "-filter_complex", filt, "-map", f"[{last}]", "-map", "[a]",
                "-c:a", "aac", "-b:a", "160k", "-shortest",
            ]
        else:
            if audio:
                logger.warning("HELIX_REEL_AUDIO points at a missing file (%s) — rendering silent", audio)
            cmd += ["-filter_complex", chain, "-map", f"[{last}]"]

        cmd += [
            "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path),
        ]
        _run(cmd)
        logger.info("Reel written: %s (%.1fs)", out_path, runtime)
        return out_path
    finally:
        if tmp_holder is not None:
            tmp_holder.cleanup()
