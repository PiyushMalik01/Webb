from __future__ import annotations

import socket
import struct
import threading
import time
from typing import List, Tuple

from PIL import Image

from .renderer import resize_for_display, image_to_jpeg
from .transport import _get_esp32_host, CMD_FULL_FRAME, TCP_PORT, send_image

TARGET_FRAME_MS = 100
GIF_JPEG_QUALITY = 35

_lock = threading.Lock()
_stop_event = threading.Event()
_current_thread: threading.Thread | None = None
_playing = False


def is_playing() -> bool:
    return _playing


def extract_gif_frames(img: Image.Image) -> List[Tuple[Image.Image, float]]:
    """Extract frames from a GIF, skipping frames to match achievable FPS."""
    raw_frames: List[Tuple[Image.Image, int]] = []
    try:
        while True:
            duration_ms = img.info.get("duration", 100)
            if duration_ms < 20:
                duration_ms = 100
            frame = img.convert("RGB")
            raw_frames.append((frame, duration_ms))
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    if not raw_frames:
        return []

    avg_duration = sum(d for _, d in raw_frames) / len(raw_frames)
    skip = max(1, round(TARGET_FRAME_MS / avg_duration))

    frames: List[Tuple[Image.Image, float]] = []
    for i in range(0, len(raw_frames), skip):
        frame_img, _ = raw_frames[i]
        frame_img = resize_for_display(frame_img)
        delay = sum(d for _, d in raw_frames[i:i + skip]) / 1000.0
        frames.append((frame_img, delay))

    return frames


def _send_frame_persistent(sock: socket.socket, jpeg: bytes) -> None:
    header = struct.pack(">BI", CMD_FULL_FRAME, len(jpeg))
    sock.sendall(header + jpeg)
    resp = sock.recv(64).decode("utf-8", errors="ignore").strip()
    if not resp.startswith("OK"):
        raise RuntimeError(f"ESP32: {resp}")


def _playback_loop(frames: List[Tuple[bytes, float]], loops: int) -> None:
    global _playing
    _playing = True
    try:
        host = _get_esp32_host()
        if not host:
            print("[gif] no ESP32 host found, falling back to per-frame transport")
            _playback_loop_fallback(frames, loops)
            return

        iteration = 0
        while not _stop_event.is_set():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            try:
                sock.connect((host, TCP_PORT))
                for i, (jpeg, delay) in enumerate(frames):
                    if _stop_event.is_set():
                        return
                    t0 = time.monotonic()
                    try:
                        _send_frame_persistent(sock, jpeg)
                    except Exception as e:
                        print(f"[gif] connection lost at frame {i+1}, reconnecting: {e}")
                        sock.close()
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(5.0)
                        sock.connect((host, TCP_PORT))
                        _send_frame_persistent(sock, jpeg)
                    elapsed = time.monotonic() - t0
                    remaining = delay - elapsed
                    if remaining > 0 and not _stop_event.is_set():
                        _stop_event.wait(remaining)
            except Exception as e:
                print(f"[gif] TCP connect failed: {e}")
                return
            finally:
                sock.close()
            iteration += 1
            if loops > 0 and iteration >= loops:
                return
    finally:
        _playing = False


def _playback_loop_fallback(frames: List[Tuple[bytes, float]], loops: int) -> None:
    iteration = 0
    while not _stop_event.is_set():
        for jpeg, delay in frames:
            if _stop_event.is_set():
                return
            try:
                send_image(jpeg)
            except Exception as e:
                print(f"[gif] frame send failed: {e}")
                return
            _stop_event.wait(delay)
            if _stop_event.is_set():
                return
        iteration += 1
        if loops > 0 and iteration >= loops:
            return


def stop_gif() -> None:
    global _current_thread
    _stop_event.set()
    with _lock:
        if _current_thread and _current_thread.is_alive():
            _current_thread.join(timeout=3)
        _current_thread = None


def play_gif(img: Image.Image, loops: int = 0) -> dict:
    global _current_thread

    stop_gif()

    frames_raw = extract_gif_frames(img)
    if not frames_raw:
        raise ValueError("GIF has no frames")

    jpeg_frames: List[Tuple[bytes, float]] = []
    total_size = 0
    for frame_img, delay in frames_raw:
        jpeg = image_to_jpeg(frame_img, quality=GIF_JPEG_QUALITY)
        jpeg_frames.append((jpeg, delay))
        total_size += len(jpeg)

    _stop_event.clear()
    t = threading.Thread(
        target=_playback_loop,
        args=(jpeg_frames, loops),
        daemon=True,
    )
    t.start()

    with _lock:
        _current_thread = t

    return {
        "frame_count": len(jpeg_frames),
        "avg_frame_bytes": total_size // len(jpeg_frames),
        "total_bytes": total_size,
    }
