from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

TOKEN_FILE = Path(__file__).parent.parent / ".spotify_token.json"
SCOPES = "user-read-currently-playing user-read-playback-state"


def _creds() -> tuple[str, str, str]:
    cid = os.getenv("SPOTIFY_CLIENT_ID", "")
    secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    redirect = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8000/api/spotify/callback")
    if not cid or not secret:
        raise RuntimeError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET required")
    return cid, secret, redirect


def get_auth_url() -> str:
    cid, _, redirect = _creds()
    params = {
        "client_id": cid,
        "response_type": "code",
        "redirect_uri": redirect,
        "scope": SCOPES,
        "show_dialog": "true",
    }
    return "https://accounts.spotify.com/authorize?" + urlencode(params)


def exchange_code(code: str) -> dict:
    cid, secret, redirect = _creds()
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect,
        },
        auth=(cid, secret),
        timeout=10,
    )
    resp.raise_for_status()
    token_data = resp.json()
    token_data["obtained_at"] = time.time()
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    return token_data


def _refresh_token(refresh_token: str) -> dict:
    cid, secret, _ = _creds()
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        auth=(cid, secret),
        timeout=10,
    )
    resp.raise_for_status()
    token_data = resp.json()
    token_data["obtained_at"] = time.time()
    if "refresh_token" not in token_data:
        token_data["refresh_token"] = refresh_token
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    return token_data


def get_access_token() -> str | None:
    if not TOKEN_FILE.exists():
        return None
    data = json.loads(TOKEN_FILE.read_text())
    expires_in = data.get("expires_in", 3600)
    obtained_at = data.get("obtained_at", 0)
    if time.time() > obtained_at + expires_in - 60:
        refresh = data.get("refresh_token")
        if not refresh:
            return None
        data = _refresh_token(refresh)
    return data.get("access_token")


def is_authenticated() -> bool:
    return get_access_token() is not None
