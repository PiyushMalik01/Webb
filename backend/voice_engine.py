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

# Follow-up tracking
_follow_up_deadline: float = 0.0


def get_state() -> VoiceState:
    with _state_lock:
        return _state


def _set_state(new_state: VoiceState) -> None:
    global _state
    with _state_lock:
        _state = new_state

    # Update ESP32 face
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
    """Transcribe audio using Whisper. In-memory, no temp files."""
    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return ""

        # Encode as WAV in memory
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
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

# Keywords that indicate speech is directed at Webb
TRIGGER_KEYWORDS = [
    "webb", "web", "hey", "open", "close", "search", "start", "stop",
    "set", "add", "what", "how", "can you", "tell me", "show me",
    "play", "pause", "volume", "mute", "switch", "type", "lock",
    "screenshot", "remind", "timer", "task", "delete", "list",
    "minimize", "maximize", "brightness", "next", "previous",
]


def _is_for_webb(text: str) -> bool:
    """Fast keyword check — is this speech directed at Webb?"""
    lower = text.lower().strip()
    if len(lower) < 2:
        return False

    # Direct keyword match
    for kw in TRIGGER_KEYWORDS:
        if kw in lower:
            return True

    # If 4+ words and contains a verb-like word, probably a command
    words = lower.split()
    if len(words) >= 4:
        return True

    return False


def _strip_trigger(text: str) -> str:
    """Remove leading trigger words."""
    lower = text.lower().strip()
    for prefix in ["hey webb ", "hey web ", "hi webb ", "hi web ",
                    "okay webb ", "ok webb ", "yo webb ", "webb ", "web "]:
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
    return text


# ── Speech Handler (called by AudioEngine) ───────────────────

def _on_speech(audio: np.ndarray) -> None:
    """Called by AudioEngine when a complete utterance is captured."""
    global _follow_up_deadline

    current = get_state()

    # If muted (speaking), ignore
    if current == VoiceState.SPEAKING:
        return

    # In follow-up mode: accept all speech without gate check
    if current == VoiceState.FOLLOW_UP:
        with _pending_lock:
            _pending_audio.clear()
            _pending_audio.append(audio)
        _process_event.set()
        return

    # In idle mode: need to pass the gate
    if current in (VoiceState.IDLE,):
        with _pending_lock:
            _pending_audio.clear()
            _pending_audio.append(audio)
        _process_event.set()
        return

    # Otherwise (processing, executing): ignore new audio


def _process_loop() -> None:
    """Background thread that processes captured speech."""
    global _follow_up_deadline

    follow_up_timeout = float(os.getenv("FOLLOW_UP_TIMEOUT_MS", "5000")) / 1000.0

    while not _stop_event.is_set():
        # Check follow-up timeout
        if get_state() == VoiceState.FOLLOW_UP:
            if time.time() > _follow_up_deadline:
                _set_state(VoiceState.IDLE)
                engine = get_audio_engine()
                engine.set_silence_duration(int(os.getenv("VAD_SILENCE_MS", "800")))

        # Wait for speech event
        triggered = _process_event.wait(timeout=0.2)
        if not triggered:
            continue
        _process_event.clear()

        # Get audio
        with _pending_lock:
            if not _pending_audio:
                continue
            audio = _pending_audio.pop(0)

        current = get_state()

        # Transcribe
        _set_state(VoiceState.LISTENING)
        text = _transcribe(audio)

        if not text or len(text.strip()) < 2:
            if current == VoiceState.FOLLOW_UP:
                _set_state(VoiceState.FOLLOW_UP)
            else:
                _set_state(VoiceState.IDLE)
            continue

        print(f"[voice] Heard: \"{text}\"")

        # Gate check (skip in follow-up mode)
        in_follow_up = current == VoiceState.FOLLOW_UP
        if not in_follow_up and not _is_for_webb(text):
            print(f"[voice] Not for Webb, ignoring")
            _set_state(VoiceState.IDLE)
            continue

        # Strip trigger words
        command = _strip_trigger(text)
        print(f"[voice] Processing: \"{command}\"")

        # Process and respond
        _handle_command(command)

        # Enter follow-up window
        _follow_up_deadline = time.time() + follow_up_timeout
        _set_state(VoiceState.FOLLOW_UP)

        # Shorten silence detection for follow-up
        engine = get_audio_engine()
        engine.set_silence_duration(500)


def _handle_command(text: str) -> None:
    """Process a command through the AI brain with streaming TTS."""
    from . import ai_manager
    from . import streaming_tts

    _set_state(VoiceState.PROCESSING)

    # Use streaming for natural sentence-by-sentence speech
    sentences, action_results = ai_manager.process_streamed(text)

    if action_results:
        _set_state(VoiceState.EXECUTING)

    # Speak sentences — each one starts playing as soon as it's generated
    if sentences:
        _set_state(VoiceState.SPEAKING)
        for sentence in sentences:
            if sentence.strip():
                streaming_tts.speak_sync(sentence)


# ── Manual Trigger ───────────────────────────────────────────

def trigger_manual() -> Dict[str, Any]:
    """Manual mic button trigger. Captures speech and processes it."""
    if get_state() not in (VoiceState.IDLE, VoiceState.FOLLOW_UP):
        return {"speak": "I'm already busy.", "actions": [], "face": "IDLE", "action_results": []}

    engine = get_audio_engine()

    # Briefly unmute if muted
    was_muted = engine.muted
    if was_muted:
        engine.unmute()

    _set_state(VoiceState.LISTENING)

    # Capture directly using sounddevice (bypass the callback for manual trigger)
    import sounddevice as sd

    duration = float(os.getenv("VOICE_PHRASE_TIME_LIMIT_SECS", "8"))
    try:
        recording = sd.rec(
            int(duration * 16000),
            samplerate=16000,
            channels=1,
            dtype='int16',
            blocking=True,
        )
        audio = recording[:, 0]
    except Exception as e:
        _set_state(VoiceState.IDLE)
        return {"speak": "", "actions": [], "face": "IDLE", "action_results": [], "stt_error": str(e)}

    # Transcribe
    text = _transcribe(audio)
    if not text:
        _set_state(VoiceState.IDLE)
        return {"speak": "I didn't hear anything.", "actions": [], "face": "IDLE", "action_results": []}

    # Process
    from . import ai_manager
    from . import streaming_tts

    _set_state(VoiceState.PROCESSING)
    sentences, action_results = ai_manager.process_streamed(text)

    speak = " ".join(sentences)

    if sentences:
        _set_state(VoiceState.SPEAKING)
        for s in sentences:
            if s.strip():
                streaming_tts.speak(s)

    # Enter follow-up
    global _follow_up_deadline
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


def interrupt() -> None:
    """Interrupt current speech/processing."""
    from . import streaming_tts
    streaming_tts.interrupt()
    _set_state(VoiceState.IDLE)


# ── Start / Stop ─────────────────────────────────────────────

def start() -> None:
    """Start the voice engine."""
    global _process_thread

    mode = os.getenv("VOICE_MODE", "passive")
    if mode == "disabled":
        print("[voice] Voice engine disabled")
        return

    # Start audio engine with speech callback
    engine = get_audio_engine()
    engine._on_speech = _on_speech

    # Set up mute-on-speak callbacks
    from . import streaming_tts
    streaming_tts.set_callbacks(
        on_start=lambda: engine.mute(),
        on_end=lambda: (time.sleep(0.3), engine.unmute()),  # 300ms grace period
    )

    engine.start()

    # Start processing thread
    if _process_thread is None or not _process_thread.is_alive():
        _stop_event.clear()
        _process_thread = threading.Thread(target=_process_loop, daemon=True)
        _process_thread.start()

    print(f"[voice] Engine started (mode={mode})")


def stop() -> None:
    """Stop the voice engine."""
    _stop_event.set()
    _process_event.set()  # Unblock the wait

    engine = get_audio_engine()
    engine.stop()

    from . import streaming_tts
    streaming_tts.shutdown()

    if _process_thread is not None:
        _process_thread.join(timeout=3.0)
