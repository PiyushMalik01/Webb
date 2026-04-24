from __future__ import annotations

import socket
import struct
import threading
import time

import requests

from .spotify_auth import get_access_token, is_authenticated
from .display.spotify_renderer import render_spotify_card
from .display.transport import send_image, _get_esp32_host, CMD_FULL_FRAME, TCP_PORT
from .display.gif_player import is_playing as gif_is_playing
from .display import idle_player

_poll_thread: threading.Thread | None = None
_stop_event = threading.Event()
_active = False
_last_track_id: str | None = None

API_POLL_INTERVAL = 5.0
FRAME_INTERVAL = 0.15
IDLE_TIMEOUT = 10.0


def is_active() -> bool:
    return _active


def _get_currently_playing() -> dict | None:
    token = get_access_token()
    if not token:
        return None
    try:
        resp = requests.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if resp.status_code in (204, 202):
            return None
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data or not data.get("item"):
            return None

        item = data["item"]
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        images = item.get("album", {}).get("images", [])
        art_url = images[1]["url"] if len(images) > 1 else (images[0]["url"] if images else "")

        return {
            "id": item.get("id", ""),
            "name": item.get("name", "Unknown"),
            "artist": artists,
            "album": item.get("album", {}).get("name", ""),
            "art_url": art_url,
            "progress_ms": data.get("progress_ms", 0),
            "duration_ms": item.get("duration_ms", 1),
            "is_playing": data.get("is_playing", False),
            "_fetched_at": time.monotonic(),
        }
    except Exception as e:
        print(f"[spotify] API error: {e}")
        return None


def _send_persistent(sock: socket.socket, jpeg: bytes) -> None:
    header = struct.pack(">BI", CMD_FULL_FRAME, len(jpeg))
    sock.sendall(header + jpeg)
    resp = sock.recv(64).decode("utf-8", errors="ignore").strip()
    if not resp.startswith("OK"):
        raise RuntimeError(f"ESP32: {resp}")


def _connect() -> socket.socket | None:
    host = _get_esp32_host()
    if not host:
        return None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, TCP_PORT))
        return sock
    except Exception as e:
        print(f"[spotify] TCP connect failed: {e}")
        return None


def _poll_loop() -> None:
    global _active, _last_track_id
    _active = True
    last_api_poll = 0.0
    current_track: dict | None = None
    idle_since: float | None = None
    idle_video_running = False
    sock: socket.socket | None = None

    try:
        while not _stop_event.is_set():
            if gif_is_playing():
                if idle_video_running:
                    idle_player.stop()
                    idle_video_running = False
                if sock:
                    sock.close()
                    sock = None
                _stop_event.wait(2)
                continue

            now = time.monotonic()
            if now - last_api_poll >= API_POLL_INTERVAL:
                current_track = _get_currently_playing()
                last_api_poll = now

            if current_track and current_track["is_playing"]:
                if idle_video_running:
                    idle_player.stop()
                    idle_video_running = False
                idle_since = None

                elapsed_since_fetch = now - current_track["_fetched_at"]
                interpolated = dict(current_track)
                interpolated["progress_ms"] = int(
                    current_track["progress_ms"] + elapsed_since_fetch * 1000
                )
                try:
                    t0 = time.monotonic()
                    jpeg = render_spotify_card(interpolated)
                    # persistent TCP
                    if sock is None:
                        sock = _connect()
                    if sock:
                        try:
                            _send_persistent(sock, jpeg)
                        except Exception:
                            sock.close()
                            sock = _connect()
                            if sock:
                                _send_persistent(sock, jpeg)
                    else:
                        send_image(jpeg)
                    _last_track_id = current_track["id"]
                    elapsed = time.monotonic() - t0
                    remaining = FRAME_INTERVAL - elapsed
                    if remaining > 0:
                        _stop_event.wait(remaining)
                except Exception as e:
                    print(f"[spotify] render/send error: {e}")
                    _stop_event.wait(FRAME_INTERVAL)
            else:
                if idle_since is None:
                    idle_since = now

                if now - idle_since >= IDLE_TIMEOUT and not idle_video_running:
                    _last_track_id = None
                    if sock:
                        sock.close()
                        sock = None
                    idle_player.start()
                    idle_video_running = True

                if idle_video_running:
                    _stop_event.wait(3)
                else:
                    if current_track:
                        try:
                            jpeg = render_spotify_card(current_track)
                            if sock is None:
                                sock = _connect()
                            if sock:
                                try:
                                    _send_persistent(sock, jpeg)
                                except Exception:
                                    sock.close()
                                    sock = _connect()
                                    if sock:
                                        _send_persistent(sock, jpeg)
                            else:
                                send_image(jpeg)
                        except Exception:
                            pass
                    _stop_event.wait(FRAME_INTERVAL)
    finally:
        if sock:
            sock.close()
        if idle_video_running:
            idle_player.stop()
        _active = False


def start() -> None:
    global _poll_thread
    if _poll_thread and _poll_thread.is_alive():
        return
    if not is_authenticated():
        print("[spotify] not authenticated, skipping start")
        return
    _stop_event.clear()
    _poll_thread = threading.Thread(target=_poll_loop, daemon=True)
    _poll_thread.start()
    print("[spotify] poller started")


def stop() -> None:
    global _poll_thread
    _stop_event.set()
    idle_player.stop()
    if _poll_thread and _poll_thread.is_alive():
        _poll_thread.join(timeout=3)
    _poll_thread = None
    print("[spotify] poller stopped")
