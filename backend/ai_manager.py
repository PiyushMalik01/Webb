from __future__ import annotations

import json
import os
from typing import Any, Dict

from openai import OpenAI


SYSTEM_PROMPT = """
You are Webb, a helpful desk companion.
You receive short user commands as plain text and must convert them into a SINGLE JSON intent.

Supported intents (choose exactly one, set only the fields you can infer):
- add_task: { "type": "add_task", "title": str, "priority": "low"|"medium"|"high"|null, "due_date": str|null }
- complete_task: { "type": "complete_task", "title": str|null }
- start_timer: { "type": "start_timer", "duration_minutes": int }
- set_reminder: { "type": "set_reminder", "message": str, "time": str }
- list_tasks: { "type": "list_tasks" }
- general_chat: { "type": "general_chat", "response": str }

Return ONLY minified JSON, with no explanations.
"""


NUDGE_SYSTEM_PROMPT = """
You are a supportive productivity coach.
Respond with exactly one short motivational sentence (max 18 words), plain text only.
"""


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key, timeout=20.0)


def parse_intent(text: str) -> Dict[str, Any]:
    """
    Call an OpenAI chat model to map free-form text into a structured intent dict.
    Falls back to a simple general_chat intent when the API is unavailable.
    """
    text = text.strip()
    if not text:
        return {"type": "general_chat", "response": "I did not hear anything."}

    try:
        client = _get_client()
    except Exception:
        return {"type": "general_chat", "response": text}

    try:
        completion = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            max_tokens=256,
        )
        content = completion.choices[0].message.content or ""
        data = json.loads(content)
        if isinstance(data, dict) and "type" in data:
            return data
    except Exception:
        pass

    return {"type": "general_chat", "response": text}


def generate_idle_nudge() -> str:
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


