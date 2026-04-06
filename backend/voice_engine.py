from __future__ import annotations

import io
import os
import threading
import time
import wave
from enum import Enum
from typing import Any, Dict, Optional

import numpy as np

from .audio_engine import get_audio_engine
from .notifications_hub import hub


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    EXECUTING = "executing"
    FOLLOW_UP = "follow_up"


_state = VoiceState.IDLE
_state_lock = threading.Lock()
_pending_audio: list[np.ndarray] = []
_pending_lock = threading.Lock()
_process_event = threading.Event()
_stop_event = threading.Event()
_process_thread: Optional[threading.Thread] = None
_follow_up_deadline: float = 0.0


def get_state() -> VoiceState:
    with _state_lock:
        return _state


def _set_state(new_state: VoiceState) -> None:
    global _state
    with _state_lock:
        _state = new_state

    face_map = {
        VoiceState.IDLE: "IDLE",
        VoiceState.LISTENING: "LISTENING",
        VoiceState.PROCESSING: "THINKING",
        VoiceState.SPEAKING: "SPEAKING",
        VoiceState.EXECUTING: "FOCUS",
        VoiceState.FOLLOW_UP: "IDLE",
    }
    try:
        from .serial_manager import get_serial_manager
        get_serial_manager().send_face(face_map.get(new_state, "IDLE"))
    except Exception:
        pass


# ── STT (in-memory, no temp files) ──────────────────────────

def _transcribe(audio: np.ndarray) -> str:
    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return ""

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio.astype(np.int16).tobytes())
        buf.seek(0)
        buf.name = "audio.wav"

        client = OpenAI(api_key=api_key, timeout=10.0)
        transcript = client.audio.transcriptions.create(
            model=os.getenv("OPENAI_WHISPER_MODEL", "gpt-4o-mini-transcribe"),
            file=buf,
            language="en",
        )
        return transcript.text.strip()
    except Exception as e:
        print(f"[voice] STT error: {e}")
        return ""


# ── Gate ─────────────────────────────────────────────────────

TRIGGER_KEYWORDS = [
    "webb", "web", "hey", "open", "close", "search", "start", "stop",
    "set", "add", "what", "how", "can you", "tell me", "show me",
    "play", "pause", "volume", "mute", "switch", "type", "lock",
    "screenshot", "remind", "timer", "task", "delete", "list",
    "minimize", "maximize", "brightness", "next", "previous",
    "alarm", "wake",
]


def _is_for_webb(text: str) -> bool:
    lower = text.lower().strip()
    if len(lower) < 2:
        return False
    for kw in TRIGGER_KEYWORDS:
        if kw in lower:
            return True
    if len(lower.split()) >= 4:
        return True
    return False


def _strip_trigger(text: str) -> str:
    lower = text.lower().strip()
    for prefix in ["hey webb ", "hey web ", "hi webb ", "hi web ",
                    "okay webb ", "ok webb ", "yo webb ", "webb ", "web "]:
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
    return text


# ── Speech Handler ───────────────────────────────────────────

def _on_speech(audio: np.ndarray) -> None:
    current = get_state()

    # Ignore during speaking (mute-on-speak)
    if current == VoiceState.SPEAKING:
        return

    # Ignore if already busy (processing/executing)
    if current in (VoiceState.PROCESSING, VoiceState.EXECUTING, VoiceState.LISTENING):
        return

    # Accept in follow-up or idle
    with _pending_lock:
        _pending_audio.clear()
        _pending_audio.append(audio)
    _process_event.set()


# ── Process Loop ─────────────────────────────────────────────

def _process_loop() -> None:
    global _follow_up_deadline

    follow_up_timeout = float(os.getenv("FOLLOW_UP_TIMEOUT_MS", "5000")) / 1000.0

    while not _stop_event.is_set():
        # Check follow-up timeout
        if get_state() == VoiceState.FOLLOW_UP:
            if time.time() > _follow_up_deadline:
                _set_state(VoiceState.IDLE)
                try:
                    get_audio_engine().set_silence_duration(int(os.getenv("VAD_SILENCE_MS", "800")))
                except Exception:
                    pass

        triggered = _process_event.wait(timeout=0.3)
        if not triggered:
            continue
        _process_event.clear()

        with _pending_lock:
            if not _pending_audio:
                continue
            audio = _pending_audio.pop(0)

        current = get_state()

        # Transcribe
        _set_state(VoiceState.LISTENING)
        try:
            text = _transcribe(audio)
        except Exception as e:
            print(f"[voice] Transcribe failed: {e}")
            _set_state(VoiceState.IDLE)
            continue

        if not text or len(text.strip()) < 2:
            _set_state(VoiceState.FOLLOW_UP if current == VoiceState.FOLLOW_UP else VoiceState.IDLE)
            continue

        print(f"[voice] Heard: \"{text}\"")

        # Gate check (skip in follow-up)
        in_follow_up = current == VoiceState.FOLLOW_UP
        if not in_follow_up and not _is_for_webb(text):
            print(f"[voice] Not for Webb, ignoring")
            _set_state(VoiceState.IDLE)
            continue

        command = _strip_trigger(text)
        print(f"[voice] Command: \"{command}\"")

        # Process with timeout protection
        try:
            _handle_command(command)
        except Exception as e:
            print(f"[voice] Command failed: {e}")
            _set_state(VoiceState.IDLE)
            continue

        # Enter follow-up window
        _follow_up_deadline = time.time() + follow_up_timeout
        _set_state(VoiceState.FOLLOW_UP)
        try:
            get_audio_engine().set_silence_duration(500)
        except Exception:
            pass


def _handle_command(text: str) -> None:
    from . import ai_manager
    from . import streaming_tts

    _set_state(VoiceState.PROCESSING)

    try:
        sentences, action_results = ai_manager.process_streamed(text)
    except Exception as e:
        print(f"[voice] AI error: {e}")
        _set_state(VoiceState.IDLE)
        return

    if action_results:
        _set_state(VoiceState.EXECUTING)

    if sentences:
        _set_state(VoiceState.SPEAKING)
        for sentence in sentences:
            if sentence.strip():
                try:
                    streaming_tts.speak_sync(sentence)
                except Exception:
                    pass


# ── Manual Trigger (non-blocking) ────────────────────────────

_manual_result: Optional[Dict[str, Any]] = None
_manual_done = threading.Event()


def trigger_manual() -> Dict[str, Any]:
    """
    Manual mic button. Runs in a background thread to not block FastAPI.
    Uses a short recording window with VAD-based end detection.
    """
    global _manual_result

    if get_state() not in (VoiceState.IDLE, VoiceState.FOLLOW_UP):
        return {"speak": "I'm already busy.", "actions": [], "face": "IDLE", "action_results": []}

    _manual_done.clear()
    _manual_result = None

    t = threading.Thread(target=_manual_capture_and_process, daemon=True)
    t.start()
    t.join(timeout=30)  # Max 30s timeout

    if _manual_result is not None:
        return _manual_result

    _set_state(VoiceState.IDLE)
    return {"speak": "Something went wrong.", "actions": [], "face": "IDLE", "action_results": []}


def _manual_capture_and_process():
    global _manual_result, _follow_up_deadline

    engine = get_audio_engine()
    was_muted = engine.muted
    if was_muted:
        engine.unmute()

    _set_state(VoiceState.LISTENING)

    # Record for up to 6 seconds
    import sounddevice as sd
    try:
        duration = 6.0
        recording = sd.rec(
            int(duration * 16000),
            samplerate=16000,
            channels=1,
            dtype='int16',
        )
        sd.wait()  # Wait for recording to finish
        audio = recording[:, 0]
    except Exception as e:
        _manual_result = {"speak": "", "actions": [], "face": "IDLE", "action_results": [], "stt_error": str(e)}
        _set_state(VoiceState.IDLE)
        return

    # Transcribe
    text = _transcribe(audio)
    if not text:
        _manual_result = {"speak": "I didn't hear anything.", "actions": [], "face": "IDLE", "action_results": []}
        _set_state(VoiceState.IDLE)
        return

    text = _strip_trigger(text)
    print(f"[voice] Manual: \"{text}\"")

    # Process
    from . import ai_manager
    from . import streaming_tts

    _set_state(VoiceState.PROCESSING)
    try:
        sentences, action_results = ai_manager.process_streamed(text)
    except Exception as e:
        _manual_result = {"speak": "Sorry, something went wrong.", "actions": [], "face": "SAD", "action_results": []}
        _set_state(VoiceState.IDLE)
        return

    speak = " ".join(s for s in sentences if s.strip())

    if sentences:
        _set_state(VoiceState.SPEAKING)
        for s in sentences:
            if s.strip():
                streaming_tts.speak(s)

    _follow_up_deadline = time.time() + 5.0
    _set_state(VoiceState.FOLLOW_UP)

    _manual_result = {
        "text": text,
        "speak": speak,
        "actions": [],
        "face": "HAPPY" if action_results else "IDLE",
        "action_results": [{"name": a["name"], "result": a["result"]} for a in action_results],
        "stt_error": "",
    }


def interrupt() -> None:
    from . import streaming_tts
    streaming_tts.interrupt()
    _set_state(VoiceState.IDLE)


# ── Start / Stop ─────────────────────────────────────────────

def start() -> None:
    global _process_thread

    mode = os.getenv("VOICE_MODE", "passive")
    if mode == "disabled":
        print("[voice] Voice engine disabled")
        return

    engine = get_audio_engine()
    engine._on_speech = _on_speech

    from . import streaming_tts
    streaming_tts.set_callbacks(
        on_start=lambda: engine.mute(),
        on_end=lambda: _delayed_unmute(engine),
    )

    engine.start()

    if _process_thread is None or not _process_thread.is_alive():
        _stop_event.clear()
        _process_thread = threading.Thread(target=_process_loop, daemon=True)
        _process_thread.start()

    print(f"[voice] Engine started (mode={mode})")


def _delayed_unmute(engine):
    """Unmute after a short delay to avoid echo."""
    time.sleep(0.3)
    engine.unmute()


def stop() -> None:
    _stop_event.set()
    _process_event.set()

    try:
        get_audio_engine().stop()
    except Exception:
        pass

    try:
        from . import streaming_tts
        streaming_tts.shutdown()
    except Exception:
        pass

    if _process_thread is not None:
        _process_thread.join(timeout=3.0)
