from __future__ import annotations

from fastapi import APIRouter

from ..voice_manager import capture_and_process_once

router = APIRouter()


@router.post("/once")
def voice_once() -> dict:
    """
    Trigger a one-shot voice capture and intent execution.
    """
    summary = capture_and_process_once()
    return summary


@router.get("/status")
def voice_status() -> dict:
    # Reserved for future wake-word support.
    return {"listening": False}

