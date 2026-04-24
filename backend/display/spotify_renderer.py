from __future__ import annotations

import io
import math
import random
from pathlib import Path
from typing import Any

import cv2
import requests
from PIL import Image, ImageDraw, ImageFont

from .renderer import DISPLAY_W, DISPLAY_H, image_to_jpeg

_art_cache: dict[str, Image.Image] = {}
_rotation_angle: float = 0.0
_frame_count: int = 0
_eq_bars: list[float] = [0.0] * 7
_eq_targets: list[float] = [0.0] * 7
_scroll_offset: int = 0
_theme: str = "dark"
_spotify_icon: Image.Image | None = None

_element_frames: list[Image.Image] | None = None
_element_index: int = 0
_element_size: tuple[int, int] = (0, 0)

_cached_vinyl: dict[str, Image.Image] = {}
_cached_album_card: dict[str, Image.Image] = {}
_el_mask_cache: dict[tuple[int, int], Image.Image] = {}

# base layer cache — static parts rendered once per track
_base_layer: Image.Image | None = None
_base_track_key: str = ""
_base_theme_key: str = ""

# layout constants
SWITCH_FRAMES = 40
ELEMENT_VIDEO = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "assets" / "playerelement.mp4"

C1_X, C1_Y, C1_SIZE, C1_PAD = 6, 6, 118, 3
C1_INNER = C1_SIZE - C1_PAD * 2


def _get_spotify_icon() -> Image.Image | None:
    global _spotify_icon
    if _spotify_icon is not None:
        return _spotify_icon
    icon_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "assets" / "spotify icon.png"
    if icon_path.exists():
        _spotify_icon = Image.open(icon_path).convert("RGBA")
    return _spotify_icon


def set_theme(theme: str) -> None:
    global _theme, _base_layer
    _theme = theme
    _base_layer = None


def get_theme() -> str:
    return _theme


def _t() -> dict:
    if _theme == "light":
        return {
            "bg": (255, 255, 255),
            "card": (20, 20, 25),
            "text": (255, 255, 255),
            "sub": (160, 160, 170),
            "dim": (120, 120, 130),
            "accent": (30, 215, 96),
            "bar_bg": (50, 50, 55),
            "vinyl_body": (35, 35, 40),
            "vinyl_groove": (45, 45, 50),
            "vinyl_rim": (55, 55, 60),
            "vinyl_hole": (20, 20, 25),
            "eq_lo": 160,
            "eq_hi": 255,
            "time": (140, 140, 150),
            "wave_bg": (50, 50, 55),
        }
    return {
        "bg": (0, 0, 0),
        "card": (235, 235, 240),
        "text": (10, 10, 10),
        "sub": (80, 80, 90),
        "dim": (110, 110, 118),
        "accent": (30, 215, 96),
        "bar_bg": (200, 200, 208),
        "vinyl_body": (210, 210, 215),
        "vinyl_groove": (195, 195, 200),
        "vinyl_rim": (180, 180, 185),
        "vinyl_hole": (235, 235, 240),
        "eq_lo": 170,
        "eq_hi": 30,
        "time": (100, 100, 110),
        "wave_bg": (200, 200, 208),
    }


def _font_bold(size: int) -> ImageFont.FreeTypeFont:
    for name in ("arialbd", "calibrib", "seguisb", "segoeui"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _font_regular(size: int) -> ImageFont.FreeTypeFont:
    for name in ("arial", "calibri", "segoeui"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


_FONT_TITLE = _font_bold(13)
_FONT_ARTIST = _font_regular(10)
_FONT_ALBUM = _font_regular(8)
_FONT_TIME = _font_regular(9)


def _fetch_art(url: str) -> Image.Image:
    if url in _art_cache:
        return _art_cache[url].copy()
    resp = requests.get(url, timeout=5)
    img = Image.open(io.BytesIO(resp.content)).convert("RGB")
    _art_cache[url] = img
    if len(_art_cache) > 20:
        oldest = next(iter(_art_cache))
        del _art_cache[oldest]
    return img.copy()


def _dominant_color(art: Image.Image) -> tuple[int, int, int]:
    small = art.convert("RGB").resize((4, 4), Image.NEAREST)
    pixels = list(small.getdata())
    r = max(60, sum(p[0] for p in pixels) // len(pixels))
    g = max(60, sum(p[1] for p in pixels) // len(pixels))
    b = max(60, sum(p[2] for p in pixels) // len(pixels))
    return (r, g, b)


def _scroll_text(text: str, font: ImageFont.FreeTypeFont, max_w: int,
                 offset: int) -> str:
    if font.getlength(text) <= max_w:
        return text
    padded = text + "     " + text
    char_w = max(font.getlength("A"), 1)
    start = int(offset / char_w) % len(padded)
    visible = padded[start:]
    while font.getlength(visible) > max_w and len(visible) > 1:
        visible = visible[:-1]
    return visible


def _update_eq_bars(is_playing: bool) -> None:
    global _eq_bars, _eq_targets
    if is_playing:
        for i in range(7):
            if random.random() > 0.5:
                _eq_targets[i] = random.uniform(0.2, 1.0)
    else:
        _eq_targets = [0.1] * 7
    for i in range(7):
        _eq_bars[i] += (_eq_targets[i] - _eq_bars[i]) * 0.3


def _draw_equalizer(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
                    theme: dict) -> None:
    bar_w = max(3, (w - 6 * 2) // 7)
    gap = 3
    for i in range(7):
        bar_h = max(3, int(h * _eq_bars[i]))
        bx = x + i * (bar_w + gap)
        by = y + h - bar_h
        t = _eq_bars[i]
        brightness = int(theme["eq_lo"] + (theme["eq_hi"] - theme["eq_lo"]) * t)
        draw.rectangle([bx, by, bx + bar_w, y + h], fill=(brightness, brightness, brightness))


def _get_vinyl(art: Image.Image | None, size: int, angle: float,
               theme: dict) -> Image.Image:
    q_angle = int(angle / 4) * 4
    key = f"{id(art)}_{size}_{q_angle}_{_theme}"
    if key in _cached_vinyl:
        return _cached_vinyl[key]

    disc = Image.new("RGB", (size, size), theme["bg"])
    draw = ImageDraw.Draw(disc)
    cx, cy = size // 2, size // 2
    r = size // 2 - 2

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=theme["vinyl_body"])
    for ring_r in range(r - 2, r // 3, -8):
        draw.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
                     outline=theme["vinyl_groove"], width=1)

    art_r = r // 2 + 6
    if art:
        art_resized = art.convert("RGB").resize((art_r * 2, art_r * 2), Image.BILINEAR)
        art_rotated = art_resized.rotate(-q_angle, resample=Image.BILINEAR, expand=False)
        mask = Image.new("L", (art_r * 2, art_r * 2), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, art_r * 2 - 1, art_r * 2 - 1], fill=255)
        disc.paste(art_rotated, (cx - art_r, cy - art_r), mask)

    draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=theme["vinyl_hole"])
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=theme["vinyl_rim"], width=1)

    if len(_cached_vinyl) > 30:
        _cached_vinyl.clear()
    _cached_vinyl[key] = disc
    return disc


def _get_album_card(art: Image.Image, size: int) -> Image.Image:
    key = f"{id(art)}_{size}"
    if key in _cached_album_card:
        return _cached_album_card[key]
    card = Image.new("RGB", (size, size), (0, 0, 0))
    art_resized = art.convert("RGB").resize((size, size), Image.BILINEAR)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size, size], radius=10, fill=255)
    card.paste(art_resized, (0, 0), mask)
    if len(_cached_album_card) > 10:
        _cached_album_card.clear()
    _cached_album_card[key] = card
    return card


def _get_el_mask(w: int, h: int) -> Image.Image:
    key = (w, h)
    if key in _el_mask_cache:
        return _el_mask_cache[key]
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=6, fill=255)
    _el_mask_cache[key] = mask
    return mask


def _load_element_frames(card_w: int, card_h: int) -> list[Image.Image]:
    cap = cv2.VideoCapture(str(ELEMENT_VIDEO))
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS)
    skip = max(1, round(fps * 0.15))
    frames: list[Image.Image] = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % skip == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            src_ratio = pil.width / pil.height
            tgt_ratio = card_w / card_h
            if src_ratio > tgt_ratio:
                new_w = int(pil.height * tgt_ratio)
                left = (pil.width - new_w) // 2
                pil = pil.crop((left, 0, left + new_w, pil.height))
            else:
                new_h = int(pil.width / tgt_ratio)
                top = (pil.height - new_h) // 2
                pil = pil.crop((0, top, pil.width, top + new_h))
            pil = pil.resize((card_w, card_h), Image.BILINEAR)
            frames.append(pil)
        idx += 1
    cap.release()
    print(f"[spotify] loaded {len(frames)} element frames")
    return frames


def _compute_layout(theme: dict) -> dict:
    """Compute all card positions once."""
    c2_x = C1_X + C1_SIZE + 5
    c2_y = C1_Y
    c2_w = DISPLAY_W - c2_x - 6
    c2_h = 68
    c3_x = c2_x
    c3_y = c2_y + c2_h + 4
    c3_w = c2_w
    c3_h = C1_SIZE - c2_h - 4
    bottom_y = C1_Y + C1_SIZE + 4
    bottom_h = DISPLAY_H - bottom_y - 6
    c5_h = bottom_h
    c5_w = max(50, int(c5_h * 0.56) + 4)
    c5_x = DISPLAY_W - c5_w - 6
    c5_y = bottom_y
    c4_x = 6
    c4_y = bottom_y
    c4_w = c5_x - c4_x - 4
    c4_h = bottom_h
    return {
        "c2": (c2_x, c2_y, c2_w, c2_h),
        "c3": (c3_x, c3_y, c3_w, c3_h),
        "c4": (c4_x, c4_y, c4_w, c4_h),
        "c5": (c5_x, c5_y, c5_w, c5_h),
        "bottom_y": bottom_y, "bottom_h": bottom_h,
        "el_pad": 2,
    }


_layout: dict | None = None


def _get_layout(theme: dict) -> dict:
    global _layout
    if _layout is None:
        _layout = _compute_layout(theme)
    return _layout


def _build_base(theme: dict, name: str, artist: str, album: str,
                art: Image.Image | None) -> Image.Image:
    """Render all static parts: background, card shapes, text, icon, album card."""
    lay = _get_layout(theme)
    img = Image.new("RGB", (DISPLAY_W, DISPLAY_H), theme["bg"])
    draw = ImageDraw.Draw(img)

    # card 1 background
    draw.rounded_rectangle(
        [C1_X, C1_Y, C1_X + C1_SIZE, C1_Y + C1_SIZE],
        radius=10, fill=theme["card"],
    )

    # card 2 — track info
    c2_x, c2_y, c2_w, c2_h = lay["c2"]
    draw.rounded_rectangle([c2_x, c2_y, c2_x + c2_w, c2_y + c2_h],
                           radius=8, fill=theme["card"])

    icon = _get_spotify_icon()
    icon_size = 30
    if icon:
        icon_resized = icon.resize((icon_size, icon_size), Image.LANCZOS)
        img.paste(icon_resized, (c2_x + c2_w - icon_size - 5, c2_y + (c2_h - icon_size) // 2), icon_resized)
        draw = ImageDraw.Draw(img)

    text_pad = 8
    text_max_w = c2_w - text_pad - icon_size - 10
    draw.text((c2_x + text_pad, c2_y + 22), name[:30],
              fill=theme["text"], font=_FONT_TITLE)
    draw.text((c2_x + text_pad, c2_y + 38), artist[:30],
              fill=theme["sub"], font=_FONT_ARTIST)
    if album:
        draw.text((c2_x + text_pad, c2_y + 53), album[:30],
                  fill=theme["dim"], font=_FONT_ALBUM)

    # card 3 background
    c3_x, c3_y, c3_w, c3_h = lay["c3"]
    draw.rounded_rectangle([c3_x, c3_y, c3_x + c3_w, c3_y + c3_h],
                           radius=8, fill=theme["card"])

    # card 5 background
    c5_x, c5_y, c5_w, c5_h = lay["c5"]
    draw.rounded_rectangle([c5_x, c5_y, c5_x + c5_w, c5_y + c5_h],
                           radius=8, fill=theme["card"])

    # card 4 background
    c4_x, c4_y, c4_w, c4_h = lay["c4"]
    draw.rounded_rectangle([c4_x, c4_y, c4_x + c4_w, c4_y + c4_h],
                           radius=8, fill=theme["card"])

    return img


def render_spotify_card(track: dict[str, Any]) -> bytes:
    global _rotation_angle, _frame_count, _scroll_offset
    global _element_frames, _element_index, _element_size
    global _base_layer, _base_track_key, _base_theme_key

    name = track.get("name", "Unknown")
    artist = track.get("artist", "Unknown")
    album = track.get("album", "")
    progress_ms = track.get("progress_ms", 0)
    duration_ms = track.get("duration_ms", 1)
    is_playing = track.get("is_playing", True)
    art_url = track.get("art_url", "")

    theme = _t()
    lay = _get_layout(theme)

    art = None
    accent = theme["accent"]
    if art_url:
        try:
            art = _fetch_art(art_url)
            accent = _dominant_color(art)
        except Exception:
            pass

    if is_playing:
        _rotation_angle = (_rotation_angle + 8) % 360
        _frame_count += 1
        _scroll_offset += 2

    _update_eq_bars(is_playing)

    # rebuild base layer only when track or theme changes
    track_key = f"{name}_{artist}_{album}_{art_url}"
    if _base_layer is None or _base_track_key != track_key or _base_theme_key != _theme:
        _base_layer = _build_base(theme, name, artist, album, art)
        _base_track_key = track_key
        _base_theme_key = _theme

    # start from cached base
    img = _base_layer.copy()
    draw = ImageDraw.Draw(img)

    # ── DYNAMIC: Card 1 content (vinyl or album art) ──
    show_vinyl = (_frame_count // SWITCH_FRAMES) % 2 == 0
    if show_vinyl:
        disc = _get_vinyl(art, C1_INNER, _rotation_angle, theme)
        img.paste(disc, (C1_X + C1_PAD, C1_Y + C1_PAD))
    elif art:
        card_art = _get_album_card(art, C1_INNER)
        img.paste(card_art, (C1_X + C1_PAD, C1_Y + C1_PAD))

    draw = ImageDraw.Draw(img)

    # ── DYNAMIC: Card 3 equalizer ──
    c3_x, c3_y, c3_w, c3_h = lay["c3"]
    draw.rounded_rectangle([c3_x, c3_y, c3_x + c3_w, c3_y + c3_h],
                           radius=8, fill=theme["card"])
    _draw_equalizer(draw, c3_x + 8, c3_y + 5, c3_w - 16, c3_h - 10, theme)

    # ── DYNAMIC: Card 5 element video ──
    c5_x, c5_y, c5_w, c5_h = lay["c5"]
    el_pad = lay["el_pad"]
    el_w = c5_w - el_pad * 2
    el_h = c5_h - el_pad * 2
    if (_element_frames is None or _element_size != (el_w, el_h)) and ELEMENT_VIDEO.exists():
        _element_frames = _load_element_frames(el_w, el_h)
        _element_size = (el_w, el_h)
    if _element_frames:
        el_frame = _element_frames[_element_index % len(_element_frames)]
        img.paste(el_frame, (c5_x + el_pad, c5_y + el_pad), _get_el_mask(el_w, el_h))
        draw = ImageDraw.Draw(img)
        if is_playing:
            _element_index += 1

    # ── DYNAMIC: Card 4 progress wave ──
    c4_x, c4_y, c4_w, c4_h = lay["c4"]
    draw.rounded_rectangle([c4_x, c4_y, c4_x + c4_w, c4_y + c4_h],
                           radius=8, fill=theme["card"])

    wave_pad = 10
    bar_y = c4_y + c4_h // 2 - 1
    bar_x0 = c4_x + wave_pad
    bar_x1 = c4_x + c4_w - wave_pad
    bar_w = bar_x1 - bar_x0

    progress = min(progress_ms / max(duration_ms, 1), 1.0)
    fill_x = bar_x0 + int(bar_w * progress)
    wave_phase = _frame_count * 0.4

    draw.line([(bar_x0, bar_y + 1), (bar_x1, bar_y + 1)], fill=theme["wave_bg"], width=2)
    if fill_x > bar_x0 + 2:
        points = []
        for x in range(bar_x0, fill_x, 2):
            amp = 3 if is_playing else 1
            wy = bar_y + int(math.sin((x - bar_x0) * 0.1 + wave_phase) * amp)
            points.append((x, wy))
        if len(points) > 1:
            draw.line(points, fill=accent, width=2)

    dot_wy = bar_y + int(math.sin((fill_x - bar_x0) * 0.1 + wave_phase) * (3 if is_playing else 1))
    draw.ellipse([fill_x - 3, dot_wy - 3, fill_x + 3, dot_wy + 3], fill=theme["text"])

    draw.text((bar_x0, bar_y + 7), _format_time(progress_ms),
              fill=theme["time"], font=_FONT_TIME)
    draw.text((bar_x1, bar_y + 7), _format_time(duration_ms),
              fill=theme["time"], font=_FONT_TIME, anchor="ra")

    return image_to_jpeg(img, quality=78)


def _format_time(ms: int) -> str:
    s = ms // 1000
    m, s = divmod(s, 60)
    return f"{m}:{s:02d}"
