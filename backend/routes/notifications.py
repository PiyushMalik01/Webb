from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..notifications_hub import hub

router = APIRouter()


@router.get("/")
async def list_notifications() -> list[dict]:
    return await hub.list_recent()


@router.websocket("/ws")
async def notifications_ws(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        while True:
            # keepalive; clients may send pings
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(ws)

