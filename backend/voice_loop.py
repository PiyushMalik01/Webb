from __future__ import annotations

import os
import tempfile
import threading
import time
from enum import Enum
from typing import Any, Dict, Optional

import speech_recognition as sr


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


def get_state() -> VoiceState:
    with _state_lock:
        return _state


def _set_state(new_state: VoiceState) -> None:
    global _state
    with _state_lock:
        _state = new_state

    # Update face on ESP32
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


# ── Fast STT ─────────────────────────────────────────────────

def _fast_transcribe(audio_data) -> str:
    """Transcribe audio. Returns empty string on failure."""
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


# ── Process & Respond ────────────────────────────────────────

def _process_and_respond(text: str) -> Dict[str, Any]:
    """Process through AI brain, execute actions, speak response. Optimized for speed."""
    from . import ai_manager
    from . import tts_manager

    _set_state(VoiceState.PROCESSING)
    result = ai_manager.process_message(text)

    speak_text = result.get("speak", "")
    face = result.get("face", "HAPPY")

    # Set face immediately
    try:
        from .serial_manager import get_serial_manager
        get_serial_manager().send_face(face)
    except Exception:
        pass

    # Execute actions (no artificial delay)
    if result.get("action_results"):
        _set_state(VoiceState.EXECUTING)

    # Speak response
    if speak_text:
        _set_state(VoiceState.SPEAKING)
        tts_manager.speak_sync(speak_text)

    _set_state(VoiceState.IDLE)
    return result


# ── Passive Listening ────────────────────────────────────────

def _passive_listen_loop() -> None:
    """
    Smart passive listening:
    1. Wait for speech (energy-based, no constant API calls)
    2. Transcribe what was said
    3. Use AI classifier to determine if it's directed at Webb
    4. Only process if it is — ignore everything else silently
    """
    print("[voice_loop] Passive listening active — talk to Webb naturally")

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.energy_threshold = 300  # Adjust based on ambient noise
    recognizer.pause_threshold = 1.2   # 1.2s silence = end of phrase
    recognizer.phrase_threshold = 0.3
    recognizer.non_speaking_duration = 0.5

    while not _stop_event.is_set():
        if get_state() != VoiceState.IDLE:
            time.sleep(0.1)
            continue

        try:
            # Step 1: Wait for speech (blocks until voice detected, zero CPU)
            with sr.Microphone() as source:
                # Brief ambient noise calibration (only first time is slow)
                recognizer.adjust_for_ambient_noise(source, duration=0.15)
                try:
                    audio = recognizer.listen(
                        source,
                        timeout=None,           # Wait forever for speech
                        phrase_time_limit=12.0,  # Max 12s per phrase
                    )
                except sr.WaitTimeoutError:
                    continue

            # Step 2: Transcribe
            text = _fast_transcribe(audio)
            if not text or len(text.strip()) < 2:
                continue

            # Step 3: Is this directed at Webb? (fast classifier)
            from . import ai_manager
            if not ai_manager.is_directed_at_webb(text):
                # Not for Webb — silently ignore
                continue

            print(f"[voice_loop] For Webb: \"{text}\"")

            # Step 4: Strip trigger words if present
            command = _strip_trigger(text)

            # Step 5: Process
            _process_and_respond(command)

        except Exception as e:
            if "aborted" not in str(e).lower():
                print(f"[voice_loop] Error: {e}")
            _set_state(VoiceState.IDLE)
            time.sleep(0.3)


def _strip_trigger(text: str) -> str:
    """Remove leading trigger words like 'hey webb' from the command."""
    lower = text.lower().strip()
    prefixes = [
        "hey webb ", "hey web ", "hi webb ", "hi web ",
        "okay webb ", "ok webb ", "yo webb ",
        "webb ", "web ",
    ]
    for prefix in prefixes:
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
    return text


# ── Wake Word Loop (Picovoice) ───────────────────────────────

def _wake_word_loop() -> None:
    """Wake word detection using Picovoice Porcupine."""
    access_key = os.getenv("PICOVOICE_ACCESS_KEY", "")
    if not access_key:
        return

    try:
        import pvporcupine
        import pvrecorder
    except ImportError:
        return

    porcupine = None
    recorder = None

    try:
        custom_keyword = os.getenv("WAKE_WORD_PATH")
        if custom_keyword and os.path.exists(custom_keyword):
            keyword_paths = [custom_keyword]
            keywords = None
        else:
            keyword_paths = None
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

        print("[voice_loop] Wake word active")

        while not _stop_event.is_set():
            if get_state() != VoiceState.IDLE:
                time.sleep(0.1)
                continue

            pcm = recorder.read()
            if porcupine.process(pcm) >= 0:
                _set_state(VoiceState.LISTENING)
                command = _capture_command()
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


def _capture_command() -> str:
    """Capture a voice command with proper silence detection."""
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.5
    recognizer.phrase_threshold = 0.3

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            audio = recognizer.listen(
                source,
                timeout=5.0,
                phrase_time_limit=15.0,
            )
        return _fast_transcribe(audio)
    except sr.WaitTimeoutError:
        return ""
    except Exception:
        return ""


# ── Manual Trigger ───────────────────────────────────────────

def trigger_manual() -> Dict[str, Any]:
    """Manually trigger voice capture from mic button."""
    if get_state() != VoiceState.IDLE:
        return {"speak": "I'm already busy.", "actions": [], "face": "IDLE", "action_results": []}

    _set_state(VoiceState.LISTENING)
    command = _capture_command()

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
    from . import tts_manager
    tts_manager.interrupt()
    _set_state(VoiceState.IDLE)


# ── Start / Stop ─────────────────────────────────────────────

def start() -> None:
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
        print("[voice_loop] No listening mode. Use mic button only.")


def stop() -> None:
    _stop_event.set()
    if _listen_thread is not None:
        _listen_thread.join(timeout=3.0)
