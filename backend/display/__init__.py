from __future__ import annotations

from .renderer import render_test_card, image_to_jpeg
from .transport import send_image


def push_test_image() -> int:
    """Render a test card, convert to JPEG, push to ESP32. Returns JPEG size."""
    img = render_test_card()
    jpeg = image_to_jpeg(img)
    send_image(jpeg)
    return len(jpeg)
