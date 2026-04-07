"""
Webb Windows Control — Robust multi-monitor, multi-window automation.

Architecture:
1. WindowManager — tracks all windows, handles focus, multi-monitor
2. ElementFinder — finds UI elements with fallback chain
3. ScreenCapture — captures the correct monitor
4. ActionExecutor — executes actions with verification
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from . import action_registry


# ══════════════════════════════════════════════════════════════
#  WINDOW MANAGER — tracks windows, handles focus
# ══════════════════════════════════════════════════════════════

user32 = ctypes.windll.user32


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    rect: Tuple[int, int, int, int]  # left, top, right, bottom
    monitor: int  # monitor index
    is_visible: bool


def _get_hwnd_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _get_hwnd_pid(hwnd: int) -> int:
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _get_hwnd_rect(hwnd: int) -> Tuple[int, int, int, int]:
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right, rect.bottom)


def get_monitors() -> List[Dict[str, Any]]:
    """Get all connected monitors with their geometry."""
    monitors = []
    try:
        import mss
        with mss.mss() as sct:
            for i, mon in enumerate(sct.monitors):
                if i == 0:
                    continue  # Skip the "all monitors" entry
                monitors.append({
                    "index": i,
                    "left": mon["left"],
                    "top": mon["top"],
                    "width": mon["width"],
                    "height": mon["height"],
                })
    except Exception:
        # Fallback: just primary
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        monitors.append({"index": 1, "left": 0, "top": 0, "width": w, "height": h})
    return monitors


def _point_to_monitor(x: int, y: int, monitors: List[Dict]) -> int:
    """Determine which monitor a point is on."""
    for mon in monitors:
        if (mon["left"] <= x < mon["left"] + mon["width"] and
                mon["top"] <= y < mon["top"] + mon["height"]):
            return mon["index"]
    return 1  # Default to primary


def get_all_windows() -> List[WindowInfo]:
    """Enumerate all visible windows with full info."""
    windows = []
    monitors = get_monitors()

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _get_hwnd_title(hwnd)
        if not title or title in ("Program Manager", ""):
            return True
        try:
            rect = _get_hwnd_rect(hwnd)
            pid = _get_hwnd_pid(hwnd)
            cx = (rect[0] + rect[2]) // 2
            cy = (rect[1] + rect[3]) // 2
            mon = _point_to_monitor(cx, cy, monitors)
            windows.append(WindowInfo(
                hwnd=hwnd, title=title, pid=pid,
                rect=rect, monitor=mon, is_visible=True,
            ))
        except Exception:
            pass
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return windows


def get_active_window() -> Optional[WindowInfo]:
    """Get the currently focused window with monitor info."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    title = _get_hwnd_title(hwnd)
    if not title:
        return None
    rect = _get_hwnd_rect(hwnd)
    pid = _get_hwnd_pid(hwnd)
    monitors = get_monitors()
    cx = (rect[0] + rect[2]) // 2
    cy = (rect[1] + rect[3]) // 2
    mon = _point_to_monitor(cx, cy, monitors)
    return WindowInfo(hwnd=hwnd, title=title, pid=pid, rect=rect, monitor=mon, is_visible=True)


def find_window(query: str) -> Optional[WindowInfo]:
    """Find a window by title (fuzzy match)."""
    query_lower = query.lower().strip()
    windows = get_all_windows()

    # Exact match
    for w in windows:
        if query_lower == w.title.lower():
            return w

    # Substring match
    for w in windows:
        if query_lower in w.title.lower():
            return w

    # Word match
    for w in windows:
        if any(query_lower in word.lower() for word in w.title.split()):
            return w

    return None


def focus_window(hwnd: int) -> bool:
    """Bring a window to foreground. Returns True if successful."""
    try:
        # If minimized, restore it first
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE

        # Try SetForegroundWindow
        result = user32.SetForegroundWindow(hwnd)
        if result:
            time.sleep(0.2)  # Brief pause for window to come to front
            return True

        # Fallback: Alt trick (Windows blocks SetForegroundWindow sometimes)
        import pyautogui
        pyautogui.press('alt')
        time.sleep(0.05)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        return user32.GetForegroundWindow() == hwnd
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════
#  ELEMENT FINDER — robust UI element search with fallback
# ══════════════════════════════════════════════════════════════

def find_and_click(name: str, window_title: str = "") -> str:
    """
    Find and click a UI element. Fallback chain:
    1. UI Automation exact match
    2. UI Automation partial match
    3. UI Automation by control type + name
    4. Vision fallback (screenshot + AI)
    """
    try:
        from pywinauto import Desktop

        # Target specific window or active window
        if window_title:
            win_info = find_window(window_title)
            if win_info:
                focus_window(win_info.hwnd)
                time.sleep(0.2)

        desktop = Desktop(backend="uia")
        win = desktop.top_window()

        # Attempt 1: exact title match
        try:
            el = win.child_window(title=name, found_index=0)
            el.wait('visible', timeout=2)
            el.click_input()
            return f"Clicked '{name}'"
        except Exception:
            pass

        # Attempt 2: partial match
        try:
            el = win.child_window(title_re=f"(?i).*{_escape_regex(name)}.*", found_index=0)
            el.wait('visible', timeout=2)
            el.click_input()
            return f"Clicked '{el.window_text()}'"
        except Exception:
            pass

        # Attempt 3: search by automation ID
        try:
            el = win.child_window(auto_id=name, found_index=0)
            el.click_input()
            return f"Clicked element with ID '{name}'"
        except Exception:
            pass

        # Attempt 4: vision fallback
        return _vision_click_fallback(name)

    except Exception as e:
        return f"Error finding '{name}': {e}"


def _escape_regex(s: str) -> str:
    import re
    return re.escape(s)


def get_ui_tree(window_title: str = "") -> str:
    """Get clickable elements from a specific or active window."""
    try:
        from pywinauto import Desktop

        if window_title:
            win_info = find_window(window_title)
            if win_info:
                focus_window(win_info.hwnd)
                time.sleep(0.2)

        desktop = Desktop(backend="uia")
        win = desktop.top_window()

        elements = []
        clickable = {"Button", "MenuItem", "TabItem", "Hyperlink",
                     "ListItem", "TreeItem", "CheckBox", "RadioButton", "ComboBox"}
        for child in win.descendants():
            try:
                ct = child.element_info.control_type
                name = child.window_text()
                if name and ct in clickable:
                    elements.append(f"[{ct}] {name}")
            except Exception:
                pass

        title = win.window_text()
        return f"Window: {title}\nElements:\n" + "\n".join(elements[:40])
    except Exception as e:
        return f"Error: {e}"


def read_text(window_title: str = "") -> str:
    """Read visible text from a specific or active window."""
    try:
        from pywinauto import Desktop

        if window_title:
            win_info = find_window(window_title)
            if win_info:
                focus_window(win_info.hwnd)
                time.sleep(0.2)

        desktop = Desktop(backend="uia")
        win = desktop.top_window()

        texts = []
        seen = set()
        for child in win.descendants():
            try:
                t = child.window_text().strip()
                if t and len(t) < 500 and t not in seen:
                    seen.add(t)
                    texts.append(t)
            except Exception:
                pass
        return "\n".join(texts[:50])
    except Exception as e:
        return f"Error: {e}"


def type_in_field(field_name: str, text: str, window_title: str = "") -> str:
    """Type into an input field. Targets specific window if given."""
    try:
        from pywinauto import Desktop

        if window_title:
            win_info = find_window(window_title)
            if win_info:
                focus_window(win_info.hwnd)
                time.sleep(0.2)

        desktop = Desktop(backend="uia")
        win = desktop.top_window()

        # Try by name
        try:
            el = win.child_window(title_re=f"(?i).*{_escape_regex(field_name)}.*",
                                  control_type="Edit", found_index=0)
            el.set_text(text)
            return f"Typed in '{field_name}'"
        except Exception:
            pass

        # Try first Edit control
        try:
            el = win.child_window(control_type="Edit", found_index=0)
            el.set_text(text)
            return f"Typed in input field"
        except Exception:
            pass

        # Fallback: click and type with pyautogui
        import pyautogui
        pyautogui.write(text, interval=0.02)
        return f"Typed text"
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════════════
#  SCREEN CAPTURE — multi-monitor aware
# ══════════════════════════════════════════════════════════════

def capture_active_screen() -> Tuple[Any, int, int, int]:
    """Capture the screen of the active window's monitor. Returns (PIL Image, monitor_left, monitor_top, monitor_index)."""
    import mss
    from PIL import Image

    active = get_active_window()
    monitors = get_monitors()

    if active:
        target_mon = active.monitor
    else:
        target_mon = 1

    with mss.mss() as sct:
        # Find the right monitor
        if target_mon < len(sct.monitors):
            mon = sct.monitors[target_mon]
        else:
            mon = sct.monitors[1]

        shot = sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return img, mon["left"], mon["top"], target_mon


def _vision_click_fallback(description: str) -> str:
    """Vision fallback: capture active monitor, find element, click."""
    try:
        import base64, io, re
        from openai import OpenAI
        import pyautogui

        img, mon_left, mon_top, mon_idx = capture_active_screen()

        # Resize for API
        scale = min(1.0, 1920 / img.width)
        if scale < 1.0:
            img = img.resize((int(img.width * scale), int(img.height * scale)))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=15.0)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": f'Find "{description}" in this screenshot. Return ONLY JSON: {{"x": 123, "y": 456}}. Image is {img.width}x{img.height}px.'},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]}],
            max_tokens=50,
        )

        match = re.search(r'"x"\s*:\s*(\d+)\s*,\s*"y"\s*:\s*(\d+)', resp.choices[0].message.content)
        if not match:
            return f"Could not find '{description}' on screen"

        # Convert image coords back to screen coords (accounting for monitor offset)
        x = int(int(match.group(1)) / scale) + mon_left
        y = int(int(match.group(2)) / scale) + mon_top

        pyautogui.click(x, y)
        return f"Clicked '{description}' at ({x}, {y}) on monitor {mon_idx}"
    except Exception as e:
        return f"Vision fallback failed: {e}"


def describe_screen() -> str:
    """Describe what's on the active monitor."""
    try:
        import base64, io
        from openai import OpenAI

        img, _, _, mon_idx = capture_active_screen()
        img.thumbnail((1024, 1024))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=15.0)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe what's on this screen concisely. Focus on the main app and visible content."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]}],
            max_tokens=200,
        )
        return f"[Monitor {mon_idx}] {resp.choices[0].message.content}"
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════════════
#  WINDOW ACTIONS
# ══════════════════════════════════════════════════════════════

def switch_to_window(name: str) -> str:
    """Find and focus a window by name."""
    win = find_window(name)
    if not win:
        return f"No window matching '{name}'"
    if focus_window(win.hwnd):
        return f"Switched to '{win.title}' on monitor {win.monitor}"
    return f"Found '{win.title}' but couldn't bring it to front"


def snap_window(position: str) -> str:
    try:
        import pyautogui
        p = position.lower().strip()
        snaps = {"left": ("win", "left"), "right": ("win", "right"),
                 "maximize": ("win", "up"), "minimize": ("win", "down")}
        if p in snaps:
            pyautogui.hotkey(*snaps[p])
            return f"Snapped {p}"
        if p == "center":
            active = get_active_window()
            if not active:
                return "No active window"
            monitors = get_monitors()
            mon = next((m for m in monitors if m["index"] == active.monitor), monitors[0])
            w = active.rect[2] - active.rect[0]
            h = active.rect[3] - active.rect[1]
            x = mon["left"] + (mon["width"] - w) // 2
            y = mon["top"] + (mon["height"] - h) // 2
            user32.MoveWindow(active.hwnd, x, y, w, h, True)
            return "Centered on current monitor"
        return f"Unknown position: {p}"
    except Exception as e:
        return f"Error: {e}"


def list_windows() -> str:
    windows = get_all_windows()
    if not windows:
        return "No windows found"
    lines = []
    for w in windows[:25]:
        lines.append(f"[Mon {w.monitor}] {w.title}")
    return "Open windows:\n" + "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  CLIPBOARD
# ══════════════════════════════════════════════════════════════

def copy_to_clipboard(text: str) -> str:
    try:
        process = subprocess.Popen(['clip'], stdin=subprocess.PIPE)
        process.communicate(text.encode('utf-16-le'))
        return "Copied"
    except Exception as e:
        return f"Error: {e}"


def read_clipboard() -> str:
    try:
        user32.OpenClipboard(0)
        try:
            handle = user32.GetClipboardData(13)
            return ctypes.c_wchar_p(handle).value if handle else "Empty"
        finally:
            user32.CloseClipboard()
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════════════
#  SYSTEM INFO
# ══════════════════════════════════════════════════════════════

def get_system_info() -> str:
    info = []
    try:
        class SPS(ctypes.Structure):
            _fields_ = [("AC", ctypes.c_byte), ("F", ctypes.c_byte),
                        ("P", ctypes.c_byte), ("S", ctypes.c_byte),
                        ("L", ctypes.c_ulong), ("FL", ctypes.c_ulong)]
        sps = SPS()
        ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps))
        if sps.P <= 100:
            info.append(f"Battery: {sps.P}% ({'charging' if sps.AC == 1 else 'on battery'})")
    except Exception:
        pass
    try:
        class MSX(ctypes.Structure):
            _fields_ = [("L", ctypes.c_ulong), ("Load", ctypes.c_ulong),
                        ("T", ctypes.c_ulonglong), ("A", ctypes.c_ulonglong),
                        *[(f"p{i}", ctypes.c_ulonglong) for i in range(5)]]
        m = MSX()
        m.L = ctypes.sizeof(MSX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        info.append(f"RAM: {m.A/(1024**3):.1f}GB free / {m.T/(1024**3):.1f}GB ({m.Load}% used)")
    except Exception:
        pass
    monitors = get_monitors()
    info.append(f"Monitors: {len(monitors)}")
    return "\n".join(info) if info else "No info available"


def kill_process(name: str) -> str:
    try:
        r = subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True, text=True, timeout=5)
        return f"Killed {name}" if r.returncode == 0 else f"Failed: {r.stderr.strip()}"
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════════════
#  REGISTER
# ══════════════════════════════════════════════════════════════

def register_windows_actions() -> None:
    r = action_registry.register

    # Window management
    r("switch_to", "Switch to a window by name (fuzzy match, multi-monitor aware)",
      {"type": "object", "properties": {
          "name": {"type": "string", "description": "Window title or app name"}
      }, "required": ["name"]},
      switch_to_window, "green", "windows")

    r("snap_window", "Snap window to position (left, right, center, maximize, minimize)",
      {"type": "object", "properties": {
          "position": {"type": "string", "description": "left/right/center/maximize/minimize"}
      }, "required": ["position"]},
      snap_window, "green", "windows")

    r("list_windows", "List all open windows with their monitor",
      {"type": "object", "properties": {}},
      lambda: list_windows(), "green", "windows")

    r("get_window_info", "Get info about the active window",
      {"type": "object", "properties": {}},
      lambda: json.dumps({"window": get_active_window().__dict__} if get_active_window() else {"window": None}),
      "green", "windows")

    # UI Automation (primary)
    r("click_element", "Click a button/element by name in the active or specified window. Falls back to vision if not found.",
      {"type": "object", "properties": {
          "name": {"type": "string", "description": "Element name/text"},
          "window_title": {"type": "string", "description": "Target window (optional, uses active if empty)"},
      }, "required": ["name"]},
      find_and_click, "green", "ui")

    r("read_window_text", "Read visible text from the active or specified window",
      {"type": "object", "properties": {
          "window_title": {"type": "string", "description": "Target window (optional)"},
      }},
      read_text, "green", "ui")

    r("list_ui_elements", "List clickable elements in the active or specified window",
      {"type": "object", "properties": {
          "window_title": {"type": "string", "description": "Target window (optional)"},
      }},
      get_ui_tree, "green", "ui")

    r("type_in_field", "Type text into an input field",
      {"type": "object", "properties": {
          "field_name": {"type": "string", "description": "Field name"},
          "text": {"type": "string", "description": "Text to type"},
          "window_title": {"type": "string", "description": "Target window (optional)"},
      }, "required": ["field_name", "text"]},
      type_in_field, "green", "ui")

    # Vision
    r("vision_click", "Find and click something by visual description (fallback, uses screenshot + AI)",
      {"type": "object", "properties": {
          "description": {"type": "string", "description": "What to click visually"}
      }, "required": ["description"]},
      _vision_click_fallback, "green", "ui")

    r("describe_screen", "Describe what's on the active monitor",
      {"type": "object", "properties": {}},
      lambda: describe_screen(), "green", "ui")

    # Clipboard
    r("copy_to_clipboard", "Copy text to clipboard",
      {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
      copy_to_clipboard, "green", "system")

    r("read_clipboard", "Read clipboard content",
      {"type": "object", "properties": {}},
      lambda: read_clipboard(), "green", "system")

    # System
    r("get_system_info", "Get battery, RAM, monitor count",
      {"type": "object", "properties": {}},
      lambda: get_system_info(), "green", "system")

    r("kill_process", "Force-close an app by process name",
      {"type": "object", "properties": {"name": {"type": "string", "description": "e.g. chrome.exe"}}, "required": ["name"]},
      kill_process, "yellow", "system")

    r("get_monitors", "List all connected monitors with their resolution",
      {"type": "object", "properties": {}},
      lambda: json.dumps(get_monitors()), "green", "system")
