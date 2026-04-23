from __future__ import annotations

from fastapi import APIRouter, UploadFile, File

from ..display import push_test_image
from ..display.renderer import image_to_jpeg, resize_for_display
from ..display.transport import send_image

router = APIRouter()


@router.post("/test")
def display_test() -> dict:
    """Render a test card and push to ESP32."""
    try:
        size = push_test_image()
        return {"ok": True, "size_bytes": size}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/push")
async def display_push(file: UploadFile = File(...)) -> dict:
    """Accept an image upload, resize to 320x240, push as JPEG."""
    try:
        from PIL import Image
        import io

        data = await file.read()
        img = Image.open(io.BytesIO(data))
        img = resize_for_display(img)
        jpeg = image_to_jpeg(img)
        send_image(jpeg)
        return {"ok": True, "size_bytes": len(jpeg)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
