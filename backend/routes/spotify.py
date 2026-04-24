from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse

from ..spotify_auth import get_auth_url, exchange_code, is_authenticated
from .. import spotify_player
from ..display.spotify_renderer import set_theme, get_theme

router = APIRouter()


@router.get("/login")
def spotify_login():
    return RedirectResponse(get_auth_url())


@router.get("/callback")
def spotify_callback(code: str = "", error: str = ""):
    if error:
        return HTMLResponse(f"<h2>Auth failed: {error}</h2>")
    if not code:
        return HTMLResponse("<h2>No code received</h2>")
    exchange_code(code)
    spotify_player.start()
    return HTMLResponse(
        "<h2 style='font-family:sans-serif;color:#1DB954'>"
        "Spotify connected! You can close this tab.</h2>"
    )


@router.get("/status")
def spotify_status():
    return {
        "authenticated": is_authenticated(),
        "poller_active": spotify_player.is_active(),
    }


@router.post("/start")
def spotify_start():
    if not is_authenticated():
        return {"ok": False, "error": "Not authenticated. Visit /api/spotify/login first."}
    spotify_player.start()
    return {"ok": True}


@router.post("/stop")
def spotify_stop():
    spotify_player.stop()
    return {"ok": True}


@router.post("/theme")
def spotify_theme(theme: str = "toggle"):
    if theme == "toggle":
        theme = "light" if get_theme() == "dark" else "dark"
    if theme not in ("dark", "light"):
        return {"ok": False, "error": "Theme must be 'dark' or 'light'"}
    set_theme(theme)
    return {"ok": True, "theme": theme}


@router.get("/theme")
def spotify_theme_get():
    return {"theme": get_theme()}
