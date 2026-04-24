from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import List, Tuple

import cv2
from PIL import Image

from .renderer import resize_for_display, image_to_jpeg
from .transport import send_image
from .gif_player import is_playing as gif_is_playing

IDLE_VIDEO = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "assets" / "idlestate.mp4"
FRAME_INTERVAL = 0.12
JPEG_QUALITY = 80

_lock = threading.Lock()
_stop_event = threading.Event()
_thread: threading.Thread | None = None
_playing = False
_frames: List[bytes] | None = None


def is_playing() -> bool:
    return _playing


def _extract_frames() -> List[bytes]:
    cap = cv2.VideoCapture(str(IDLE_VIDEO))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {IDLE_VIDEO}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    skip = max(1, round(fps * FRAME_INTERVAL))

    frames: List[bytes] = []
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % skip == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            # fit inside 320x240 with black letterbox
            pil_img.thumbnail((320, 240), Image.LANCZOS)
            canvas = Image.new("RGB", (320, 240), (0, 0, 0))
            ox = (320 - pil_img.width) // 2
            oy = (240 - pil_img.height) // 2
            canvas.paste(pil_img, (ox, oy))
            jpeg = image_to_jpeg(canvas, quality=JPEG_QUALITY)
            frames.append(jpeg)
        idx += 1

    cap.release()
    print(f"[idle] extracted {len(frames)} frames from {idx} total (skip={skip})")
    return frames


def _playback_loop() -> None:
    global _playing, _frames
    _playing = True
    try:
        if _frames is None:
            _frames = _extract_frames()
        if not _frames:
            return

        while not _stop_event.is_set():
            for jpeg in _frames:
                if _stop_event.is_set():
                    return
                if gif_is_playing():
                    _stop_event.wait(1)
                    continue
                try:
                    send_image(jpeg)
                except Exception as e:
                    print(f"[idle] send error: {e}")
                    return
                _stop_event.wait(FRAME_INTERVAL)
    finally:
        _playing = False


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    if not IDLE_VIDEO.exists():
        print(f"[idle] video not found: {IDLE_VIDEO}")
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_playback_loop, daemon=True)
    _thread.start()
    print("[idle] player started")


def stop() -> None:
    global _thread
    _stop_event.set()
    with _lock:
        if _thread and _thread.is_alive():
            _thread.join(timeout=3)
        _thread = None
