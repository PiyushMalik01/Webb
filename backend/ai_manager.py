from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai import OpenAI

from . import action_registry
from .context_builder import build_messages
from .conversation_manager import conversation
from .database import SessionLocal
from .models import Reminder, Task
from .serial_manager import get_serial_manager
from .fast_path import try_fast_path

_client: Optional[OpenAI] = None

# Pending actions waiting for user confirmation
_pending_actions: List[Dict[str, Any]] = []


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=api_key, timeout=12.0)
    return _client


def process_message(text: str) -> Dict[str, Any]:
    """
    Process a user message. Tries fast path first, then LLM with function calling.
    Returns: {"speak": str, "actions": list, "face": str, "action_results": list}
    """
    global _pending_actions
    text = text.strip()
    if not text:
        return _result("I didn't catch that.", face="IDLE")

    # 0. Check if user is confirming a pending action
    if _pending_actions:
        lower = text.lower().strip()
        yes_words = {"yes", "yeah", "yep", "sure", "do it", "go ahead", "ok", "okay", "confirm", "y"}
        no_words = {"no", "nah", "nope", "cancel", "don't", "stop", "n", "never mind"}

        if any(w in lower for w in yes_words):
            # Execute all pending actions
            results = []
            for pa in _pending_actions:
                # Force execute by bypassing safety (user confirmed)
                action = action_registry.get(pa["name"])
                if action:
                    try:
                        result = action.fn(**pa["params"])
                        results.append({"name": pa["name"], "result": result})
                    except Exception as e:
                        results.append({"name": pa["name"], "result": f"Failed: {e}"})
            _pending_actions.clear()
            speak = "; ".join(r["result"] for r in results) or "Done."
            conversation.add_user(text)
            conversation.add_assistant(speak)
            return _result(speak, action_results=results)

        if any(w in lower for w in no_words):
            _pending_actions.clear()
            conversation.add_user(text)
            conversation.add_assistant("Okay, cancelled.")
            return _result("Okay, cancelled.", face="IDLE")

    # 1. Try fast path (instant, no API call)
    fast = try_fast_path(text)
    if fast is not None:
        action_results = []
        if fast["action"]:
            res = action_registry.execute(fast["action"], fast["params"])
            action_results.append({"name": fast["action"], "result": res.get("result", "")})

        speak = fast.get("speak") or res.get("result", "Done") if fast["action"] else fast.get("speak", "")
        conversation.add_user(text)
        conversation.add_assistant(speak)
        return _result(speak, action_results=action_results)

    # 2. LLM with function calling
    messages = build_messages(text)
    tools = action_registry.get_openai_tools()

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=messages,
            tools=tools if tools else None,
            max_tokens=256,
            temperature=0.7,
        )
    except Exception as e:
        return _result(f"Sorry, I had trouble thinking.", face="SAD")

    msg = response.choices[0].message
    action_results = []

    # 3. Handle tool calls
    if msg.tool_calls:
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                params = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                params = {}

            res = action_registry.execute(name, params)
            action_results.append({
                "name": name,
                "params": params,
                "result": res.get("result", ""),
                "ok": res.get("ok", False),
                "needs_confirmation": res.get("needs_confirmation", False),
            })

        # If any action needs confirmation, store them and ask the user
        pending = [a for a in action_results if a.get("needs_confirmation")]
        if pending:
            _pending_actions.clear()
            for a in pending:
                _pending_actions.append({"name": a["name"], "params": a.get("params", {})})
            descriptions = ", ".join(a["name"].replace("_", " ") for a in pending)
            speak = f"Should I go ahead and {descriptions}?"
            conversation.add_user(text)
            conversation.add_assistant(speak)
            return _result(speak, action_results=action_results, face="IDLE")

        # Get a spoken summary from LLM (feed tool results back)
        follow_up_messages = messages + [
            {"role": "assistant", "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]},
        ]
        for tc, ar in zip(msg.tool_calls, action_results):
            follow_up_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": ar.get("result", "Done"),
            })

        try:
            summary = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                messages=follow_up_messages,
                max_tokens=100,
            )
            speak = summary.choices[0].message.content or "Done."
        except Exception:
            speak = "Done."
    else:
        # Plain text response (conversation, question, etc.)
        speak = msg.content or ""

    # Determine face from context
    face = _pick_face(speak, action_results)

    conversation.add_user(text)
    conversation.add_assistant(speak)

    return _result(speak, action_results=action_results, face=face)


def process_streamed(text: str) -> tuple[list[str], list[dict]]:
    """
    Process a message and return sentences as they're generated.
    Returns (sentences_list, action_results).
    For streaming TTS — caller can start speaking the first sentence immediately.
    """
    text = text.strip()
    if not text:
        return ["I didn't catch that."], []

    # Fast path
    fast = try_fast_path(text)
    if fast is not None:
        action_results = []
        if fast["action"]:
            res = action_registry.execute(fast["action"], fast["params"])
            action_results.append({"name": fast["action"], "result": res.get("result", "")})
        speak = fast.get("speak") or (res.get("result", "Done") if fast["action"] else "")
        conversation.add_user(text)
        conversation.add_assistant(speak)
        return [speak] if speak else ["Done."], action_results

    # LLM streaming
    messages = build_messages(text)
    tools = action_registry.get_openai_tools()

    try:
        client = _get_client()
        stream = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=messages,
            tools=tools if tools else None,
            max_tokens=256,
            temperature=0.7,
            stream=True,
        )
    except Exception:
        return ["Sorry, I had trouble thinking."], []

    # Collect streamed response
    content_buf = ""
    tool_calls_data: Dict[int, Dict] = {}
    sentences = []

    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta is None:
            continue

        # Collect content
        if delta.content:
            content_buf += delta.content
            # Check for sentence boundaries
            while True:
                match = re.search(r'[.!?]\s', content_buf)
                if match:
                    end = match.end()
                    sentence = content_buf[:end].strip()
                    content_buf = content_buf[end:]
                    if sentence:
                        sentences.append(sentence)
                else:
                    break

        # Collect tool calls
        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in tool_calls_data:
                    tool_calls_data[idx] = {"id": "", "name": "", "arguments": ""}
                if tc_delta.id:
                    tool_calls_data[idx]["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        tool_calls_data[idx]["name"] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        tool_calls_data[idx]["arguments"] += tc_delta.function.arguments

    # Flush remaining content
    if content_buf.strip():
        sentences.append(content_buf.strip())

    # Execute tool calls
    action_results = []
    if tool_calls_data:
        for idx in sorted(tool_calls_data.keys()):
            tc = tool_calls_data[idx]
            name = tc["name"]
            try:
                params = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                params = {}
            res = action_registry.execute(name, params)
            action_results.append({"name": name, "result": res.get("result", "")})

        if not sentences:
            # Tools were called but no spoken response — get a natural summary from LLM
            results_text = ", ".join(f'{r["name"]}: {r["result"]}' for r in action_results)
            try:
                client = _get_client()
                summary = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                    messages=[
                        {"role": "system", "content": "You are Webb, a friendly desk assistant. Summarize what you just did in one short natural sentence. Don't mention function names or technical details. Speak like a human."},
                        {"role": "user", "content": f"I did these actions: {results_text}. Summarize naturally."},
                    ],
                    max_tokens=60,
                )
                sentences = [summary.choices[0].message.content.strip()]
            except Exception:
                sentences = ["Done."]

    conversation.add_user(text)
    conversation.add_assistant(" ".join(sentences))

    return sentences if sentences else ["Done."], action_results


def _pick_face(speak: str, action_results: list) -> str:
    """Pick an appropriate face expression based on response content."""
    lower = speak.lower()
    if any(w in lower for w in ["sorry", "can't", "failed", "error"]):
        return "SAD"
    if any(w in lower for w in ["done", "started", "opened", "set", "created"]):
        return "HAPPY"
    if action_results:
        return "HAPPY"
    return "IDLE"


def _result(speak: str = "", face: str = "HAPPY", action_results: list = None) -> Dict[str, Any]:
    return {
        "speak": speak,
        "actions": [],
        "face": face,
        "action_results": action_results or [],
    }


# ── Idle Nudge (kept for idle_manager) ───────────────────────

NUDGE_PROMPT = "You are a supportive productivity coach. Respond with exactly one short motivational sentence (max 18 words), plain text only."


def generate_idle_nudge() -> str:
    try:
        client = _get_client()
        r = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=[
                {"role": "system", "content": NUDGE_PROMPT},
                {"role": "user", "content": "Give me one nudge."},
            ],
            max_tokens=48,
        )
        return (r.choices[0].message.content or "").strip() or "Ready to get back to it?"
    except Exception:
        return "Ready to get back to it?"


# ── Task Actions (registered on startup) ─────────────────────

def _add_task(title: str, priority: str = "medium", due_date: str = "") -> str:
    with SessionLocal() as db:
        task = Task(title=title, priority=priority or "medium", due_date=due_date or None)
        db.add(task)
        db.commit()
    try:
        get_serial_manager().send_face("HAPPY")
    except Exception:
        pass
    from .notifications_hub import hub
    hub.publish_threadsafe({"type": "task_changed"})
    return f"Task added: {title}"


def _complete_task(title: str) -> str:
    with SessionLocal() as db:
        task = db.query(Task).filter(Task.completed.is_(False), Task.title.ilike(f"%{title}%")).first()
        if not task:
            return f"No active task matching '{title}'"
        task.completed = True
        db.commit()
        name = task.title
    from .notifications_hub import hub
    hub.publish_threadsafe({"type": "task_changed"})
    return f"Completed: {name}"


def _delete_task(title: str) -> str:
    with SessionLocal() as db:
        task = db.query(Task).filter(Task.title.ilike(f"%{title}%")).first()
        if not task:
            return f"No task matching '{title}'"
        db.delete(task)
        db.commit()
        name = task.title
    from .notifications_hub import hub
    hub.publish_threadsafe({"type": "task_changed"})
    return f"Deleted task: {name}"


def _list_tasks() -> str:
    with SessionLocal() as db:
        tasks = db.query(Task).filter(Task.completed.is_(False)).order_by(Task.created_at.desc()).limit(10).all()
        if not tasks:
            return "No active tasks."
        lines = [f"- {t.title} ({t.priority})" for t in tasks]
    return "Active tasks:\n" + "\n".join(lines)


def _start_timer(minutes: int = 25) -> str:
    """Directly start the timer — no HTTP needed."""
    import asyncio
    from .routes.timer import _timer, _timer_lock, _current_status, _broadcast, _ensure_tick_task_started

    async def _do():
        await _ensure_tick_task_started()
        async with _timer_lock:
            _timer.state = "running"
            _timer.duration_seconds = int(minutes) * 60
            _timer.seconds_remaining = _timer.duration_seconds
            _timer.last_tick_monotonic = __import__("time").monotonic()
        status = _current_status()
        await _broadcast(status)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_do(), loop).result(timeout=5)
        else:
            asyncio.run(_do())
    except Exception as e:
        return f"Timer error: {e}"

    try:
        get_serial_manager().send_face("FOCUS")
    except Exception:
        pass
    return f"Timer started: {minutes} minutes"


def _stop_timer() -> str:
    import asyncio
    from .routes.timer import _timer, _timer_lock, _current_status, _broadcast

    async def _do():
        async with _timer_lock:
            _timer.state = "idle"
            _timer.duration_seconds = 0
            _timer.seconds_remaining = 0
            _timer.last_tick_monotonic = 0.0
        await _broadcast(_current_status())

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_do(), loop).result(timeout=5)
        else:
            asyncio.run(_do())
    except Exception:
        pass
    return "Timer stopped"


def _pause_timer() -> str:
    import asyncio
    from .routes.timer import _timer, _timer_lock, _current_status, _broadcast

    async def _do():
        async with _timer_lock:
            if _timer.state == "running":
                _timer.state = "paused"
        await _broadcast(_current_status())

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(_do(), loop).result(timeout=5)
        else:
            asyncio.run(_do())
    except Exception:
        pass
    return "Timer paused"


def _set_reminder(message: str, time: str = "") -> str:
    trigger_time = _parse_time(time)
    with SessionLocal() as db:
        reminder = Reminder(message=message, trigger_time=trigger_time, repeat="none")
        db.add(reminder)
        db.commit()
    from datetime import datetime as dt
    try:
        display_time = dt.fromisoformat(trigger_time).strftime("%I:%M %p")
    except Exception:
        display_time = trigger_time
    return f"Reminder set: {message} at {display_time}"


def _set_alarm(time: str, message: str = "Time to wake up") -> str:
    """Set an alarm — uses reminder system but with 'alarm' keyword for loud wake-up."""
    trigger_time = _parse_time(time)
    alarm_message = f"ALARM: {message}"
    with SessionLocal() as db:
        reminder = Reminder(message=alarm_message, trigger_time=trigger_time, repeat="none")
        db.add(reminder)
        db.commit()
    from datetime import datetime as dt
    try:
        display_time = dt.fromisoformat(trigger_time).strftime("%I:%M %p")
    except Exception:
        display_time = trigger_time
    return f"Alarm set for {display_time}: {message}"


def _parse_time(time_str: str) -> str:
    """Parse natural time strings into ISO format."""
    from datetime import datetime as dt, timedelta

    time_str = time_str.strip()
    if not time_str:
        return dt.utcnow().isoformat()

    # Already ISO format
    try:
        dt.fromisoformat(time_str)
        return time_str
    except ValueError:
        pass

    now = dt.now()
    lower = time_str.lower().strip()

    # "in X minutes/hours"
    import re
    m = re.match(r"in\s+(\d+)\s*(min(?:ute)?s?|hours?|hrs?)", lower)
    if m:
        val = int(m.group(1))
        unit = m.group(2)
        if "hour" in unit or "hr" in unit:
            target = now + timedelta(hours=val)
        else:
            target = now + timedelta(minutes=val)
        return target.isoformat()

    # "X minutes/hours"
    m = re.match(r"(\d+)\s*(min(?:ute)?s?|hours?|hrs?)", lower)
    if m:
        val = int(m.group(1))
        unit = m.group(2)
        if "hour" in unit or "hr" in unit:
            target = now + timedelta(hours=val)
        else:
            target = now + timedelta(minutes=val)
        return target.isoformat()

    # "7:30 AM", "7:30 PM", "7:30am", "7 AM"
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", lower)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        period = m.group(3)
        if period == "pm" and hour != 12:
            hour += 12
        if period == "am" and hour == 12:
            hour = 0
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)  # Next day if time already passed
        return target.isoformat()

    # "tomorrow X"
    if lower.startswith("tomorrow"):
        rest = lower.replace("tomorrow", "").strip()
        tomorrow = now + timedelta(days=1)
        m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", rest)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2) or 0)
            period = m.group(3)
            if period == "pm" and hour != 12:
                hour += 12
            if period == "am" and hour == 12:
                hour = 0
            target = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return target.isoformat()
        return tomorrow.replace(hour=8, minute=0, second=0).isoformat()

    # Fallback: return as-is (the LLM might have given an ISO string)
    return time_str


def _navigate_app(page: str) -> str:
    """Tell frontend to navigate to a page."""
    from .notifications_hub import hub
    hub.publish_threadsafe({"type": "navigate", "path": f"/{page.strip('/')}"})
    return f"Showing {page}"


def register_task_actions() -> None:
    """Register all productivity actions with proper OpenAI tool schemas."""
    r = action_registry.register

    r("add_task", "Create a new task",
      {"type": "object", "properties": {
          "title": {"type": "string", "description": "Task title"},
          "priority": {"type": "string", "enum": ["low", "medium", "high"], "description": "Priority level"},
          "due_date": {"type": "string", "description": "Due date (YYYY-MM-DD format)"},
      }, "required": ["title"]},
      _add_task, "green", "productivity")

    r("complete_task", "Mark a task as complete by title",
      {"type": "object", "properties": {
          "title": {"type": "string", "description": "Task title or partial match"},
      }, "required": ["title"]},
      _complete_task, "green", "productivity")

    r("delete_task", "Delete a task by title",
      {"type": "object", "properties": {
          "title": {"type": "string", "description": "Task title or partial match"},
      }, "required": ["title"]},
      _delete_task, "green", "productivity")

    r("list_tasks", "List all active tasks",
      {"type": "object", "properties": {}},
      lambda: _list_tasks(), "green", "productivity")

    r("start_timer", "Start a Pomodoro focus timer",
      {"type": "object", "properties": {
          "minutes": {"type": "integer", "description": "Duration in minutes", "default": 25},
      }, "required": ["minutes"]},
      _start_timer, "green", "productivity")

    r("stop_timer", "Stop the running timer",
      {"type": "object", "properties": {}},
      lambda: _stop_timer(), "green", "productivity")

    r("pause_timer", "Pause the running timer",
      {"type": "object", "properties": {}},
      lambda: _pause_timer(), "green", "productivity")

    r("set_reminder", "Set a reminder",
      {"type": "object", "properties": {
          "message": {"type": "string", "description": "Reminder message"},
          "time": {"type": "string", "description": "When to trigger (ISO datetime or natural language)"},
      }, "required": ["message"]},
      _set_reminder, "green", "productivity")

    r("set_alarm", "Set an alarm to wake up the user at a specific time",
      {"type": "object", "properties": {
          "time": {"type": "string", "description": "When to ring (e.g. '7:30 AM', 'in 20 minutes', '6 AM')"},
          "message": {"type": "string", "description": "Alarm message", "default": "Time to wake up"},
      }, "required": ["time"]},
      _set_alarm, "green", "productivity")

    r("navigate_app", "Navigate the Webb dashboard to a specific page",
      {"type": "object", "properties": {
          "page": {"type": "string", "enum": ["tasks", "timer", "reminders", "settings"], "description": "Page to show"},
      }, "required": ["page"]},
      _navigate_app, "green", "productivity")
