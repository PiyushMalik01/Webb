from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Tuple


# Fast patterns: regex → (action_name, param_extractor, spoken_response)
# These bypass the LLM entirely for <500ms response
PATTERNS: list[Tuple[re.Pattern, str, callable, Optional[str]]] = []


def _build_patterns():
    global PATTERNS
    PATTERNS = [
        # Volume
        (re.compile(r"^(?:set\s+)?volume\s+(up|down|mute|unmute|\d+%?)$", re.I),
         "volume", lambda m: {"action": m.group(1).replace("%", "")}, None),

        # Media
        (re.compile(r"^(pause|play|resume|next|previous|prev|stop)\s*(music|track|song|media)?$", re.I),
         "media", lambda m: {"action": m.group(1)}, None),

        # Timer
        (re.compile(r"^(?:start|set)\s+(?:a\s+)?(\d+)\s*(?:min(?:ute)?s?)\s*(?:timer|focus)?$", re.I),
         "start_timer", lambda m: {"minutes": int(m.group(1))}, lambda m: f"Timer started, {m.group(1)} minutes"),

        (re.compile(r"^stop\s*(?:the\s+)?timer$", re.I),
         "stop_timer", lambda m: {}, "Timer stopped"),

        (re.compile(r"^pause\s*(?:the\s+)?timer$", re.I),
         "pause_timer", lambda m: {}, "Timer paused"),

        # Screenshot
        (re.compile(r"^(?:take\s+(?:a\s+)?)?screenshot$", re.I),
         "screenshot", lambda m: {}, "Screenshot saved"),

        # Lock
        (re.compile(r"^lock\s*(?:the\s+)?(?:screen|computer|pc)?$", re.I),
         "lock_screen", lambda m: {}, None),

        # Time
        (re.compile(r"^what(?:'s|\s+is)\s+the\s+time$", re.I),
         "_tell_time", lambda m: {}, None),
        (re.compile(r"^what\s+time\s+is\s+it$", re.I),
         "_tell_time", lambda m: {}, None),

        # Mute/unmute shorthand
        (re.compile(r"^(mute|unmute)$", re.I),
         "volume", lambda m: {"action": m.group(1)}, None),

        # Show desktop
        (re.compile(r"^show\s+(?:the\s+)?desktop$", re.I),
         "show_desktop", lambda m: {}, "Showing desktop"),

        # Minimize/maximize
        (re.compile(r"^(minimize|maximise|maximize)\s*(?:this|window)?$", re.I),
         lambda m: "minimize" if "min" in m.group(1).lower() else "maximize",
         lambda m: {}, None),
    ]


def try_fast_path(text: str) -> Optional[dict]:
    """
    Try to match text against fast patterns.
    Returns {"action": name, "params": dict, "speak": str} or None.
    """
    if not PATTERNS:
        _build_patterns()

    clean = text.strip()
    # Strip leading trigger words
    for prefix in ["hey webb ", "webb ", "hey web ", "web "]:
        if clean.lower().startswith(prefix):
            clean = clean[len(prefix):].strip()
            break

    for pattern, action, param_fn, speak in PATTERNS:
        match = pattern.match(clean)
        if match:
            # Handle callable action names
            act_name = action(match) if callable(action) else action
            params = param_fn(match)

            # Handle time specially
            if act_name == "_tell_time":
                now = datetime.now()
                time_str = now.strftime("%I:%M %p")
                return {"action": None, "params": {}, "speak": f"It's {time_str}"}

            # Handle callable speak
            if callable(speak):
                speak_text = speak(match)
            else:
                speak_text = speak

            return {"action": act_name, "params": params, "speak": speak_text}

    return None
