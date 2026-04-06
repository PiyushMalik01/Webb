from __future__ import annotations

import ctypes
import json
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

from . import action_registry

APP_REGISTRY_PATH = Path(__file__).parent / "app_registry.json"


def _load_app_registry() -> dict[str, str]:
    try:
        with open(APP_REGISTRY_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_app_registry(registry: dict[str, str]) -> None:
    with open(APP_REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def _fuzzy_match(name: str, registry: dict[str, str]) -> Optional[str]:
    name_lower = name.lower().strip()
    # Exact match
    if name_lower in registry:
        return registry[name_lower]
    # Substring match
    for key, val in registry.items():
        if name_lower in key or key in name_lower:
            return val
    return None


# ── App Launcher ──────────────────────────────────────────────

def launch_app(app_name: str) -> str:
    registry = _load_app_registry()
    exe = _fuzzy_match(app_name, registry)
    if exe is None:
        return f"I don't know the app '{app_name}'. You can add it in Settings."

    try:
        if exe.startswith("ms-"):
            os.startfile(exe)
        else:
            subprocess.Popen(exe, shell=True)
        return f"Opening {app_name}"
    except Exception as e:
        return f"Failed to open {app_name}: {e}"


def add_app(app_name: str, path: str) -> str:
    registry = _load_app_registry()
    registry[app_name.lower().strip()] = path.strip()
    _save_app_registry(registry)
    return f"Registered {app_name} at {path}"


def list_apps() -> str:
    registry = _load_app_registry()
    if not registry:
        return "No apps registered."
    return "Known apps: " + ", ".join(sorted(registry.keys()))


# ── Window Management ─────────────────────────────────────────

def switch_to(app_name: str) -> str:
    try:
        import ctypes
        user32 = ctypes.windll.user32

        target = app_name.lower()
        found_hwnd = None

        def _callback(hwnd, _):
            nonlocal found_hwnd
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value.lower()
                    if target in title:
                        found_hwnd = hwnd
                        return False  # Stop enumeration
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(_callback), 0)

        if found_hwnd:
            user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(found_hwnd)
            return f"Switched to {app_name}"
        return f"No window found for '{app_name}'"
    except Exception as e:
        return f"Failed to switch window: {e}"


def minimize_active() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("win", "down")
        return "Window minimized"
    except Exception as e:
        return f"Failed: {e}"


def maximize_active() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("win", "up")
        return "Window maximized"
    except Exception as e:
        return f"Failed: {e}"


def close_active() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("alt", "F4")
        return "Window closed"
    except Exception as e:
        return f"Failed: {e}"


def show_desktop() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("win", "d")
        return "Showing desktop"
    except Exception as e:
        return f"Failed: {e}"


# ── Volume / Media ────────────────────────────────────────────

def set_volume(action: str) -> str:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))

        action = action.lower().strip()
        current = volume.GetMasterVolumeLevelScalar()

        if action in ("up", "increase"):
            volume.SetMasterVolumeLevelScalar(min(1.0, current + 0.1), None)
            return f"Volume up to {int(min(1.0, current + 0.1) * 100)}%"
        elif action in ("down", "decrease"):
            volume.SetMasterVolumeLevelScalar(max(0.0, current - 0.1), None)
            return f"Volume down to {int(max(0.0, current - 0.1) * 100)}%"
        elif action in ("mute", "unmute", "toggle"):
            muted = volume.GetMute()
            volume.SetMute(not muted, None)
            return "Unmuted" if muted else "Muted"
        else:
            # Try to parse as a percentage
            try:
                pct = int(action.replace("%", ""))
                volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, pct / 100)), None)
                return f"Volume set to {pct}%"
            except ValueError:
                return f"Unknown volume action: {action}"
    except Exception as e:
        return f"Volume control failed: {e}"


def media_control(action: str) -> str:
    try:
        import pyautogui
        action = action.lower().strip()
        if action in ("play", "pause", "playpause"):
            pyautogui.press("playpause")
            return "Play/pause toggled"
        elif action in ("next", "skip"):
            pyautogui.press("nexttrack")
            return "Next track"
        elif action in ("previous", "prev", "back"):
            pyautogui.press("prevtrack")
            return "Previous track"
        elif action in ("stop",):
            pyautogui.press("stop")
            return "Media stopped"
        else:
            return f"Unknown media action: {action}"
    except Exception as e:
        return f"Media control failed: {e}"


# ── System Actions ────────────────────────────────────────────

def take_screenshot() -> str:
    try:
        import mss
        from PIL import Image

        screenshots_dir = Path.home() / "Pictures" / "Screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        from datetime import datetime
        filename = f"webb_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = screenshots_dir / filename
        img.save(str(filepath))
        return f"Screenshot saved to {filepath}"
    except Exception as e:
        return f"Screenshot failed: {e}"


def lock_screen() -> str:
    try:
        ctypes.windll.user32.LockWorkStation()
        return "Screen locked"
    except Exception as e:
        return f"Lock failed: {e}"


def set_brightness(action: str) -> str:
    try:
        import subprocess
        action = action.lower().strip()

        # Get current brightness via PowerShell
        result = subprocess.run(
            ["powershell", "-Command", "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"],
            capture_output=True, text=True, timeout=5
        )
        current = int(result.stdout.strip()) if result.stdout.strip() else 50

        if action in ("up", "increase"):
            new_val = min(100, current + 10)
        elif action in ("down", "decrease"):
            new_val = max(0, current - 10)
        else:
            try:
                new_val = max(0, min(100, int(action.replace("%", ""))))
            except ValueError:
                return f"Unknown brightness action: {action}"

        subprocess.run(
            ["powershell", "-Command", f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {new_val})"],
            capture_output=True, timeout=5
        )
        return f"Brightness set to {new_val}%"
    except Exception as e:
        return f"Brightness control failed: {e}"


# ── Web & Search ──────────────────────────────────────────────

def web_search(query: str) -> str:
    try:
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return f"Searching for: {query}"
    except Exception as e:
        return f"Search failed: {e}"


def open_url(url: str) -> str:
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        return f"Opening {url}"
    except Exception as e:
        return f"Failed to open URL: {e}"


# ── Typing & Dictation ───────────────────────────────────────

def type_text(text: str) -> str:
    try:
        import pyautogui
        import time
        time.sleep(0.3)  # Small delay to ensure target window is focused
        pyautogui.write(text, interval=0.02)
        return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"
    except Exception as e:
        return f"Typing failed: {e}"


# ── File Operations ───────────────────────────────────────────

KNOWN_FOLDERS = {
    "downloads": Path.home() / "Downloads",
    "documents": Path.home() / "Documents",
    "desktop": Path.home() / "Desktop",
    "pictures": Path.home() / "Pictures",
    "music": Path.home() / "Music",
    "videos": Path.home() / "Videos",
}


def open_folder(name: str) -> str:
    name_lower = name.lower().strip()
    folder = KNOWN_FOLDERS.get(name_lower)
    if folder is None:
        # Try as a direct path
        p = Path(name)
        if p.is_dir():
            folder = p
        else:
            return f"Unknown folder: {name}"
    try:
        os.startfile(str(folder))
        return f"Opened {folder.name}"
    except Exception as e:
        return f"Failed to open folder: {e}"


def open_file(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"File not found: {path}"
        os.startfile(str(p))
        return f"Opened {p.name}"
    except Exception as e:
        return f"Failed to open file: {e}"


# ── Registration ──────────────────────────────────────────────

def register_all_actions() -> None:
    """Register all system actions in the action registry."""
    r = action_registry.register

    # App management
    r("launch_app", "Open an application by name (e.g. Chrome, VS Code, Spotify)", ["app_name"], launch_app, "apps")
    r("add_app", "Register a new application with its path", ["app_name", "path"], add_app, "apps")
    r("list_apps", "List all known applications", [], lambda: list_apps(), "apps")

    # Window management
    r("switch_to", "Switch to an open window by name", ["app_name"], switch_to, "windows")
    r("minimize", "Minimize the active window", [], lambda: minimize_active(), "windows")
    r("maximize", "Maximize the active window", [], lambda: maximize_active(), "windows")
    r("close_window", "Close the active window", [], lambda: close_active(), "windows")
    r("show_desktop", "Show the desktop (minimize all)", [], lambda: show_desktop(), "windows")

    # Volume & media
    r("volume", "Control volume: up, down, mute, unmute, or a percentage", ["action"], set_volume, "system")
    r("media", "Control media playback: play, pause, next, previous, stop", ["action"], media_control, "system")

    # System
    r("screenshot", "Take a screenshot and save to Pictures/Screenshots", [], lambda: take_screenshot(), "system")
    r("lock_screen", "Lock the computer screen", [], lambda: lock_screen(), "system")
    r("brightness", "Control screen brightness: up, down, or a percentage", ["action"], set_brightness, "system")

    # Web
    r("web_search", "Search Google for a query", ["query"], web_search, "web")
    r("open_url", "Open a URL in the browser", ["url"], open_url, "web")

    # Typing
    r("type_text", "Type text into the active window", ["text"], type_text, "input")

    # Files
    r("open_folder", "Open a folder (Downloads, Documents, Desktop, etc.)", ["name"], open_folder, "files")
    r("open_file", "Open a file by its path", ["path"], open_file, "files")
