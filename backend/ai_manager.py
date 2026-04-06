from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

from openai import OpenAI

from . import action_registry
from .context_builder import build_messages
from .conversation_manager import conversation
from .database import SessionLocal
from .models import Reminder, Task
from .serial_manager import get_serial_manager


NUDGE_SYSTEM_PROMPT = """
You are a supportive productivity coach.
Respond with exactly one short motivational sentence (max 18 words), plain text only.
"""

INTENT_CLASSIFIER_PROMPT = """You hear ambient audio transcriptions from a desk microphone. Classify if the speech is directed at the desk assistant "Webb" or not.

Reply with ONLY one word:
- WEBB — if the person is talking to Webb / giving a command / asking Webb something
- IGNORE — if it's background noise, talking to someone else, music, TV, or not directed at Webb

Examples:
"hey webb open chrome" → WEBB
"so I was telling him about the meeting" → IGNORE
"open my browser please" → WEBB
"yeah that sounds good" → IGNORE
"what time is it" → WEBB
"haha that's funny" → IGNORE
"play some music" → WEBB
"can you hear me" → WEBB
"I don't know man" → IGNORE
"""

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=api_key, timeout=10.0)
    return _client


def is_directed_at_webb(text: str) -> bool:
    """Fast AI classifier: is this speech directed at Webb or background noise?"""
    text = text.strip()
    if not text:
        return False

    # Quick keyword check first (instant, no API call)
    lower = text.lower()
    direct_triggers = ["webb", "web ", "hey web", "open ", "search ", "start ", "set ",
                       "add ", "what ", "how ", "can you", "tell me", "show me",
                       "play ", "pause", "volume", "mute", "close ", "switch ",
                       "type ", "lock", "screenshot", "remind", "timer", "task"]
    for trigger in direct_triggers:
        if trigger in lower:
            return True

    # If no keyword match, ask AI (fast model, tiny prompt)
    try:
        client = _get_client()
        completion = client.chat.completions.create(
            model="gpt-4.1-nano",  # Fastest model for classification
            messages=[
                {"role": "system", "content": INTENT_CLASSIFIER_PROMPT},
                {"role": "user", "content": text},
            ],
            max_tokens=4,
        )
        answer = (completion.choices[0].message.content or "").strip().upper()
        return answer == "WEBB"
    except Exception:
        # If classifier fails, default to processing (better to respond than ignore)
        return True


def process_message(text: str) -> Dict[str, Any]:
    """
    Process a user message through the AI Brain.
    Returns: {"speak": str, "actions": list, "face": str, "action_results": list}
    """
    text = text.strip()
    if not text:
        return {"speak": "I didn't catch that.", "actions": [], "face": "IDLE", "action_results": []}

    # Build messages with full context
    messages = build_messages(text)

    # Call AI
    try:
        client = _get_client()
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=messages,
            max_tokens=256,
            temperature=0.7,
        )
        content = completion.choices[0].message.content or ""
    except Exception as e:
        return {
            "speak": f"Sorry, I had trouble thinking: {e}",
            "actions": [],
            "face": "IDLE",
            "action_results": [],
        }

    # Parse JSON response
    try:
        # Strip markdown fences if present
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # AI returned plain text instead of JSON — treat as conversation
        data = {"speak": content.strip(), "actions": [], "face": "HAPPY"}

    speak = str(data.get("speak", ""))
    actions = data.get("actions", [])
    face = str(data.get("face", "HAPPY"))

    # Execute actions
    action_results = []
    for action_spec in actions:
        if not isinstance(action_spec, dict):
            continue
        name = action_spec.get("name", "")
        params = action_spec.get("params", {})
        if not isinstance(params, dict):
            params = {}
        result = action_registry.execute(name, params)
        action_results.append({"name": name, "result": result})

    # Record conversation
    conversation.add_user(text)
    conversation.add_assistant(speak)

    return {
        "speak": speak,
        "actions": actions,
        "face": face,
        "action_results": action_results,
    }


def generate_idle_nudge() -> str:
    """Generate a motivational nudge for idle users."""
    try:
        client = _get_client()
    except Exception:
        return "Ready to get back to it?"

    try:
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=[
                {"role": "system", "content": NUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": "Give me one nudge."},
            ],
            max_tokens=48,
        )
        content = (completion.choices[0].message.content or "").strip()
        if content:
            return content
    except Exception:
        pass

    return "Ready to get back to it?"


# ── Task/Timer/Reminder Actions ──────────────────────────────

def _add_task(title: str, priority: str = "medium", due_date: str = "") -> str:
    with SessionLocal() as db:
        task = Task(title=title, priority=priority or "medium", due_date=due_date or None)
        db.add(task)
        db.commit()
    try:
        get_serial_manager().send_face("HAPPY")
    except Exception:
        pass
    return f"Task added: {title}"


def _complete_task(title: str) -> str:
    with SessionLocal() as db:
        task = db.query(Task).filter(
            Task.completed.is_(False),
            Task.title.ilike(f"%{title}%"),
        ).first()
        if not task:
            return f"No active task matching '{title}'"
        task.completed = True
        db.commit()
        task_title = task.title
    try:
        get_serial_manager().send_face("HAPPY")
    except Exception:
        pass
    return f"Completed: {task_title}"


def _start_timer(duration_minutes: int = 25) -> str:
    # We can't directly start the async timer from here, so return instruction
    return f"Start a {duration_minutes} minute timer from the Timer page, or say the duration."


def _set_reminder(message: str, time: str = "") -> str:
    with SessionLocal() as db:
        reminder = Reminder(message=message, trigger_time=time or "", repeat="none")
        db.add(reminder)
        db.commit()
    try:
        get_serial_manager().send_face("REMINDER")
    except Exception:
        pass
    return f"Reminder set: {message}"


def _list_tasks() -> str:
    with SessionLocal() as db:
        tasks = db.query(Task).filter(Task.completed.is_(False)).order_by(Task.created_at.desc()).limit(10).all()
        if not tasks:
            return "No active tasks."
        lines = [f"- {t.title} ({t.priority})" for t in tasks]
    return "Active tasks:\n" + "\n".join(lines)


def register_task_actions() -> None:
    """Register task/timer/reminder actions in the action registry."""
    r = action_registry.register
    r("add_task", "Create a new task with title, priority (low/medium/high), and optional due_date", ["title", "priority", "due_date"], _add_task, "productivity")
    r("complete_task", "Mark a task as complete by title (fuzzy match)", ["title"], _complete_task, "productivity")
    r("start_timer", "Start a Pomodoro focus timer", ["duration_minutes"], _start_timer, "productivity")
    r("set_reminder", "Set a reminder with a message and time", ["message", "time"], _set_reminder, "productivity")
    r("list_tasks", "List all active tasks", [], lambda: _list_tasks(), "productivity")
