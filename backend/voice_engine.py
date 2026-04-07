from __future__ import annotations

import io
import os
import threading
import time
import wave
from enum import Enum
from typing import Any, Dict, Optional

import numpy as np


def _log(msg: str) -> None:
    """Print that handles Unicode on Windows console."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode())


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    EXECUTING = "executing"
    FOLLOW_UP = "follow_up"


_state = VoiceState.IDLE
_state_lock = threading.Lock()
_stop_event = threading.Event()
_follow_up_deadline: float = 0.0

# Audio delivery from AudioEngine
_speech_queue: list[np.ndarray] = []
_speech_lock = threading.Lock()
_speech_event = threading.Event()

# Processing thread
_proc_thread: Optional[threading.Thread] = None

# Manual trigger
_manual_result: Optional[Dict[str, Any]] = None
_manual_event = threading.Event()
_manual_mode = False


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


# ── STT ──────────────────────────────────────────────────────

def _transcribe(audio: np.ndarray) -> str:
    """Transcribe audio using Whisper API. In-memory, no temp files."""
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
        _log(f"[voice] STT error: {e}")
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


# ── Speech Callback (from AudioEngine) ───────────────────────

def _on_speech(audio: np.ndarray) -> None:
    """Called by AudioEngine when VAD detects a complete utterance."""
    current = get_state()

    # Ignore if busy
    if current in (VoiceState.SPEAKING, VoiceState.PROCESSING, VoiceState.EXECUTING):
        return

    # If in manual mode, deliver to manual handler
    global _manual_mode
    if _manual_mode:
        with _speech_lock:
            _speech_queue.clear()
            _speech_queue.append(audio)
        _manual_event.set()
        return

    # Normal passive mode: queue for processing
    if current in (VoiceState.IDLE, VoiceState.FOLLOW_UP):
        with _speech_lock:
            _speech_queue.clear()
            _speech_queue.append(audio)
        _speech_event.set()


# ── Process Loop ─────────────────────────────────────────────

def _process_loop() -> None:
    """Background thread that processes speech from the audio engine."""
    global _follow_up_deadline

    follow_up_timeout = float(os.getenv("FOLLOW_UP_TIMEOUT_MS", "5000")) / 1000.0

    while not _stop_event.is_set():
        # Check follow-up timeout
        if get_state() == VoiceState.FOLLOW_UP and time.time() > _follow_up_deadline:
            _set_state(VoiceState.IDLE)
            try:
                from .audio_engine import get_audio_engine
                get_audio_engine().set_silence_duration(int(os.getenv("VAD_SILENCE_MS", "800")))
            except Exception:
                pass

        # Wait for speech
        triggered = _speech_event.wait(timeout=0.3)
        if not triggered:
            continue
        _speech_event.clear()

        # Get audio
        with _speech_lock:
            if not _speech_queue:
                continue
            audio = _speech_queue.pop(0)

        current = get_state()
        in_follow_up = current == VoiceState.FOLLOW_UP

        # Transcribe
        _log("[voice] Transcribing...")
        _set_state(VoiceState.LISTENING)
        try:
            text = _transcribe(audio)
        except Exception as e:
            _log(f"[voice] Transcribe error: {e}")
            _set_state(VoiceState.IDLE)
            continue

        if not text or len(text.strip()) < 2:
            _log("[voice] Empty transcription, ignoring")
            _set_state(VoiceState.FOLLOW_UP if in_follow_up else VoiceState.IDLE)
            continue

        _log(f"[voice] Heard: \"{text}\"")

        # Gate check (skip in follow-up)
        if not in_follow_up and not _is_for_webb(text):
            _log(f"[voice] Not for Webb, ignoring")
            _set_state(VoiceState.IDLE)
            continue

        command = _strip_trigger(text)
        if not command:
            _set_state(VoiceState.IDLE)
            continue

        _log(f"[voice] Command: \"{command}\"")

        # Process
        try:
            _handle_command(command)
        except Exception as e:
            _log(f"[voice] Command error: {e}")

        # Enter follow-up window
        _follow_up_deadline = time.time() + follow_up_timeout
        _set_state(VoiceState.FOLLOW_UP)
        try:
            from .audio_engine import get_audio_engine
            get_audio_engine().set_silence_duration(500)
        except Exception:
            pass


def _handle_command(text: str) -> None:
    """Process command through AI brain + streaming TTS."""
    from . import ai_manager
    from . import streaming_tts

    _set_state(VoiceState.PROCESSING)

    try:
        sentences, action_results = ai_manager.process_streamed(text)
    except Exception as e:
        _log(f"[voice] AI error: {e}")
        _set_state(VoiceState.IDLE)
        return

    if action_results:
        _set_state(VoiceState.EXECUTING)

    if sentences:
        _set_state(VoiceState.SPEAKING)
        for sentence in sentences:
            s = sentence.strip()
            if s:
                try:
                    streaming_tts.speak_sync(s)
                except Exception as e:
                    _log(f"[voice] TTS error: {e}")


# ── Manual Trigger ───────────────────────────────────────────

def trigger_manual() -> Dict[str, Any]:
    """
    Manual mic button. Uses the SAME audio engine (no conflicting streams).
    Temporarily enters manual mode so the next speech detection goes here.
    """
    global _manual_mode, _manual_result, _follow_up_deadline

    if get_state() not in (VoiceState.IDLE, VoiceState.FOLLOW_UP):
        return {"speak": "I'm already busy.", "actions": [], "face": "IDLE", "action_results": []}

    _set_state(VoiceState.LISTENING)
    _manual_event.clear()
    _manual_result = None
    _manual_mode = True

    try:
        # Wait for the audio engine to deliver speech (max 10s)
        got_audio = _manual_event.wait(timeout=10.0)

        if not got_audio:
            _manual_mode = False
            _set_state(VoiceState.IDLE)
            return {"speak": "I didn't hear anything.", "actions": [], "face": "IDLE", "action_results": []}

        # Get the audio
        with _speech_lock:
            if not _speech_queue:
                _manual_mode = False
                _set_state(VoiceState.IDLE)
                return {"speak": "I didn't hear anything.", "actions": [], "face": "IDLE", "action_results": []}
            audio = _speech_queue.pop(0)

        _manual_mode = False

        # Transcribe
        text = _transcribe(audio)
        if not text:
            _set_state(VoiceState.IDLE)
            return {"speak": "I didn't hear anything.", "actions": [], "face": "IDLE", "action_results": []}

        text = _strip_trigger(text)
        _log(f"[voice] Manual: \"{text}\"")

        # Process
        from . import ai_manager
        from . import streaming_tts

        _set_state(VoiceState.PROCESSING)
        try:
            sentences, action_results = ai_manager.process_streamed(text)
        except Exception as e:
            _set_state(VoiceState.IDLE)
            return {"speak": "Sorry, something went wrong.", "actions": [], "face": "SAD", "action_results": []}

        speak = " ".join(s.strip() for s in sentences if s.strip())

        if sentences:
            _set_state(VoiceState.SPEAKING)
            for s in sentences:
                if s.strip():
                    streaming_tts.speak(s)

        _follow_up_deadline = time.time() + 5.0
        _set_state(VoiceState.FOLLOW_UP)

        return {
            "text": text,
            "speak": speak,
            "actions": [],
            "face": "HAPPY" if action_results else "IDLE",
            "action_results": [{"name": a["name"], "result": a["result"]} for a in action_results],
            "stt_error": "",
        }

    except Exception as e:
        _manual_mode = False
        _set_state(VoiceState.IDLE)
        return {"speak": "", "actions": [], "face": "IDLE", "action_results": [], "stt_error": str(e)}


def interrupt() -> None:
    from . import streaming_tts
    streaming_tts.interrupt()
    _set_state(VoiceState.IDLE)


# ── Start / Stop ─────────────────────────────────────────────

def start() -> None:
    global _proc_thread

    mode = os.getenv("VOICE_MODE", "passive")
    if mode == "disabled":
        _log("[voice] Voice engine disabled")
        return

    # Start audio engine
    from .audio_engine import get_audio_engine
    engine = get_audio_engine()
    engine._on_speech = _on_speech

    # Mute-on-speak
    from . import streaming_tts
    streaming_tts.set_callbacks(
        on_start=lambda: engine.mute(),
        on_end=lambda: _delayed_unmute(engine),
    )

    engine.start()

    # Start process loop
    if _proc_thread is None or not _proc_thread.is_alive():
        _stop_event.clear()
        _proc_thread = threading.Thread(target=_process_loop, daemon=True)
        _proc_thread.start()

    _log(f"[voice] Engine started (mode={mode})")


def _delayed_unmute(engine):
    time.sleep(0.3)
    engine.unmute()


def stop() -> None:
    _stop_event.set()
    _speech_event.set()
    _manual_event.set()

    try:
        from .audio_engine import get_audio_engine
        get_audio_engine().stop()
    except Exception:
        pass

    try:
        from . import streaming_tts
        streaming_tts.shutdown()
    except Exception:
        pass

    if _proc_thread is not None:
        _proc_thread.join(timeout=3.0)
