from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from pynput import keyboard, mouse

from .ai_manager import generate_idle_nudge
from .notifications_hub import hub
from .serial_manager import get_serial_manager


class IdleManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_activity = time.time()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None
        self._cooldown_until = 0.0

    def mark_activity(self) -> None:
        with self._lock:
            self._last_activity = time.time()

    def start(self) -> None:
        if os.getenv("IDLE_DISABLED") == "1":
            return
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        # start input listeners (non-blocking)
        self._keyboard_listener = keyboard.Listener(
            on_press=lambda _: self.mark_activity(),
            on_release=lambda _: self.mark_activity(),
        )
        self._keyboard_listener.start()

        self._mouse_listener = mouse.Listener(
            on_move=lambda *_: self.mark_activity(),
            on_click=lambda *_: self.mark_activity(),
            on_scroll=lambda *_: self.mark_activity(),
        )
        self._mouse_listener.start()

    def stop(self) -> None:
        self._stop.set()

        if self._keyboard_listener is not None:
            try:
                self._keyboard_listener.stop()
            except Exception:
                pass
            self._keyboard_listener = None

        if self._mouse_listener is not None:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def _run(self) -> None:
        threshold_mins = int(os.getenv("IDLE_THRESHOLD_MINS", "20"))
        threshold_s = max(60, threshold_mins * 60)
        cooldown_s = int(os.getenv("IDLE_COOLDOWN_SECS", "600"))

        while not self._stop.is_set():
            now = time.time()
            with self._lock:
                idle_for = now - self._last_activity
                cooldown_until = self._cooldown_until

            if idle_for >= threshold_s and now >= cooldown_until:
                text = generate_idle_nudge()

                try:
                    get_serial_manager().send_face("REMINDER")
                except Exception:
                    pass

                event = {
                    "type": "idle_nudge",
                    "text": text,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

                fut = hub.publish_threadsafe(event)
                if fut is not None:
                    try:
                        fut.result(timeout=2.0)
                    except Exception:
                        pass

                with self._lock:
                    self._cooldown_until = time.time() + cooldown_s

            time.sleep(2)


idle_manager = IdleManager()

