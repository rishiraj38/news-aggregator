"""
Generate portrait feed cards: readable lower-third panel over photo, Helix mark, ticker.
"""

from __future__ import annotations

import io
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

CANVAS_W = 1080
CANVAS_H = 1350

_RED_HEADLINE = (255, 77, 90, 255)
_WHITE_SOFT = (248, 249, 252, 255)
_PANEL = (14, 16, 28, 238)
_BAR_RED = (160, 22, 45, 255)

_FONT_BOLD: Sequence[str] = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
)
_FONT_REG: Sequence[str] = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
)


def _load_font(paths: Sequence[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in paths:
        p = Path(path)
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def fetch_background_rgba(url: str, timeout: float = 12.0) -> Image.Image | None:
    if not url or not url.startswith("http"):
        return None
    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
            },
        )
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    except Exception as e:
        logger.warning("Could not load background image: %s", e)
        return None


def fit_cover_crop_top(img: Image.Image, dest_w: int, dest_h: int) -> Image.Image:
    """Cover crop; when trimming vertical excess, keep the **top** (faces / subjects)."""
    w, h = img.size
    src_ratio = w / h
    dest_ratio = dest_w / dest_h
    if src_ratio > dest_ratio:
        nw = int(h * dest_ratio)
        box = ((w - nw) // 2, 0, (w - nw) // 2 + nw, h)
    else:
        nh = int(w / dest_ratio)
        box = (0, 0, w, nh)
    return img.crop(box).resize((dest_w, dest_h), Image.Resampling.LANCZOS)


def fit_contain_rgba(img: Image.Image, max_w: int, max_h: int) -> Tuple[Image.Image, int, int]:
    """Scale down (or up) so the whole image fits inside max_w×max_h; return image + top-left offset."""
    w, h = img.size
    if w < 1 or h < 1:
        blank = Image.new("RGBA", (1, 1), (32, 32, 42, 255))
        return blank, max_w // 2, max_h // 2
    scale = min(max_w / w, max_h / h)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    out = img.resize((nw, nh), Image.Resampling.LANCZOS)
    ox = (max_w - nw) // 2
    oy = (max_h - nh) // 2
    return out, ox, oy


def _paste_photo_blur_fill_then_contain(canvas: Image.Image, photo: Image.Image) -> None:
    """
    Full artwork visible: blurred cover fills the canvas (no harsh letterboxing), sharp image centered contain-mode.
    """
    bg = fit_cover_crop_top(photo, CANVAS_W, CANVAS_H)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=40))
    canvas.paste(bg.convert("RGB"), (0, 0))
    fg, ox, oy = fit_contain_rgba(photo, CANVAS_W, CANVAS_H)
    canvas.paste(fg, (ox, oy), fg)


def _gradient_overlay(size: Tuple[int, int], start_alpha: int, end_alpha: int) -> Image.Image:
    w, h = size
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = grad.load()
    if not px:
        return grad
    for y in range(h):
        t = y / max(h - 1, 1)
        a = int(start_alpha + (end_alpha - start_alpha) * t)
        for x in range(w):
            px[x, y] = (0, 0, 0, a)
    return grad


def humanize_detail_text(text: str) -> str:
    """Turn shouty all-caps agency copy into calmer sentence case for reading."""
    s = re.sub(r"\s+", " ", (text or "").strip())
    if len(s) < 2:
        return s
    if s.isupper() and len(s) > 24:
        s = s.lower()
        s = s[0].upper() + s[1:]
    return s


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = current + " " + word
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _soft_text_shadow(
    draw: ImageDraw.ImageDraw,
    pos: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill,
    shadow: Tuple[int, int, int, int],
    so: int = 2,
) -> None:
    x, y = pos
    draw.text((x + so, y + so), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def _accent_bar(draw: ImageDraw.ImageDraw, x: int, y: int, h: int) -> None:
    draw.rounded_rectangle([(x, y), (x + 8, y + h)], radius=3, fill=_RED_HEADLINE)


@dataclass
class BreakingGraphicSpec:
    main_headline: str
    detail_text: str
    background_image_url: Optional[str] = None
    brand_label: str = "HELIX AI"
    ticker_text: str = "BREAKING NEWS"
    logo_path: Optional[str] = None


def _make_default_helix_logo(max_width: int = 300) -> Image.Image:
    """Stacked mark: Helix + AI News, soft shadow, indigo panel."""
    w0, h0 = 316, 102
    pad = 14
    im = Image.new("RGBA", (w0 + pad * 2, h0 + pad * 2), (0, 0, 0, 0))
    ox, oy = pad, pad
    shadow = Image.new("RGBA", (w0 + pad * 2, h0 + pad * 2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([(ox + 4, oy + 6), (ox + w0 + 4, oy + h0 + 6)], radius=22, fill=(0, 0, 0, 95))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    im.alpha_composite(shadow, (0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([(ox, oy), (ox + w0 - 1, oy + h0 - 1)], radius=22, fill=(38, 42, 92, 255))
    dr.rounded_rectangle([(ox + 2, oy + 2), (ox + w0 - 3, oy + h0 - 3)], radius=20, outline=(130, 140, 220, 200), width=2)

    fz_main = 40
    fz_sub = 20
    f_main = _load_font(_FONT_BOLD, fz_main)
    f_sub = _load_font(_FONT_BOLD, fz_sub)
    t1 = "Helix"
    t2 = "AI NEWS"
    tw1 = dr.textlength(t1, font=f_main)
    tw2 = dr.textlength(t2, font=f_sub)
    cx = ox + (w0 - tw1) // 2
    cy = oy + 16
    _soft_text_shadow(dr, (cx, cy), t1, f_main, (255, 255, 255, 255), (0, 0, 0, 140), so=3)
    cx2 = ox + (w0 - tw2) // 2
    dr.text((cx2, cy + fz_main + 4), t2, font=f_sub, fill=(186, 198, 255, 255))

    if im.size[0] > max_width:
        ratio = max_width / im.size[0]
        im = im.resize((max_width, max(1, int(im.size[1] * ratio))), Image.Resampling.LANCZOS)
    return im


def _load_logo_file(path_str: str) -> Optional[Image.Image]:
    p = Path(path_str).expanduser()
    if not p.is_file():
        return None
    try:
        return Image.open(p).convert("RGBA")
    except OSError as e:
        logger.warning("Could not read logo %s: %s", p, e)
        return None


def _paste_helix_logo_top_right(canvas: Image.Image, spec: BreakingGraphicSpec) -> None:
    target_w = min(300, CANVAS_W // 2)
    path_candidates = (spec.logo_path, os.getenv("HELIX_LOGO_PATH", "").strip())
    logo_img: Optional[Image.Image] = None
    for p in path_candidates:
        if p:
            logo_img = _load_logo_file(p)
            if logo_img:
                break
    if logo_img:
        ratio = target_w / logo_img.size[0]
        nh = max(52, int(logo_img.size[1] * ratio))
        logo_img = logo_img.resize((target_w, nh), Image.Resampling.LANCZOS)
        # Subtle backing so PNGs work on busy photos
        bx0 = CANVAS_W - logo_img.size[0] - 40
        by0 = 28
        pad = Image.new("RGBA", (logo_img.size[0] + 24, logo_img.size[1] + 24), (0, 0, 0, 0))
        bd = ImageDraw.Draw(pad)
        bd.rounded_rectangle([(0, 0), (pad.size[0] - 1, pad.size[1] - 1)], radius=16, fill=(10, 12, 24, 180))
        canvas.alpha_composite(pad, (bx0 - 12, by0 - 12))
        canvas.alpha_composite(logo_img, (bx0, by0))
        return

    mark = _make_default_helix_logo(max_width=target_w)
    canvas.alpha_composite(mark, (CANVAS_W - mark.size[0] - 36, 26))


def render_breaking_news_card(spec: BreakingGraphicSpec, solid_fallback: Tuple[int, int, int] = (18, 20, 32)) -> Image.Image:
    base_rgba = Image.new("RGBA", (CANVAS_W, CANVAS_H), (*solid_fallback, 255))
    if spec.background_image_url:
        photo = fetch_background_rgba(spec.background_image_url)
        if photo:
            _paste_photo_blur_fill_then_contain(base_rgba, photo)

    overlay_h = int(CANVAS_H * 0.50)
    grad = _gradient_overlay((CANVAS_W, overlay_h), 0, 165)
    base_rgba.alpha_composite(grad, dest=(0, CANVAS_H - overlay_h))

    draw = ImageDraw.Draw(base_rgba)

    panel_pad_h = 52
    panel_left = panel_pad_h
    panel_right = CANVAS_W - panel_pad_h
    bar_x = panel_left + 28
    main_tx = bar_x + 22
    headline_max_w = panel_right - main_tx - 28

    main_line = spec.main_headline.upper().strip()
    main_font_size = 76
    while main_font_size >= 48:
        main_font = _load_font(_FONT_BOLD, main_font_size)
        if draw.textlength(main_line, font=main_font) <= headline_max_w:
            break
        main_font_size -= 4
    else:
        main_font = _load_font(_FONT_BOLD, main_font_size)

    detail_raw = humanize_detail_text(spec.detail_text)
    detail_font = _load_font(_FONT_REG, 33)
    text_max = panel_right - panel_left - 72
    wrapped = wrap_text(draw, detail_raw, detail_font, text_max)
    wrapped = wrapped[:4]

    lh = int(getattr(detail_font, "size", 33) * 1.34)
    main_block_h = int(main_font_size * 1.18)
    panel_pad_v = 32
    bar_h = 72
    bar_top = CANVAS_H - bar_h - 20
    main_y = bar_top - 28 - (len(wrapped) * lh) - main_block_h - 24
    main_y = max(main_y, CANVAS_H - overlay_h + 96)
    panel_top = main_y - panel_pad_v
    panel_bottom = min(
        main_y + main_block_h + len(wrapped) * lh + panel_pad_v + 20,
        bar_top - 14,
    )
    overlay = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        [(panel_left, panel_top), (panel_right, panel_bottom)],
        radius=26,
        fill=_PANEL,
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(0.6))
    base_rgba.alpha_composite(overlay)

    draw = ImageDraw.Draw(base_rgba)

    _accent_bar(draw, bar_x, main_y + 4, main_block_h - 8)

    _soft_text_shadow(
        draw,
        (main_tx, main_y),
        main_line,
        main_font,
        _RED_HEADLINE,
        (0, 0, 0, 170),
        so=3,
    )

    y = main_y + main_block_h + 14
    for line in wrapped:
        _soft_text_shadow(draw, (panel_left + 36, y), line, detail_font, _WHITE_SOFT, (0, 0, 0, 120), so=2)
        y += lh

    draw.rectangle([(0, bar_top), (CANVAS_W, CANVAS_H - 20)], fill=_BAR_RED)

    ticker_font = _load_font(_FONT_REG, 26)
    label = spec.ticker_text.strip().upper() or "BREAKING NEWS"
    tick = f"  ·  {label}  ·  {label}  ·  "
    draw.text((32, bar_top + 22), tick, font=ticker_font, fill=(255, 255, 255, 240))

    _paste_helix_logo_top_right(base_rgba, spec)

    return base_rgba.convert("RGB")


def save_card(img: Image.Image, path: Path, quality: int = 93) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", quality=quality, optimize=True)
