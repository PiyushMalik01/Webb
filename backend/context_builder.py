from __future__ import annotations

import os
from datetime import datetime

from .activity_monitor import get_current_window, get_open_windows
from .conversation_manager import conversation
from .database import SessionLocal
from .models import Reminder, Task


def _get_task_summary() -> str:
    """Get a summary of current tasks."""
    try:
        with SessionLocal() as db:
            active = db.query(Task).filter(Task.completed.is_(False)).count()
            completed_today = (
                db.query(Task)
                .filter(
                    Task.completed.is_(True),
                    Task.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0),
                )
                .count()
            )
        return f"{active} active, {completed_today} completed today"
    except Exception:
        return "unknown"


def _get_timer_summary() -> str:
    """Get current timer state."""
    try:
        from .routes.timer import _timer, _timer_lock
        import asyncio

        # Access the timer state directly (it's module-level)
        state = _timer.state
        remaining = _timer.seconds_remaining
        if state == "running":
            mins = remaining // 60
            secs = remaining % 60
            return f"running ({mins}:{secs:02d} left)"
        elif state == "paused":
            mins = remaining // 60
            secs = remaining % 60
            return f"paused ({mins}:{secs:02d} left)"
        return "idle"
    except Exception:
        return "idle"


def _get_next_reminder() -> str:
    """Get the next upcoming reminder."""
    try:
        with SessionLocal() as db:
            now = datetime.utcnow().isoformat()
            reminder = (
                db.query(Reminder)
                .filter(Reminder.triggered.is_(False), Reminder.trigger_time > now)
                .order_by(Reminder.trigger_time.asc())
                .first()
            )
            if reminder:
                return f"'{reminder.message}' at {reminder.trigger_time}"
            return "none"
    except Exception:
        return "none"


def build_system_prompt() -> str:
    """Build the full system prompt with dynamic context."""
    user_name = os.getenv("WEBB_USER_NAME", "User")

    # Gather context
    now = datetime.now()
    current_time = now.strftime("%I:%M %p")
    current_date = now.strftime("%A, %B %d, %Y")

    window = get_current_window()
    active_window = window.title if window else "unknown"

    open_wins = get_open_windows()
    running_apps = ", ".join(open_wins[:10]) if open_wins else "unknown"

    task_summary = _get_task_summary()
    timer_state = _get_timer_summary()
    next_reminder = _get_next_reminder()

    # Import action descriptions
    from .action_registry import describe_for_ai
    action_descriptions = describe_for_ai()

    return f"""You are Webb, a personal AI desk assistant. You sit on {user_name}'s desk as a physical bot with a display face.

Your personality: helpful, concise, slightly witty. You're eager but not annoying. Keep responses under 2 sentences for actions, up to 4 for conversation.

Current context:
- Time: {current_time}
- Date: {current_date}
- Active window: {active_window}
- Open apps: {running_apps}
- Tasks: {task_summary}
- Timer: {timer_state}
- Next reminder: {next_reminder}

Available actions you can perform:
{action_descriptions}

When the user asks you to do something:
1. Determine which action(s) to call
2. Return a JSON response with actions AND a spoken response

Response format:
{{"speak": "Opening Chrome for you", "actions": [{{"name": "launch_app", "params": {{"app_name": "chrome"}}}}], "face": "HAPPY"}}

For pure conversation (jokes, questions, chat), just return:
{{"speak": "your response here", "actions": [], "face": "HAPPY"}}

For multi-step actions, chain them:
{{"speak": "Opening Chrome and searching for weather", "actions": [{{"name": "launch_app", "params": {{"app_name": "chrome"}}}}, {{"name": "web_search", "params": {{"query": "weather today"}}}}], "face": "FOCUS"}}

For tasks/reminders/timer, use these actions:
- add_task(title, priority, due_date) - create a new task
- complete_task(title) - mark a task as complete
- start_timer(duration_minutes) - start a Pomodoro timer
- set_reminder(message, time) - set a reminder
- list_tasks() - list current tasks

If you can't do something, say so honestly. Never make up capabilities.
Always return valid JSON. No markdown, no code fences, just raw JSON."""


def build_messages(user_text: str) -> list[dict[str, str]]:
    """Build the full messages list for an AI call, including system prompt and conversation history."""
    messages = [{"role": "system", "content": build_system_prompt()}]
    messages.extend(conversation.get_messages())
    messages.append({"role": "user", "content": user_text})
    return messages
