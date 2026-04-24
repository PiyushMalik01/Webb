from __future__ import annotations

from fastapi import APIRouter

from ..voice_engine import get_state, interrupt, trigger_manual, is_listening_paused, pause_listening, resume_listening

router = APIRouter()


@router.post("/once")
def voice_once() -> dict:
    """Trigger a one-shot voice capture via mic button."""
    return trigger_manual()


@router.get("/status")
def voice_status() -> dict:
    """Return current voice engine state."""
    return {"state": get_state().value}


@router.post("/interrupt")
def voice_interrupt() -> dict:
    """Interrupt current voice processing/speech."""
    interrupt()
    return {"ok": True}


@router.get("/listening")
def voice_listening_status() -> dict:
    """Return whether passive listening is active."""
    return {"listening": not is_listening_paused()}


@router.post("/listening")
def voice_listening_toggle(body: dict = {}) -> dict:
    """Toggle or set passive listening. Send {"listening": true/false} or omit to toggle."""
    if "listening" in body:
        if body["listening"]:
            resume_listening()
        else:
            pause_listening()
    else:
        if is_listening_paused():
            resume_listening()
        else:
            pause_listening()
    return {"listening": not is_listening_paused()}
