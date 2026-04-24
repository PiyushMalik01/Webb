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
    """Control volume using keyboard simulation (works reliably on all Windows)."""
    try:
        import pyautogui
        action = action.lower().strip()

        if action in ("up", "increase"):
            pyautogui.press("volumeup", presses=3)
            return "Volume up"
        elif action in ("down", "decrease"):
            pyautogui.press("volumedown", presses=3)
            return "Volume down"
        elif action in ("mute", "unmute", "toggle"):
            pyautogui.press("volumemute")
            return "Volume mute toggled"
        else:
            try:
                pct = int(action.replace("%", ""))
                # Set to specific level: mute first, then press up proportionally
                pyautogui.press("volumemute")
                time.sleep(0.1)
                pyautogui.press("volumemute")  # Unmute
                presses = pct // 2  # Each press is ~2%
                pyautogui.press("volumeup", presses=presses, interval=0.02)
                return f"Volume set to ~{pct}%"
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


# ── Keyboard ─────────────────────────────────────────────────

def press_key(keys: str) -> str:
    try:
        import pyautogui
        parts = [k.strip() for k in keys.lower().replace("+", " ").split()]
        if len(parts) == 1:
            pyautogui.press(parts[0])
        else:
            pyautogui.hotkey(*parts)
        return f"Pressed {keys}"
    except Exception as e:
        return f"Key press failed: {e}"


# ── Registration ──────────────────────────────────────────────

def register_all_actions() -> None:
    """Register all system actions in the action registry."""
    r = action_registry.register

    # App management
    r("launch_app", "Open an application by name (e.g. Chrome, VS Code, Spotify)",
      {"type": "object", "properties": {
          "app_name": {"type": "string", "description": "Name of the app to launch"}
      }, "required": ["app_name"]},
      launch_app, "green", "apps")

    r("add_app", "Register a new application with its executable path",
      {"type": "object", "properties": {
          "app_name": {"type": "string", "description": "Friendly name for the app"},
          "path": {"type": "string", "description": "Executable path or ms- protocol URI"}
      }, "required": ["app_name", "path"]},
      add_app, "green", "apps")

    r("list_apps", "List all known applications",
      {"type": "object", "properties": {}},
      lambda: list_apps(), "green", "apps")

    # Window management
    r("switch_to", "Switch to an open window by name",
      {"type": "object", "properties": {
          "app_name": {"type": "string", "description": "Title or name of the window to switch to"}
      }, "required": ["app_name"]},
      switch_to, "green", "windows")

    r("minimize", "Minimize the active window",
      {"type": "object", "properties": {}},
      lambda: minimize_active(), "green", "windows")

    r("maximize", "Maximize the active window",
      {"type": "object", "properties": {}},
      lambda: maximize_active(), "green", "windows")

    r("close_window", "Close the active window",
      {"type": "object", "properties": {}},
      lambda: close_active(), "green", "windows")

    r("show_desktop", "Show the desktop (minimize all windows)",
      {"type": "object", "properties": {}},
      lambda: show_desktop(), "green", "windows")

    # Volume & media
    r("volume", "Control volume: up, down, mute, unmute, or a percentage",
      {"type": "object", "properties": {
          "action": {"type": "string", "description": "Volume action: up, down, mute, unmute, or a percentage like 50"}
      }, "required": ["action"]},
      set_volume, "green", "system")

    r("media", "Control media playback: play, pause, next, previous, stop",
      {"type": "object", "properties": {
          "action": {"type": "string", "description": "Media action: play, pause, next, previous, or stop"}
      }, "required": ["action"]},
      media_control, "green", "system")

    # System
    r("screenshot", "Take a screenshot and save to Pictures/Screenshots",
      {"type": "object", "properties": {}},
      lambda: take_screenshot(), "green", "system")

    r("lock_screen", "Lock the computer screen",
      {"type": "object", "properties": {}},
      lambda: lock_screen(), "green", "system")

    r("brightness", "Control screen brightness: up, down, or a percentage",
      {"type": "object", "properties": {
          "action": {"type": "string", "description": "Brightness action: up, down, or a percentage like 75"}
      }, "required": ["action"]},
      set_brightness, "green", "system")

    # Web
    r("web_search", "Search Google for a query",
      {"type": "object", "properties": {
          "query": {"type": "string", "description": "Search query string"}
      }, "required": ["query"]},
      web_search, "green", "web")

    r("open_url", "Open a URL in the default browser",
      {"type": "object", "properties": {
          "url": {"type": "string", "description": "URL to open (https:// prefix added if missing)"}
      }, "required": ["url"]},
      open_url, "green", "web")

    # Typing & input
    r("type_text", "Type text into the active window",
      {"type": "object", "properties": {
          "text": {"type": "string", "description": "Text to type"}
      }, "required": ["text"]},
      type_text, "green", "input")

    r("press_key", "Press a keyboard shortcut (e.g. ctrl+s, alt+tab, enter)",
      {"type": "object", "properties": {
          "keys": {"type": "string", "description": "Key or shortcut to press, e.g. 'ctrl+s', 'alt+tab', 'enter'"}
      }, "required": ["keys"]},
      press_key, "green", "input")

    # Files
    r("open_folder", "Open a folder (Downloads, Documents, Desktop, etc.)",
      {"type": "object", "properties": {
          "name": {"type": "string", "description": "Folder name or path to open"}
      }, "required": ["name"]},
      open_folder, "green", "files")

    r("open_file", "Open a file by its path",
      {"type": "object", "properties": {
          "path": {"type": "string", "description": "Full path to the file to open"}
      }, "required": ["path"]},
      open_file, "green", "files")
