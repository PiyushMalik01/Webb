from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select

from .database import SessionLocal
from .models import Reminder
from .notifications_hub import hub
from .serial_manager import get_serial_manager


async def reminder_check_loop() -> None:
    """Background task: every 30s, trigger due reminders."""
    while True:
        await asyncio.sleep(30)
        try:
            _check_and_trigger()
        except Exception as exc:
            print(f"[reminder_scheduler] error: {exc}")


def _check_and_trigger() -> None:
    db = SessionLocal()
    try:
        now = datetime.utcnow().isoformat()
        stmt = select(Reminder).where(
            Reminder.triggered == False,  # noqa: E712
            Reminder.trigger_time <= now,
        )
        due = list(db.scalars(stmt).all())

        for reminder in due:
            reminder.triggered = True

            hub.publish_threadsafe({
                "type": "reminder_triggered",
                "text": reminder.message,
                "reminder_id": reminder.id,
                "created_at": datetime.utcnow().isoformat(),
            })

            try:
                get_serial_manager().send_face("REMINDER")
            except Exception:
                pass

            # Speak the reminder aloud
            try:
                from . import streaming_tts
                is_alarm = "alarm" in reminder.message.lower() or "wake" in reminder.message.lower()
                if is_alarm:
                    # Alarm: louder, more urgent, repeat
                    streaming_tts.speak(f"Wake up! {reminder.message}")
                    streaming_tts.speak(f"Hey Piyush! {reminder.message}")
                else:
                    streaming_tts.speak(f"Reminder: {reminder.message}")
            except Exception:
                pass

            # Handle repeating reminders
            if reminder.repeat == "daily":
                _create_next(db, reminder, timedelta(days=1))
            elif reminder.repeat == "weekly":
                _create_next(db, reminder, timedelta(weeks=1))

        db.commit()
    finally:
        db.close()


def _create_next(db, original: Reminder, delta: timedelta) -> None:
    try:
        next_time = datetime.fromisoformat(original.trigger_time) + delta
    except ValueError:
        return
    new_reminder = Reminder(
        message=original.message,
        trigger_time=next_time.isoformat(),
        repeat=original.repeat,
    )
    db.add(new_reminder)
