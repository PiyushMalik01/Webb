from __future__ import annotations

import asyncio
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from pynput import keyboard, mouse

from .ai_manager import parse_intent
from .notifications_hub import hub
from .serial_manager import get_serial_manager


class IdleManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_activity = time.time()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
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
        keyboard.Listener(on_press=lambda _: self.mark_activity(), on_release=lambda _: self.mark_activity()).start()
        mouse.Listener(
            on_move=lambda *_: self.mark_activity(),
            on_click=lambda *_: self.mark_activity(),
            on_scroll=lambda *_: self.mark_activity(),
        ).start()

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
                # Generate a short motivational nudge via LLM.
                # We reuse parse_intent with a general_chat-ish prompt to keep code small.
                # If OPENAI_API_KEY is missing, parse_intent falls back safely.
                prompt = "Generate a short motivational nudge (1 sentence) to help me get back to work."
                intent = parse_intent(prompt)
                text = str(intent.get("response") or "Ready to get back to it?")

                try:
                    get_serial_manager().send_face("REMINDER")
                except Exception:
                    pass

                event = {
                    "type": "idle_nudge",
                    "text": text,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

                try:
                    asyncio.run(hub.publish(event))
                except RuntimeError:
                    # If an event loop already exists in this thread (unlikely), skip.
                    pass

                with self._lock:
                    self._cooldown_until = time.time() + cooldown_s

            time.sleep(2)


idle_manager = IdleManager()

