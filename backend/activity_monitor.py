from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class WindowInfo:
    title: str
    process: str
    since: str  # ISO timestamp


_lock = threading.Lock()
_current: Optional[WindowInfo] = None
_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None


def _get_active_window() -> Optional[WindowInfo]:
    """Get the currently active window title and process."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return None
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        # Get process name
        import ctypes.wintypes
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        process = ""
        try:
            import psutil
            proc = psutil.Process(pid.value)
            process = proc.name()
        except Exception:
            process = f"pid:{pid.value}"

        return WindowInfo(
            title=title,
            process=process,
            since=datetime.utcnow().isoformat(),
        )
    except Exception:
        return None


def _monitor_loop() -> None:
    """Background thread that polls the active window."""
    global _current
    while not _stop_event.is_set():
        info = _get_active_window()
        if info is not None:
            with _lock:
                # Only update 'since' if the window actually changed
                if _current is None or _current.title != info.title:
                    _current = info
                else:
                    info = None  # No change
        time.sleep(2)


def start() -> None:
    """Start the activity monitor background thread."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_monitor_loop, daemon=True)
    _thread.start()


def stop() -> None:
    """Stop the activity monitor."""
    _stop_event.set()
    if _thread is not None:
        _thread.join(timeout=3.0)


def get_current_window() -> Optional[WindowInfo]:
    """Get the current active window info."""
    with _lock:
        return _current


def get_open_windows() -> list[str]:
    """Get titles of all visible windows."""
    try:
        import ctypes

        titles = []

        def _enum_callback(hwnd, _):
            user32 = ctypes.windll.user32
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.strip()
                    if title and title not in ("Program Manager",):
                        titles.append(title)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_callback), 0)
        return titles
    except Exception:
        return []


def take_screenshot_for_ai() -> str:
    """Take a screenshot and send to OpenAI Vision for description."""
    try:
        import mss
        import base64
        from openai import OpenAI

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            screenshot = sct.grab(monitor)

            # Convert to PNG bytes
            from PIL import Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.thumbnail((1024, 1024))  # Resize to save tokens

            import io
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "Cannot analyze screen: OPENAI_API_KEY not set"

        client = OpenAI(api_key=api_key, timeout=30.0)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe what you see on this screen concisely. Focus on the main application, any visible text, errors, or notable content."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }
            ],
            max_tokens=300,
        )
        return response.choices[0].message.content or "Could not describe screen"
    except Exception as e:
        return f"Screenshot analysis failed: {e}"
