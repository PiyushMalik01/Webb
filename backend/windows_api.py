"""
Windows native API integration for Webb.
Priority: UI Automation API first, vision-based fallback only when needed.
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import time
from typing import Optional

from . import action_registry


# ══════════════════════════════════════════════════════════════
#  WINDOW CONTROL
# ══════════════════════════════════════════════════════════════

def get_window_info() -> str:
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        win = desktop.top_window()
        rect = win.rectangle()
        return json.dumps({
            "title": win.window_text(),
            "rect": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom},
            "maximized": win.is_maximized(),
            "minimized": win.is_minimized(),
        })
    except Exception as e:
        return f"Error: {e}"


def snap_window(position: str = "left") -> str:
    try:
        import pyautogui
        p = position.lower().strip()
        snaps = {
            "left": ("win", "left"), "right": ("win", "right"),
            "top": ("win", "up"), "maximize": ("win", "up"),
            "bottom": ("win", "down"), "minimize": ("win", "down"),
        }
        keys = snaps.get(p)
        if keys:
            pyautogui.hotkey(*keys)
            return f"Snapped {p}"
        if p == "center":
            user32 = ctypes.windll.user32
            sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            hwnd = user32.GetForegroundWindow()
            r = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            w, h = r.right - r.left, r.bottom - r.top
            user32.MoveWindow(hwnd, (sw-w)//2, (sh-h)//2, w, h, True)
            return "Centered window"
        return f"Unknown position: {p}"
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════════════
#  UI AUTOMATION (primary control method)
# ══════════════════════════════════════════════════════════════

def click_element(name: str) -> str:
    try:
        from pywinauto import Desktop
        win = Desktop(backend="uia").top_window()
        try:
            el = win.child_window(title=name, found_index=0)
            el.click_input()
            return f"Clicked '{name}'"
        except Exception:
            try:
                el = win.child_window(title_re=f".*{name}.*", found_index=0)
                el.click_input()
                return f"Clicked '{el.window_text()}'"
            except Exception:
                return f"Could not find '{name}'"
    except Exception as e:
        return f"Error: {e}"


def read_window_text() -> str:
    try:
        from pywinauto import Desktop
        win = Desktop(backend="uia").top_window()
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


def list_ui_elements() -> str:
    try:
        from pywinauto import Desktop
        win = Desktop(backend="uia").top_window()
        elements = []
        clickable_types = {"Button", "MenuItem", "TabItem", "Hyperlink", "ListItem", "TreeItem", "CheckBox", "RadioButton"}
        for child in win.descendants():
            try:
                ct = child.element_info.control_type
                name = child.window_text()
                if name and ct in clickable_types:
                    elements.append(f"[{ct}] {name}")
            except Exception:
                pass
        return "UI Elements:\n" + "\n".join(elements[:30])
    except Exception as e:
        return f"Error: {e}"


def type_in_field(field_name: str, text: str) -> str:
    try:
        from pywinauto import Desktop
        win = Desktop(backend="uia").top_window()
        try:
            el = win.child_window(title_re=f".*{field_name}.*", control_type="Edit", found_index=0)
        except Exception:
            el = win.child_window(control_type="Edit", found_index=0)
        el.set_text(text)
        return f"Typed in '{field_name}'"
    except Exception as e:
        return f"Error: {e}"


def click_menu(menu_path: str) -> str:
    """Click a menu item by path like 'File > Save' or 'Edit > Copy'."""
    try:
        from pywinauto import Desktop
        win = Desktop(backend="uia").top_window()
        parts = [p.strip() for p in menu_path.split(">")]
        menu = win.menu_select("->".join(parts))
        return f"Clicked menu: {menu_path}"
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════════════
#  CLIPBOARD
# ══════════════════════════════════════════════════════════════

def copy_to_clipboard(text: str) -> str:
    try:
        process = subprocess.Popen(['clip'], stdin=subprocess.PIPE)
        process.communicate(text.encode('utf-16-le'))
        return "Copied to clipboard"
    except Exception as e:
        return f"Error: {e}"


def read_clipboard() -> str:
    try:
        ctypes.windll.user32.OpenClipboard(0)
        try:
            handle = ctypes.windll.user32.GetClipboardData(13)
            if handle:
                return ctypes.c_wchar_p(handle).value or "Empty"
            return "Empty"
        finally:
            ctypes.windll.user32.CloseClipboard()
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════════════
#  VISION FALLBACK (only when UI Automation can't reach it)
# ══════════════════════════════════════════════════════════════

def vision_click(description: str) -> str:
    """Fallback: screenshot + AI vision to find and click an element."""
    try:
        import mss, base64, io, re
        from PIL import Image
        from openai import OpenAI
        import pyautogui

        with mss.mss() as sct:
            mon = sct.monitors[1]
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

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
            return f"Could not find '{description}'"

        x, y = int(match.group(1)), int(match.group(2))
        if scale < 1.0:
            x, y = int(x / scale), int(y / scale)
        pyautogui.click(x, y)
        return f"Clicked '{description}' at ({x}, {y})"
    except Exception as e:
        return f"Vision click error: {e}"


# ══════════════════════════════════════════════════════════════
#  SYSTEM INFO
# ══════════════════════════════════════════════════════════════

def get_system_info() -> str:
    info = []
    try:
        class SPS(ctypes.Structure):
            _fields_ = [("ACLine", ctypes.c_byte), ("Flag", ctypes.c_byte),
                        ("Pct", ctypes.c_byte), ("Sys", ctypes.c_byte),
                        ("Life", ctypes.c_ulong), ("Full", ctypes.c_ulong)]
        sps = SPS()
        ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps))
        if sps.Pct <= 100:
            info.append(f"Battery: {sps.Pct}% ({'charging' if sps.ACLine == 1 else 'on battery'})")
    except Exception:
        pass
    try:
        class MSX(ctypes.Structure):
            _fields_ = [("dwLen", ctypes.c_ulong), ("dwLoad", ctypes.c_ulong),
                        ("ullTotal", ctypes.c_ulonglong), ("ullAvail", ctypes.c_ulonglong),
                        ("p1", ctypes.c_ulonglong), ("p2", ctypes.c_ulonglong),
                        ("p3", ctypes.c_ulonglong), ("p4", ctypes.c_ulonglong),
                        ("p5", ctypes.c_ulonglong)]
        m = MSX()
        m.dwLen = ctypes.sizeof(MSX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        info.append(f"RAM: {m.ullAvail/(1024**3):.1f}GB free / {m.ullTotal/(1024**3):.1f}GB ({m.dwLoad}% used)")
    except Exception:
        pass
    return "\n".join(info) if info else "Could not get system info"


def kill_process(name: str) -> str:
    try:
        r = subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True, text=True, timeout=5)
        return f"Killed {name}" if r.returncode == 0 else f"Failed: {r.stderr.strip()}"
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════════════
#  REGISTER ALL
# ══════════════════════════════════════════════════════════════

def register_windows_actions() -> None:
    r = action_registry.register

    # Window control
    r("get_window_info", "Get details about the active window",
      {"type": "object", "properties": {}},
      lambda: get_window_info(), "green", "windows")

    r("snap_window", "Snap window to a position (left, right, center, maximize, minimize)",
      {"type": "object", "properties": {
          "position": {"type": "string", "description": "left, right, center, maximize, minimize"}
      }, "required": ["position"]},
      snap_window, "green", "windows")

    r("list_running_processes", "List all open windows",
      {"type": "object", "properties": {}},
      lambda: list_running_processes(), "green", "system")

    # UI Automation (primary)
    r("click_element", "Click a button or UI element by name in the active window",
      {"type": "object", "properties": {
          "name": {"type": "string", "description": "Name/text of the element"}
      }, "required": ["name"]},
      click_element, "green", "ui")

    r("read_window_text", "Read all visible text from the active window",
      {"type": "object", "properties": {}},
      lambda: read_window_text(), "green", "ui")

    r("list_ui_elements", "List clickable elements in the active window",
      {"type": "object", "properties": {}},
      lambda: list_ui_elements(), "green", "ui")

    r("type_in_field", "Type text into an input field in the active window",
      {"type": "object", "properties": {
          "field_name": {"type": "string", "description": "Field name"},
          "text": {"type": "string", "description": "Text to type"}
      }, "required": ["field_name", "text"]},
      type_in_field, "green", "ui")

    r("click_menu", "Click a menu item by path (e.g. 'File > Save')",
      {"type": "object", "properties": {
          "menu_path": {"type": "string", "description": "Menu path like 'File > Save As'"}
      }, "required": ["menu_path"]},
      click_menu, "green", "ui")

    # Clipboard
    r("copy_to_clipboard", "Copy text to clipboard",
      {"type": "object", "properties": {
          "text": {"type": "string", "description": "Text to copy"}
      }, "required": ["text"]},
      copy_to_clipboard, "green", "system")

    r("read_clipboard", "Read clipboard content",
      {"type": "object", "properties": {}},
      lambda: read_clipboard(), "green", "system")

    # Vision fallback
    r("vision_click", "Find and click something on screen by visual description (fallback when UI Automation fails)",
      {"type": "object", "properties": {
          "description": {"type": "string", "description": "What to click, e.g. 'the blue Send button'"}
      }, "required": ["description"]},
      vision_click, "green", "ui")

    # System
    r("kill_process", "Force-close an application",
      {"type": "object", "properties": {
          "name": {"type": "string", "description": "Process name (e.g. chrome.exe)"}
      }, "required": ["name"]},
      kill_process, "yellow", "system")

    r("get_system_info", "Get battery, memory info",
      {"type": "object", "properties": {}},
      lambda: get_system_info(), "green", "system")
