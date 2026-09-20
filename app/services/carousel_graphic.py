"""
Instagram carousel renderer: one cover slide, N story slides, one call-to-action slide.

Design rules that keep the set looking like one publication:
  * One ink background, one accent, one type family (bundled Inter → system fallback)
  * Fixed 88px side gutter and the same wordmark bar on every slide
  * Photos are full-bleed at the top and fade into the ink colour, so there is no seam
    and text never sits on busy pixels
  * Text blocks are anchored to the bottom rule, so short summaries don't leave a hole
  * Stories without a usable photo get a drawn pattern, not an empty rectangle

`render_carousel()` returns Pillow images in posting order.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.services.news_graphic import fetch_background_rgba, fit_cover_crop_top

logger = logging.getLogger(__name__)

CANVAS_W = 1080
CANVAS_H = 1350
GUTTER = 88
CONTENT_W = CANVAS_W - GUTTER * 2

# Bottom furniture: progress dots sit at the very bottom, the source rule above them.
DOTS_Y = CANVAS_H - 58
SOURCE_Y = CANVAS_H - 156
HAIRLINE_Y = SOURCE_Y - 26

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUNDLED_FONTS = _REPO_ROOT / "assets" / "fonts"

# Weight name → bundled file, then system fallbacks (CI runners only ship DejaVu).
_FONT_FILES: dict[str, tuple[str, ...]] = {
    "black": (
        "InterDisplay-Black.ttf",
        "/System/Library/Fonts/Supplemental/Arial Black.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    "bold": (
        "InterDisplay-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    "semibold": (
        "Inter-SemiBold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    "medium": (
        "Inter-Medium.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ),
    "regular": (
        "Inter-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ),
}


@dataclass(frozen=True)
class Theme:
    """Colours are RGBA so every draw call can blend consistently."""

    ink: Tuple[int, int, int, int] = (9, 12, 24, 255)
    ink_soft: Tuple[int, int, int, int] = (17, 22, 40, 255)
    accent: Tuple[int, int, int, int] = (109, 140, 255, 255)
    accent_warm: Tuple[int, int, int, int] = (255, 186, 89, 255)
    text: Tuple[int, int, int, int] = (247, 248, 252, 255)
    text_muted: Tuple[int, int, int, int] = (176, 184, 208, 255)
    hairline: Tuple[int, int, int, int] = (255, 255, 255, 38)
    brand_name: str = "HELIX"
    brand_tag: str = "AI NEWS"


@dataclass
class Story:
    title: str
    summary: str = ""
    url: str = ""
    image_url: Optional[str] = None
    topic_label: str = ""

    @property
    def source_label(self) -> str:
        return source_from_url(self.url)


@dataclass
class CarouselSpec:
    stories: Sequence[Story]
    site_url: str = ""
    handle: str = ""
    date: Optional[datetime] = None
    theme: Theme = field(default_factory=Theme)
    max_story_slides: int = 6
    cover_title: str = "TODAY IN AI & TECH"
    cta_title: str = "YOUR OWN AI NEWS BRIEFING, EVERY MORNING"
    cta_points: Sequence[str] = (
        "Pick the topics and keywords you care about",
        "Agents read hundreds of sources overnight",
        "One short email, no doomscrolling",
    )


def _font_path(weight: str) -> str:
    override = os.getenv("HELIX_FONT_DIR", "").strip()
    for candidate in _FONT_FILES.get(weight, ()):
        p = Path(candidate)
        if p.is_absolute():
            if p.is_file():
                return str(p)
            continue
        search = ([Path(override)] if override else []) + [_BUNDLED_FONTS]
        for base in search:
            bundled = base / candidate
            if bundled.is_file():
                return str(bundled)
    return ""


def load_font(weight: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = _font_path(weight)
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            logger.warning("Could not open font %s", path)
    return ImageFont.load_default()


def source_from_url(url: str) -> str:
    """`https://www.bbc.com/news/x` → `bbc.com`. Empty string when there's nothing usable."""
    m = re.match(r"https?://([^/]+)", (url or "").strip(), re.I)
    if not m:
        return ""
    host = m.group(1).lower().split(":")[0]
    for prefix in ("www.", "m.", "amp."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    return host


def clean_text(text: str) -> str:
    """Collapse whitespace and calm down all-caps agency copy."""
    s = re.sub(r"\s+", " ", (text or "").strip())
    if len(s) > 24 and s.isupper():
        s = s.lower()
        s = s[0].upper() + s[1:]
    return s


def _text_w(draw: ImageDraw.ImageDraw, text: str, font, tracking: float = 0.0) -> float:
    return draw.textlength(text, font=font) + tracking * max(0, len(text) - 1)


def draw_tracked(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font,
    fill,
    tracking: float = 0.0,
) -> float:
    """Pillow has no letter-spacing; draw glyph by glyph. Returns the width drawn."""
    if tracking <= 0:
        draw.text(xy, text, font=font, fill=fill)
        return draw.textlength(text, font=font)
    x, y = xy
    start = x
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return (x - tracking) - start


def wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return []
    lines, current = [], words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_w:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _ellipsize(lines: list[str]) -> list[str]:
    if lines:
        lines[-1] = lines[-1].rstrip(",.;:— ") + "…"
    return lines


def truncate_to_width(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    """One line that fits, ending on a word boundary with an ellipsis when cut."""
    text = clean_text(text)
    if draw.textlength(text, font=font) <= max_w:
        return text
    words = text.split()
    out: list[str] = []
    for word in words:
        trial = " ".join(out + [word])
        if draw.textlength(trial + "…", font=font) > max_w:
            break
        out.append(word)
    if not out:
        return text[:1] + "…"
    return " ".join(out).rstrip(",.;:— ") + "…"


def fit_headline(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_w: int,
    max_lines: int,
    size_from: int,
    size_to: int,
    weight: str = "black",
) -> tuple[list[str], ImageFont.FreeTypeFont | ImageFont.ImageFont, int]:
    """Largest size where the headline still fits in `max_lines`. Truncates as a last resort."""
    size = size_from
    while size >= size_to:
        font = load_font(weight, size)
        lines = wrap_to_width(draw, text, font, max_w)
        if len(lines) <= max_lines:
            return lines, font, size
        size -= 3
    font = load_font(weight, size_to)
    lines = _ellipsize(wrap_to_width(draw, text, font, max_w)[:max_lines])
    return lines, font, size_to


def _vertical_scrim(
    size: Tuple[int, int],
    top_alpha: int,
    bottom_alpha: int,
    ease: float = 1.0,
    color: Tuple[int, int, int] = (9, 12, 24),
) -> Image.Image:
    """
    Single-column gradient stretched to width — far faster than per-pixel writes.

    The colour defaults to the ink background so a photo fades into the page
    instead of into black, which used to leave a visible seam.
    """
    w, h = size
    col = Image.new("L", (1, h))
    px = col.load()
    for y in range(h):
        t = (y / max(h - 1, 1)) ** ease
        px[0, y] = int(top_alpha + (bottom_alpha - top_alpha) * t)
    layer = Image.new("RGBA", (w, h), (*color, 255))
    layer.putalpha(col.resize((w, h), Image.Resampling.BILINEAR))
    return layer


def _grain(size: Tuple[int, int], sigma: float = 7.0, alpha: int = 14) -> Image.Image:
    noise = Image.effect_noise(size, sigma).convert("L")
    layer = Image.new("RGBA", size, (255, 255, 255, 0))
    layer.putalpha(noise.point(lambda v: int(abs(v - 128) / 128 * alpha)))
    return layer


def _pattern_block(w: int, h: int, theme: Theme, ghost: str = "") -> Image.Image:
    """Drawn backdrop for stories with no usable photo: dot grid, accent glow, ghost numeral."""
    block = Image.new("RGBA", (w, h), theme.ink_soft)

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([(-w // 4, -h // 2), (int(w * 0.75), int(h * 0.7))], fill=(*theme.accent[:3], 95))
    gd.ellipse([(int(w * 0.45), int(h * 0.3)), (int(w * 1.3), int(h * 1.5))], fill=(*theme.accent_warm[:3], 46))
    block.alpha_composite(glow.filter(ImageFilter.GaussianBlur(130)))

    dots = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    step = 44
    for gy in range(step // 2, h, step):
        for gx in range(step // 2, w, step):
            dd.ellipse([(gx - 2, gy - 2), (gx + 2, gy + 2)], fill=(*theme.text[:3], 26))
    block.alpha_composite(dots)

    if ghost:
        gl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gld = ImageDraw.Draw(gl)
        font = load_font("black", int(h * 0.85))
        tw = gld.textlength(ghost, font=font)
        gld.text((w - tw - GUTTER // 2, -int(h * 0.12)), ghost, font=font, fill=(*theme.text[:3], 26))
        block.alpha_composite(gl)
    return block


def _photo_block(url: Optional[str], w: int, h: int, theme: Theme, ghost: str = "") -> Tuple[Image.Image, bool]:
    """Cover-cropped photo when one loads, else a drawn pattern. Returns (image, had_photo)."""
    photo = fetch_background_rgba(url) if url else None
    if photo is not None:
        block = fit_cover_crop_top(photo, w, h)
        if photo.size[0] < w:  # upscaled thumbnails need help
            block = ImageEnhance.Sharpness(block).enhance(1.35)
        # Bright press photos fight the white wordmark; hold them just under full brightness.
        block = ImageEnhance.Brightness(block).enhance(0.9)
        return block.convert("RGBA"), True
    return _pattern_block(w, h, theme, ghost=ghost), False


def _base_canvas(theme: Theme) -> Image.Image:
    return Image.new("RGBA", (CANVAS_W, CANVAS_H), theme.ink)


def _draw_top_bar(canvas: Image.Image, theme: Theme, index_label: str = "", shade: bool = False) -> None:
    if shade:  # soft gradient keeps the wordmark readable over any photo, with no visible edge
        canvas.alpha_composite(
            _vertical_scrim((CANVAS_W, 300), 215, 0, ease=1.6, color=theme.ink[:3]), (0, 0)
        )
    draw = ImageDraw.Draw(canvas)
    y = 62
    dot_r = 9
    draw.ellipse([(GUTTER, y + 8), (GUTTER + dot_r * 2, y + 8 + dot_r * 2)], fill=theme.accent)
    x = GUTTER + dot_r * 2 + 18
    w = draw_tracked(draw, (x, y), theme.brand_name, load_font("black", 34), theme.text, tracking=2.4)
    draw_tracked(
        draw, (x + w + 16, y + 10), theme.brand_tag, load_font("semibold", 21), theme.text_muted, tracking=3.2
    )

    if index_label:
        idx_font = load_font("semibold", 24)
        iw = _text_w(draw, index_label, idx_font, tracking=2.0)
        draw_tracked(
            draw, (int(CANVAS_W - GUTTER - iw), y + 8), index_label, idx_font, theme.text_muted, tracking=2.0
        )


def _draw_progress(canvas: Image.Image, theme: Theme, current: int, total: int) -> None:
    if total < 2:
        return
    draw = ImageDraw.Draw(canvas)
    dot_w, dot_h, gap = 26, 6, 10
    total_w = total * dot_w + (total - 1) * gap
    x = (CANVAS_W - total_w) // 2
    for i in range(total):
        fill = theme.accent if i == current else (*theme.text[:3], 55)
        draw.rounded_rectangle([(x, DOTS_Y), (x + dot_w, DOTS_Y + dot_h)], radius=3, fill=fill)
        x += dot_w + gap


def _chip(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    theme: Theme,
    fill_rgb: Optional[Tuple[int, int, int]] = None,
    text_color=None,
) -> int:
    """Pill label. Returns its width."""
    font = load_font("semibold", 22)
    tracking = 2.6
    pad_x, pad_y = 20, 12
    tw = _text_w(draw, text, font, tracking)
    x, y = xy
    h = font.size + pad_y * 2
    draw.rounded_rectangle(
        [(x, y), (x + tw + pad_x * 2, y + h)], radius=h // 2, fill=(*(fill_rgb or theme.accent[:3]), 235)
    )
    draw_tracked(draw, (x + pad_x, y + pad_y - 2), text, font, text_color or theme.ink, tracking)
    return int(tw + pad_x * 2)


def _accent_rule(draw: ImageDraw.ImageDraw, x: int, y: int, theme: Theme, w: int = 86) -> None:
    draw.rounded_rectangle([(x, y), (x + w, y + 7)], radius=4, fill=theme.accent)


def render_cover_slide(spec: CarouselSpec, stories: Sequence[Story], total_slides: int) -> Image.Image:
    theme = spec.theme
    canvas = _base_canvas(theme)
    lead = stories[0] if stories else None

    photo_h = int(CANVAS_H * 0.62)
    photo, _ = _photo_block(lead.image_url if lead else None, CANVAS_W, photo_h, theme)
    canvas.alpha_composite(photo, (0, 0))
    canvas.alpha_composite(
        _vertical_scrim((CANVAS_W, photo_h), 110, 255, ease=1.8, color=theme.ink[:3]), (0, 0)
    )
    canvas.alpha_composite(_grain((CANVAS_W, CANVAS_H)))

    draw = ImageDraw.Draw(canvas)
    teasers = [s for s in stories[:3] if (s.title or "").strip()]

    # Lay the block out from the bottom so nothing floats in dead space.
    swipe_y = CANVAS_H - 138
    teaser_step = 64
    teaser_font = load_font("semibold", 29)
    teasers_top = swipe_y - 46 - len(teasers) * teaser_step

    sub_font = load_font("medium", 30)
    sub_text = f"{len(stories)} stories worth your morning, curated and summarised by AI."
    sub_lines = wrap_to_width(draw, sub_text, sub_font, CONTENT_W)[:2]
    sub_lh = int(sub_font.size * 1.34)
    sub_top = teasers_top - 30 - len(sub_lines) * sub_lh

    hook_lines, hook_font, hook_size = fit_headline(
        draw, spec.cover_title.upper(), CONTENT_W, 2, 104, 72, weight="black"
    )
    hook_lh = int(hook_size * 1.04)
    hook_top = sub_top - 22 - len(hook_lines) * hook_lh
    date_y = hook_top - 52

    date = (spec.date or datetime.now(timezone.utc)).strftime("%d %B %Y").upper()
    _accent_rule(draw, GUTTER, date_y, theme)
    draw_tracked(
        draw, (GUTTER + 106, date_y - 9), date, load_font("semibold", 24), theme.text_muted, tracking=3.4
    )

    y = hook_top
    for line in hook_lines:
        draw.text((GUTTER, y), line, font=hook_font, fill=theme.text)
        y += hook_lh

    y = sub_top
    for line in sub_lines:
        draw.text((GUTTER, y), line, font=sub_font, fill=theme.text_muted)
        y += sub_lh

    y = teasers_top
    num_font = load_font("black", 22)
    for i, story in enumerate(teasers, start=1):
        draw.rounded_rectangle([(GUTTER, y), (GUTTER + 40, y + 40)], radius=12, fill=(*theme.accent[:3], 56))
        nw = draw.textlength(str(i), font=num_font)
        draw.text((GUTTER + 20 - nw / 2, y + 9), str(i), font=num_font, fill=theme.text)
        draw.text(
            (GUTTER + 66, y + 4),
            truncate_to_width(draw, story.title, teaser_font, CONTENT_W - 66),
            font=teaser_font,
            fill=theme.text,
        )
        y += teaser_step

    sw = draw_tracked(draw, (GUTTER, swipe_y), "SWIPE", load_font("semibold", 25), theme.accent, tracking=4.0)
    draw.text((GUTTER + sw + 18, swipe_y - 3), "→", font=load_font("bold", 28), fill=theme.accent)

    _draw_top_bar(canvas, theme, shade=True)
    _draw_progress(canvas, theme, 0, total_slides)
    return canvas.convert("RGB")


def render_story_slide(
    spec: CarouselSpec,
    story: Story,
    number: int,
    of_stories: int,
    slide_index: int,
    total_slides: int,
) -> Image.Image:
    theme = spec.theme
    canvas = _base_canvas(theme)

    photo_h = int(CANVAS_H * 0.46)
    photo, had_photo = _photo_block(
        story.image_url, CANVAS_W, photo_h, theme, ghost=f"{number:02d}"
    )
    canvas.alpha_composite(photo, (0, 0))
    canvas.alpha_composite(
        _vertical_scrim((CANVAS_W, photo_h), 60 if had_photo else 20, 250, ease=2.4, color=theme.ink[:3]),
        (0, 0),
    )
    canvas.alpha_composite(_grain((CANVAS_W, CANVAS_H)))

    draw = ImageDraw.Draw(canvas)

    # Chip + counter ride the bottom edge of the image area.
    meta_y = photo_h - 92
    if story.topic_label:
        _chip(draw, (GUTTER, meta_y), story.topic_label.upper()[:22], theme)
    counter = f"{number:02d} / {of_stories:02d}"
    counter_font = load_font("semibold", 23)
    cw = _text_w(draw, counter, counter_font, tracking=2.4)
    draw_tracked(
        draw,
        (int(CANVAS_W - GUTTER - cw), meta_y + 12),
        counter,
        counter_font,
        theme.text_muted,
        tracking=2.4,
    )

    # Measure headline + summary, then anchor the block above the source rule.
    headline = clean_text(story.title)
    lines, font, size = fit_headline(draw, headline, CONTENT_W, 4, 70, 46, weight="black")
    head_lh = int(size * 1.09)
    head_h = len(lines) * head_lh

    body_font = load_font("regular", 30)
    body_lh = int(body_font.size * 1.42)
    summary = clean_text(story.summary)
    body_lines = wrap_to_width(draw, summary, body_font, CONTENT_W) if summary else []
    max_body = 4 if len(lines) <= 3 else 3
    if len(body_lines) > max_body:
        body_lines = _ellipsize(body_lines[:max_body])

    rule_gap_top, rule_gap_bottom = 26, 34
    block_h = head_h + (rule_gap_top + 5 + rule_gap_bottom + len(body_lines) * body_lh if body_lines else 0)

    top_limit = photo_h + 44
    y = max(top_limit, HAIRLINE_Y - 44 - block_h)

    for line in lines:
        draw.text((GUTTER, y), line, font=font, fill=theme.text)
        y += head_lh

    if body_lines:
        y += rule_gap_top
        draw.rounded_rectangle([(GUTTER, y), (GUTTER + 64, y + 5)], radius=3, fill=theme.accent)
        y += rule_gap_bottom
        for line in body_lines:
            draw.text((GUTTER, y), line, font=body_font, fill=theme.text_muted)
            y += body_lh

    source = story.source_label
    if source:
        draw.line([(GUTTER, HAIRLINE_Y), (CANVAS_W - GUTTER, HAIRLINE_Y)], fill=theme.hairline, width=2)
        src_font = load_font("semibold", 23)
        draw_tracked(draw, (GUTTER, SOURCE_Y), "SOURCE", src_font, theme.text_muted, tracking=3.0)
        draw.text((GUTTER + 118, SOURCE_Y), source, font=src_font, fill=theme.text)

    _draw_top_bar(canvas, theme, shade=True)
    _draw_progress(canvas, theme, slide_index, total_slides)
    return canvas.convert("RGB")


def render_outro_slide(spec: CarouselSpec, total_slides: int) -> Image.Image:
    theme = spec.theme
    canvas = _base_canvas(theme)
    canvas.alpha_composite(_pattern_block(CANVAS_W, CANVAS_H, theme))
    canvas.alpha_composite(_vertical_scrim((CANVAS_W, CANVAS_H), 30, 235, ease=1.15, color=theme.ink[:3]))
    canvas.alpha_composite(_grain((CANVAS_W, CANVAS_H)))

    draw = ImageDraw.Draw(canvas)
    y = 410
    _accent_rule(draw, GUTTER, y, theme)
    draw_tracked(
        draw,
        (GUTTER + 106, y - 9),
        "FROM THE HELIX NEWSROOM",
        load_font("semibold", 24),
        theme.text_muted,
        tracking=3.4,
    )

    y += 56
    lines, font, size = fit_headline(draw, spec.cta_title.upper(), CONTENT_W, 4, 84, 58, weight="black")
    for line in lines:
        draw.text((GUTTER, y), line, font=font, fill=theme.text)
        y += int(size * 1.06)

    y += 44
    point_font = load_font("medium", 30)
    for point in list(spec.cta_points)[:3]:
        draw.ellipse([(GUTTER + 2, y + 12), (GUTTER + 16, y + 26)], fill=theme.accent)
        for i, line in enumerate(wrap_to_width(draw, point, point_font, CONTENT_W - 48)[:2]):
            draw.text((GUTTER + 48, y), line, font=point_font, fill=theme.text_muted)
            y += int(point_font.size * 1.3)
            if i == 0:
                continue
        y += 18

    y += 26
    if spec.site_url:
        label = spec.site_url.replace("https://", "").replace("http://", "").rstrip("/").upper()
        _chip(draw, (GUTTER, y), label[:34], theme)
        y += 84
    if spec.handle:
        draw_tracked(
            draw,
            (GUTTER, y),
            f"FOLLOW {spec.handle.upper()} FOR THE DAILY BRIEF",
            load_font("semibold", 24),
            theme.text_muted,
            tracking=2.4,
        )

    _draw_top_bar(canvas, theme)
    _draw_progress(canvas, theme, total_slides - 1, total_slides)
    return canvas.convert("RGB")


def render_carousel(spec: CarouselSpec) -> list[Image.Image]:
    """Cover + one slide per story + outro, capped at Instagram's 10-image limit."""
    stories = [s for s in spec.stories if (s.title or "").strip()][: max(1, spec.max_story_slides)]
    if not stories:
        raise ValueError("render_carousel needs at least one story with a title")

    total = len(stories) + 2  # cover + stories + outro
    slides = [render_cover_slide(spec, stories, total)]
    for i, story in enumerate(stories, start=1):
        slides.append(
            render_story_slide(
                spec, story, number=i, of_stories=len(stories), slide_index=i, total_slides=total
            )
        )
    slides.append(render_outro_slide(spec, total))
    return slides


def save_slides(slides: Iterable[Image.Image], out_dir: Path, stem: str, quality: int = 94) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, img in enumerate(slides, start=1):
        p = out_dir / f"{stem}-{i:02d}.jpg"
        img.save(p, format="JPEG", quality=quality, optimize=True, subsampling=0)
        paths.append(p)
    return paths
