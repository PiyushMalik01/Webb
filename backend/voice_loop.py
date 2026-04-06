from __future__ import annotations

import os
import tempfile
import threading
import time
from enum import Enum
from typing import Any, Dict, Optional

import speech_recognition as sr

from .notifications_hub import hub


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    EXECUTING = "executing"


_state = VoiceState.IDLE
_state_lock = threading.Lock()
_stop_event = threading.Event()
_listen_thread: Optional[threading.Thread] = None

# Trigger words — Webb only activates on these
TRIGGER_WORDS = [
    "hey webb", "hey web", "hey wab", "a web", "he web",
    "hi webb", "hi web", "okay webb", "ok webb",
    "webb", "web",
]


def get_state() -> VoiceState:
    with _state_lock:
        return _state


def _set_state(new_state: VoiceState) -> None:
    global _state
    with _state_lock:
        _state = new_state

    # Update face on ESP32 — only for meaningful state changes
    face_map = {
        VoiceState.LISTENING: "LISTENING",
        VoiceState.PROCESSING: "THINKING",
        VoiceState.SPEAKING: "SPEAKING",
        VoiceState.EXECUTING: "FOCUS",
        VoiceState.IDLE: "IDLE",
    }
    try:
        from .serial_manager import get_serial_manager
        get_serial_manager().send_face(face_map.get(new_state, "IDLE"))
    except Exception:
        pass


def _fast_transcribe(audio_data) -> str:
    """Transcribe audio using Whisper. Returns empty string on failure."""
    tmp_path = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.write(audio_data.get_wav_data())
        tmp.close()

        from .voice_manager import _get_openai_client
        client = _get_openai_client()
        with open(tmp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model=os.getenv("OPENAI_WHISPER_MODEL", "gpt-4o-mini-transcribe"),
                file=f,
                language="en",
            )
        return transcript.text.strip()
    except Exception as e:
        print(f"[voice] STT error: {e}")
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _process_and_respond(text: str) -> Dict[str, Any]:
    """Process through AI brain, execute actions, speak response."""
    from . import ai_manager
    from . import tts_manager

    _set_state(VoiceState.PROCESSING)
    result = ai_manager.process_message(text)

    speak_text = result.get("speak", "")
    face = result.get("face", "HAPPY")

    if result.get("action_results"):
        _set_state(VoiceState.EXECUTING)
        time.sleep(0.3)

    try:
        from .serial_manager import get_serial_manager
        get_serial_manager().send_face(face)
    except Exception:
        pass

    if speak_text:
        _set_state(VoiceState.SPEAKING)
        tts_manager.speak_sync(speak_text)

    _set_state(VoiceState.IDLE)
    return result


def _check_trigger(text: str) -> tuple[bool, str]:
    """
    Check if text starts with a trigger word.
    Returns (triggered, remaining_command).
    """
    lower = text.lower().strip()
    if not lower:
        return False, ""

    for trigger in sorted(TRIGGER_WORDS, key=len, reverse=True):
        if lower.startswith(trigger):
            remainder = text[len(trigger):].strip().lstrip(",.!? ")
            return True, remainder
        # Also check with slight variations (Whisper might hear "web" as "Webb")
        if lower == trigger:
            return True, ""

    return False, ""


def _capture_full_command() -> str:
    """Capture a full voice command after activation. Waits for the user to finish speaking."""
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.5  # Wait 1.5s of silence before considering speech done
    recognizer.phrase_threshold = 0.3

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(
                source,
                timeout=5.0,           # Wait up to 5s for speech to start
                phrase_time_limit=15.0,  # Allow up to 15s of continuous speech
            )
        return _fast_transcribe(audio)
    except sr.WaitTimeoutError:
        return ""
    except Exception as e:
        print(f"[voice] Capture error: {e}")
        return ""


# ── Passive Listening ────────────────────────────────────────

def _passive_listen_loop() -> None:
    """
    Passive listening: listen for trigger words only.
    Does NOT process random speech — only activates on "Webb", "Hey Webb", etc.
    Uses short capture windows to detect trigger words quickly.
    """
    print("[voice_loop] Passive listening active — say 'Hey Webb' to activate")

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8   # Short pause = end of trigger phrase
    recognizer.phrase_threshold = 0.2

    while not _stop_event.is_set():
        if get_state() != VoiceState.IDLE:
            time.sleep(0.2)
            continue

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.2)
                try:
                    # Short listen window — just enough to catch trigger words
                    audio = recognizer.listen(
                        source,
                        timeout=None,          # Wait indefinitely for speech
                        phrase_time_limit=5.0,  # But each phrase max 5s
                    )
                except sr.WaitTimeoutError:
                    continue

            # Transcribe what we heard
            text = _fast_transcribe(audio)
            if not text:
                continue

            # Check for trigger
            triggered, remainder = _check_trigger(text)
            if not triggered:
                # Not for us — ignore silently
                continue

            print(f"[voice_loop] Triggered! Heard: \"{text}\"")

            if remainder and len(remainder.split()) >= 2:
                # Full command in the trigger phrase: "Hey Webb open Chrome"
                print(f"[voice_loop] Command: \"{remainder}\"")
                _process_and_respond(remainder)
            else:
                # Just trigger word — acknowledge and listen for command
                from . import tts_manager
                _set_state(VoiceState.LISTENING)
                tts_manager.speak_sync("Yes?")

                # Now capture the full command
                _set_state(VoiceState.LISTENING)
                command = _capture_full_command()

                if command:
                    print(f"[voice_loop] Command: \"{command}\"")
                    _process_and_respond(command)
                else:
                    _set_state(VoiceState.IDLE)

        except Exception as e:
            print(f"[voice_loop] Error: {e}")
            _set_state(VoiceState.IDLE)
            time.sleep(0.5)


# ── Wake Word Loop (Picovoice) ───────────────────────────────

def _wake_word_loop() -> None:
    """Wake word detection using Picovoice Porcupine."""
    access_key = os.getenv("PICOVOICE_ACCESS_KEY", "")
    if not access_key:
        print("[voice_loop] PICOVOICE_ACCESS_KEY not set.")
        return

    try:
        import pvporcupine
        import pvrecorder
    except ImportError:
        print("[voice_loop] pvporcupine/pvrecorder not installed.")
        return

    porcupine = None
    recorder = None

    try:
        keyword_paths = None
        keywords = None

        custom_keyword = os.getenv("WAKE_WORD_PATH")
        if custom_keyword and os.path.exists(custom_keyword):
            keyword_paths = [custom_keyword]
        else:
            keywords = ["hey google"]

        sensitivity = float(os.getenv("WAKE_WORD_SENSITIVITY", "0.5"))

        porcupine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=keyword_paths,
            keywords=keywords,
            sensitivities=[sensitivity],
        )

        recorder = pvrecorder.PvRecorder(
            frame_length=porcupine.frame_length,
            device_index=-1,
        )
        recorder.start()

        print(f"[voice_loop] Wake word active")

        while not _stop_event.is_set():
            if get_state() != VoiceState.IDLE:
                time.sleep(0.1)
                continue

            pcm = recorder.read()
            if porcupine.process(pcm) >= 0:
                print("[voice_loop] Wake word detected!")
                from . import tts_manager
                _set_state(VoiceState.LISTENING)
                tts_manager.speak_sync("Yes?")

                _set_state(VoiceState.LISTENING)
                command = _capture_full_command()
                if command:
                    _process_and_respond(command)
                else:
                    _set_state(VoiceState.IDLE)

    except Exception as e:
        print(f"[voice_loop] Wake word error: {e}")
    finally:
        if recorder:
            try:
                recorder.stop()
                recorder.delete()
            except Exception:
                pass
        if porcupine:
            try:
                porcupine.delete()
            except Exception:
                pass


# ── Manual Trigger ───────────────────────────────────────────

def trigger_manual() -> Dict[str, Any]:
    """Manually trigger voice capture from mic button."""
    if get_state() != VoiceState.IDLE:
        return {"speak": "I'm already busy.", "actions": [], "face": "IDLE", "action_results": []}

    _set_state(VoiceState.LISTENING)
    command = _capture_full_command()

    if not command:
        _set_state(VoiceState.IDLE)
        return {"speak": "I didn't hear anything.", "actions": [], "face": "IDLE", "action_results": []}

    result = _process_and_respond(command)

    return {
        "text": command,
        "speak": result.get("speak", ""),
        "actions": result.get("actions", []),
        "face": result.get("face", "IDLE"),
        "action_results": result.get("action_results", []),
        "stt_error": "",
    }


def interrupt() -> None:
    """Interrupt current voice processing."""
    from . import tts_manager
    tts_manager.interrupt()
    _set_state(VoiceState.IDLE)


# ── Start / Stop ─────────────────────────────────────────────

def start() -> None:
    """Start the voice loop."""
    global _listen_thread

    if _listen_thread is not None and _listen_thread.is_alive():
        return

    _stop_event.clear()

    if os.getenv("WAKE_WORD_ENABLED", "0") == "1":
        _listen_thread = threading.Thread(target=_wake_word_loop, daemon=True)
        _listen_thread.start()
    elif os.getenv("PASSIVE_LISTENING", "1") == "1":
        _listen_thread = threading.Thread(target=_passive_listen_loop, daemon=True)
        _listen_thread.start()
    else:
        print("[voice_loop] No listening mode enabled. Use mic button only.")


def stop() -> None:
    """Stop the voice loop."""
    _stop_event.set()
    if _listen_thread is not None:
        _listen_thread.join(timeout=3.0)
