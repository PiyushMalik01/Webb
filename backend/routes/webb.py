from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import FaceSet, WebbFaceResult, WebbStatus
from ..serial_manager import get_serial_manager
from .. import tts_manager

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


@router.post("/face", response_model=WebbFaceResult)
def set_face(payload: FaceSet) -> WebbFaceResult:
    try:
        get_serial_manager().send_face(payload.face)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        return WebbFaceResult(ok=False, face=payload.face, error=f"{e}")
    return WebbFaceResult(ok=True, face=payload.face, error="")


@router.post("/speak")
def speak(payload: dict) -> dict:
    """Speak text through TTS."""
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    tts_manager.speak(text)
    return {"ok": True, "text": text}


@router.post("/mode")
def set_display_mode(payload: dict) -> dict:
    """Set the display mode on ESP32."""
    mode = payload.get("mode", "FACE")
    try:
        get_serial_manager().send_mode(mode)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "mode": mode}
