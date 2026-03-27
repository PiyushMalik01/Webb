from __future__ import annotations

import os
import tempfile
from typing import Any, Dict

import speech_recognition as sr
from openai import OpenAI

from . import ai_manager
from .database import SessionLocal
from .models import Reminder, Task
from .serial_manager import get_serial_manager


def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key, timeout=25.0)


def _stt_once() -> str:
    """
    Capture audio from the microphone and transcribe with OpenAI Whisper.
    """
    if os.getenv("VOICE_DISABLED") == "1":
        return "create a high priority task to stretch and drink water"

    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(
            source,
            timeout=float(os.getenv("VOICE_LISTEN_TIMEOUT_SECS", "4")),
            phrase_time_limit=float(os.getenv("VOICE_PHRASE_TIME_LIMIT_SECS", "7")),
        )

    # Save to a temporary WAV file, then send to OpenAI audio API
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        with open(tmp.name, "wb") as f:
            f.write(audio.get_wav_data())

        client = _get_openai_client()
        with open(tmp.name, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model=os.getenv("OPENAI_WHISPER_MODEL", "gpt-4o-mini-transcribe"),
                file=f,
            )

    return transcript.text.strip()


def _apply_intent(intent: Dict[str, Any]) -> str:
    t = intent.get("type")
    if t == "add_task":
        title = intent.get("title") or "Untitled task"
        priority = intent.get("priority") or "medium"
        due_date = intent.get("due_date")
        with SessionLocal() as db:
            task = Task(title=title, priority=priority, due_date=due_date)
            db.add(task)
            db.commit()
        try:
            get_serial_manager().send_face("HAPPY")
        except Exception:
            pass
        return f"Added task: {title}"

    if t == "start_timer":
        mins = int(intent.get("duration_minutes") or 25)
        # leaving actual timer start to HTTP clients; here we just summarise
        try:
            get_serial_manager().send_face("FOCUS")
        except Exception:
            pass
        return f"Start a {mins} minute focus timer from the app."

    if t == "set_reminder":
        message = intent.get("message") or "Reminder"
        when = intent.get("time") or ""
        with SessionLocal() as db:
            reminder = Reminder(message=message, trigger_time=when, repeat="none")
            db.add(reminder)
            db.commit()
        try:
            get_serial_manager().send_face("REMINDER")
        except Exception:
            pass
        return f"Reminder set: {message}"

    if t == "list_tasks":
        with SessionLocal() as db:
            count = db.query(Task).filter(Task.completed.is_(False)).count()
        return f"You have {count} open tasks."

    if t == "general_chat":
        return str(intent.get("response") or "OK.")

    return "I am not sure what to do with that yet."


def capture_and_process_once() -> Dict[str, Any]:
    """
    Capture a single utterance, parse intent via OpenAI, apply it, and return a summary.
    """
    try:
        text = _stt_once()
    except Exception as e:
        text = ""
        stt_error = str(e)
    else:
        stt_error = ""

    if not text:
        intent = {"type": "general_chat", "response": "I did not hear anything."}
    else:
        intent = ai_manager.parse_intent(text)

    result_summary = _apply_intent(intent)

    return {
        "text": text,
        "intent": intent,
        "result_summary": result_summary,
        "stt_error": stt_error,
    }

