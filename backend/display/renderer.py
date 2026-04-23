from __future__ import annotations

import io
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

DISPLAY_W = 320
DISPLAY_H = 240


def render_test_card() -> Image.Image:
    """Generate a 320x240 test card with gradient, text, and timestamp."""
    img = Image.new("RGB", (DISPLAY_W, DISPLAY_H))
    draw = ImageDraw.Draw(img)

    for y in range(DISPLAY_H):
        r = int(20 + (y / DISPLAY_H) * 40)
        g = int(10 + (y / DISPLAY_H) * 30)
        b = int(60 + (y / DISPLAY_H) * 120)
        draw.line([(0, y), (DISPLAY_W, y)], fill=(r, g, b))

    try:
        font_large = ImageFont.truetype("arial", 28)
        font_small = ImageFont.truetype("arial", 16)
    except OSError:
        font_large = ImageFont.load_default()
        font_small = font_large

    draw.text(
        (DISPLAY_W // 2, 80),
        "WEBB DISPLAY",
        fill=(255, 255, 255),
        font=font_large,
        anchor="mm",
    )

    draw.text(
        (DISPLAY_W // 2, 120),
        f"{DISPLAY_W}x{DISPLAY_H} JPEG Transport",
        fill=(180, 180, 180),
        font=font_small,
        anchor="mm",
    )

    timestamp = datetime.now().strftime("%H:%M:%S")
    draw.text(
        (DISPLAY_W // 2, 160),
        timestamp,
        fill=(100, 200, 255),
        font=font_small,
        anchor="mm",
    )

    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]):
        x = 30 + i * 45
        draw.rectangle([x, 200, x + 35, 225], fill=color)

    return img


def image_to_jpeg(img: Image.Image, quality: int = 60) -> bytes:
    """Convert a PIL Image to JPEG bytes."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def resize_for_display(img: Image.Image) -> Image.Image:
    """Resize and crop any image to 320x240, maintaining aspect ratio."""
    target_ratio = DISPLAY_W / DISPLAY_H
    src_ratio = img.width / img.height

    if src_ratio > target_ratio:
        new_h = img.height
        new_w = int(new_h * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, new_h))
    elif src_ratio < target_ratio:
        new_w = img.width
        new_h = int(new_w / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, new_w, top + new_h))

    return img.resize((DISPLAY_W, DISPLAY_H), Image.LANCZOS)
