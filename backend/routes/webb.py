from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import FaceSet, WebbStatus
from ..serial_manager import get_serial_manager

router = APIRouter()


@router.get("/status", response_model=WebbStatus)
def webb_status() -> WebbStatus:
    s = get_serial_manager().get_status()
    return WebbStatus(
        connected=s.connected,
        port=s.port,
        baud=s.baud,
        last_face=s.last_face,
        last_error=s.last_error,
    )


@router.post("/face")
def set_face(payload: FaceSet) -> dict[str, str]:
    try:
        get_serial_manager().send_face(payload.face)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # Surface error in response but do not fail the request
        return {"ok": "false", "face": payload.face, "error": f"{e}"}
    return {"ok": "true", "face": payload.face, "error": ""}


@router.post("/speak")
def speak_stub() -> None:
    raise HTTPException(status_code=501, detail="TTS not implemented in MVP")

