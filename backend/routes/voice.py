from __future__ import annotations

from fastapi import APIRouter

from ..voice_engine import get_state, interrupt, trigger_manual

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
