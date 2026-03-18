from __future__ import annotations

import asyncio
from collections import deque
from typing import Any, Deque, Dict, Set

from fastapi import WebSocket


class NotificationsHub:
    def __init__(self, max_items: int = 50) -> None:
        self._clients: Set[WebSocket] = set()
        self._recent: Deque[Dict[str, Any]] = deque(maxlen=max_items)
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
            for item in list(self._recent):
                await ws.send_json(item)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def publish(self, event: Dict[str, Any]) -> None:
        async with self._lock:
            self._recent.append(event)
            dead: list[WebSocket] = []
            for ws in self._clients:
                try:
                    await ws.send_json(event)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)

    async def list_recent(self) -> list[Dict[str, Any]]:
        async with self._lock:
            return list(self._recent)


hub = NotificationsHub()

