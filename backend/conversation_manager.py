from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Turn:
    role: str  # "user" or "assistant"
    content: str
    timestamp: str


class ConversationManager:
    def __init__(self, max_turns: int = 20) -> None:
        self._history: List[Turn] = []
        self._max_turns = max_turns
        self._lock = threading.Lock()

    def add_user(self, text: str) -> None:
        """Record a user message."""
        self._add(Turn(role="user", content=text, timestamp=datetime.utcnow().isoformat()))

    def add_assistant(self, text: str) -> None:
        """Record an assistant response."""
        self._add(Turn(role="assistant", content=text, timestamp=datetime.utcnow().isoformat()))

    def _add(self, turn: Turn) -> None:
        with self._lock:
            self._history.append(turn)
            if len(self._history) > self._max_turns:
                self._history = self._history[-self._max_turns:]

    def get_messages(self) -> list[dict[str, str]]:
        """Return conversation history as OpenAI-compatible messages list."""
        with self._lock:
            return [{"role": t.role, "content": t.content} for t in self._history]

    def get_last_n(self, n: int = 5) -> list[dict[str, str]]:
        """Return the last N turns."""
        with self._lock:
            return [{"role": t.role, "content": t.content} for t in self._history[-n:]]

    def clear(self) -> None:
        """Reset conversation history."""
        with self._lock:
            self._history.clear()

    @property
    def turn_count(self) -> int:
        with self._lock:
            return len(self._history)


# Global singleton
conversation = ConversationManager()
