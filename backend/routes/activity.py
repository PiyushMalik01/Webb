from __future__ import annotations

from fastapi import APIRouter

from ..activity_monitor import get_current_window, get_open_windows, take_screenshot_for_ai

router = APIRouter()


@router.get("/current")
def current_activity() -> dict:
    """Get the currently active window."""
    window = get_current_window()
    if window is None:
        return {"title": "unknown", "process": "unknown", "since": ""}
    return {"title": window.title, "process": window.process, "since": window.since}


@router.get("/windows")
def open_windows() -> dict:
    """List all open windows."""
    return {"windows": get_open_windows()}


@router.post("/screenshot")
def screenshot_context() -> dict:
    """Take a screenshot and get AI description."""
    description = take_screenshot_for_ai()
    return {"description": description}
