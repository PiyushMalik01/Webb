from __future__ import annotations

import asyncio
from collections import deque
from concurrent.futures import Future
from typing import Any, Deque, Dict, Optional, Set

from fastapi import WebSocket


class NotificationsHub:
    def __init__(self, max_items: int = 50) -> None:
        self._clients: Set[WebSocket] = set()
        self._recent: Deque[Dict[str, Any]] = deque(maxlen=max_items)
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish_threadsafe(self, event: Dict[str, Any]) -> Optional[Future[None]]:
        if self._loop is None:
            return None
        return asyncio.run_coroutine_threadsafe(self.publish(event), self._loop)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
            recent = list(self._recent)

        for item in recent:
            await ws.send_json(item)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def publish(self, event: Dict[str, Any]) -> None:
        async with self._lock:
            self._recent.append(event)
            clients = list(self._clients)

        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    async def list_recent(self) -> list[Dict[str, Any]]:
        async with self._lock:
            return list(self._recent)


hub = NotificationsHub()

