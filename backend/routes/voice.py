from __future__ import annotations

from fastapi import APIRouter

from ..schemas import VoiceOnceOut
from ..voice_manager import capture_and_process_once

router = APIRouter()


@router.post("/once", response_model=VoiceOnceOut)
def voice_once() -> VoiceOnceOut:
    """
    Trigger a one-shot voice capture and intent execution.
    """
    return VoiceOnceOut(**capture_and_process_once())


@router.get("/status")
def voice_status() -> dict:
    # Reserved for future wake-word support.
    return {"listening": False}

