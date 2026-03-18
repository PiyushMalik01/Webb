from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..schemas import TimerStart, TimerStatus
from ..serial_manager import get_serial_manager

router = APIRouter()


@dataclass
class _TimerState:
    state: str = "idle"  # idle|running|paused
    duration_seconds: int = 0
    seconds_remaining: int = 0
    last_tick_monotonic: float = 0.0


_timer = _TimerState()
_timer_lock = asyncio.Lock()
_clients: set[WebSocket] = set()


async def _broadcast(status: TimerStatus) -> None:
    dead: list[WebSocket] = []
    for ws in _clients:
        try:
            await ws.send_json(status.model_dump())
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


def _current_status() -> TimerStatus:
    return TimerStatus(
        state=_timer.state,  # type: ignore[arg-type]
        seconds_remaining=_timer.seconds_remaining,
        duration_seconds=_timer.duration_seconds,
    )


@router.get("/status", response_model=TimerStatus)
async def get_status() -> TimerStatus:
    async with _timer_lock:
        return _current_status()


@router.post("/start", response_model=TimerStatus)
async def start_timer(payload: TimerStart) -> TimerStatus:
    async with _timer_lock:
        _timer.state = "running"
        _timer.duration_seconds = int(payload.duration_minutes) * 60
        _timer.seconds_remaining = _timer.duration_seconds
        _timer.last_tick_monotonic = time.monotonic()

    try:
        get_serial_manager().send_face("FOCUS")
    except Exception:
        pass

    status = _current_status()
    await _broadcast(status)
    return status


@router.post("/pause", response_model=TimerStatus)
async def pause_timer() -> TimerStatus:
    async with _timer_lock:
        if _timer.state == "running":
            _timer.state = "paused"
    status = _current_status()
    await _broadcast(status)
    return status


@router.post("/stop", response_model=TimerStatus)
async def stop_timer() -> TimerStatus:
    async with _timer_lock:
        _timer.state = "idle"
        _timer.duration_seconds = 0
        _timer.seconds_remaining = 0
        _timer.last_tick_monotonic = 0.0

    try:
        get_serial_manager().send_face("IDLE")
    except Exception:
        pass

    status = _current_status()
    await _broadcast(status)
    return status


async def _tick_loop() -> None:
    while True:
        await asyncio.sleep(1)
        async with _timer_lock:
            if _timer.state != "running":
                continue
            now = time.monotonic()
            elapsed = int(now - _timer.last_tick_monotonic)
            if elapsed <= 0:
                continue
            _timer.last_tick_monotonic = now
            _timer.seconds_remaining = max(0, _timer.seconds_remaining - elapsed)
            status = _current_status()

            if _timer.seconds_remaining <= 0:
                _timer.state = "idle"
                _timer.duration_seconds = 0
                _timer.last_tick_monotonic = 0.0
                # best-effort serial reset
                try:
                    get_serial_manager().send_face("IDLE")
                except Exception:
                    pass
                status = _current_status()

        await _broadcast(status)


_tick_task_started = False


@router.websocket("/ws")
async def timer_ws(ws: WebSocket) -> None:
    global _tick_task_started
    await ws.accept()
    _clients.add(ws)

    if not _tick_task_started:
        _tick_task_started = True
        asyncio.create_task(_tick_loop())

    try:
        async with _timer_lock:
            await ws.send_json(_current_status().model_dump())
        while True:
            # keepalive; we don't expect messages
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
