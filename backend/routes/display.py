from __future__ import annotations

import io

from fastapi import APIRouter, UploadFile, File
from PIL import Image

from ..display import push_test_image
from ..display.renderer import image_to_jpeg, resize_for_display
from ..display.transport import send_image
from ..display.gif_player import play_gif, stop_gif

router = APIRouter()


@router.post("/test")
def display_test() -> dict:
    """Render a test card and push to ESP32."""
    try:
        stop_gif()
        size = push_test_image()
        return {"ok": True, "size_bytes": size}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/push")
async def display_push(file: UploadFile = File(...)) -> dict:
    """Accept an image upload or GIF, push to ESP32."""
    try:
        data = await file.read()
        img = Image.open(io.BytesIO(data))

        if getattr(img, "is_animated", False):
            stop_gif()
            info = play_gif(img)
            return {"ok": True, "gif": True, **info}

        stop_gif()
        img = resize_for_display(img)
        jpeg = image_to_jpeg(img)
        send_image(jpeg)
        return {"ok": True, "gif": False, "size_bytes": len(jpeg)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/stop")
def display_stop() -> dict:
    """Stop any running GIF playback."""
    stop_gif()
    return {"ok": True}
