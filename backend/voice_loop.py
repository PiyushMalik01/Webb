from __future__ import annotations

import os
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

# Trigger words that activate Webb from passive listening
TRIGGER_WORDS = {
    "webb", "web", "hey webb", "hey web", "hey", "yo", "hello",
    "hi webb", "hi web", "okay webb", "ok webb",
}

# Words/phrases to ignore (background noise, filler that isn't directed at Webb)
IGNORE_PHRASES = {
    "", "you", "the", "a", "an", "um", "uh", "hmm", "huh",
    "thank you", "thanks", "bye", "okay",
}


def get_state() -> VoiceState:
    with _state_lock:
        return _state


def _set_state(new_state: VoiceState) -> None:
    global _state
    with _state_lock:
        _state = new_state

    hub.publish_threadsafe({
        "type": "voice_state",
        "state": new_state.value,
        "created_at": __import__("datetime").datetime.utcnow().isoformat(),
    })

    face_map = {
        VoiceState.IDLE: "IDLE",
        VoiceState.LISTENING: "LISTENING",
        VoiceState.PROCESSING: "SURPRISED",
        VoiceState.SPEAKING: "HAPPY",
        VoiceState.EXECUTING: "FOCUS",
    }
    try:
        from .serial_manager import get_serial_manager
        get_serial_manager().send_face(face_map.get(new_state, "IDLE"))
    except Exception:
        pass


def _capture_speech() -> str:
    """Capture and transcribe speech using existing voice_manager."""
    from .voice_manager import _stt_once
    return _stt_once()


def _process_and_respond(text: str) -> Dict[str, Any]:
    """Process speech through AI brain, execute actions, speak response."""
    from . import ai_manager
    from . import tts_manager

    _set_state(VoiceState.PROCESSING)
    result = ai_manager.process_message(text)

    speak_text = result.get("speak", "")
    face = result.get("face", "HAPPY")

    if result.get("action_results"):
        _set_state(VoiceState.EXECUTING)
        time.sleep(0.5)

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


def _is_trigger(text: str) -> bool:
    """Check if the transcribed text contains a trigger word or is directed at Webb."""
    lower = text.lower().strip()
    if lower in IGNORE_PHRASES:
        return False
    # Check if any trigger word is in the text
    for trigger in TRIGGER_WORDS:
        if trigger in lower:
            return True
    # If it's a substantial sentence (4+ words), treat as a command
    if len(lower.split()) >= 4:
        return True
    return False


def _extract_command(text: str) -> str:
    """Strip trigger words from the beginning to get the actual command."""
    lower = text.lower().strip()
    # Remove leading trigger words
    for trigger in sorted(TRIGGER_WORDS, key=len, reverse=True):
        if lower.startswith(trigger):
            remainder = text[len(trigger):].strip()
            # Remove trailing comma, period, or leading punctuation
            remainder = remainder.lstrip(",.!? ")
            if remainder:
                return remainder
    return text


# ── Passive Listening Loop ───────────────────────────────────

def _passive_listen_loop() -> None:
    """
    Passive listening: continuously capture short audio clips,
    transcribe them, and activate if trigger words are detected
    or if the user says something substantial.
    """
    print("[voice_loop] Passive listening started")

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.0

    while not _stop_event.is_set():
        if get_state() != VoiceState.IDLE:
            time.sleep(0.3)
            continue

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                try:
                    audio = recognizer.listen(
                        source,
                        timeout=3.0,
                        phrase_time_limit=8.0,
                    )
                except sr.WaitTimeoutError:
                    continue

            # Quick transcribe
            _set_state(VoiceState.LISTENING)

            from .voice_manager import _get_openai_client
            import tempfile

            tmp_path = None
            try:
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp_path = tmp.name
                tmp.write(audio.get_wav_data())
                tmp.close()

                client = _get_openai_client()
                with open(tmp_path, "rb") as f:
                    transcript = client.audio.transcriptions.create(
                        model=os.getenv("OPENAI_WHISPER_MODEL", "gpt-4o-mini-transcribe"),
                        file=f,
                        language="en",
                    )
                text = transcript.text.strip()
            finally:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

            if not text:
                _set_state(VoiceState.IDLE)
                continue

            print(f"[voice_loop] Heard: \"{text}\"")

            if _is_trigger(text):
                command = _extract_command(text)
                # If it's just a trigger word with no command, prompt for more
                if not command or command.lower() in TRIGGER_WORDS:
                    from . import tts_manager
                    tts_manager.speak("Yes?")
                    _set_state(VoiceState.IDLE)

                    # Wait for the follow-up command
                    time.sleep(0.5)
                    try:
                        _set_state(VoiceState.LISTENING)
                        follow_up = _capture_speech()
                        if follow_up.strip():
                            print(f"[voice_loop] Follow-up: \"{follow_up}\"")
                            _process_and_respond(follow_up)
                        else:
                            _set_state(VoiceState.IDLE)
                    except Exception:
                        _set_state(VoiceState.IDLE)
                else:
                    print(f"[voice_loop] Command: \"{command}\"")
                    _process_and_respond(command)
            else:
                _set_state(VoiceState.IDLE)

        except Exception as e:
            print(f"[voice_loop] Passive listen error: {e}")
            _set_state(VoiceState.IDLE)
            time.sleep(1)


# ── Wake Word Loop (Picovoice) ───────────────────────────────

def _wake_word_loop() -> None:
    """Wake word detection loop using Picovoice Porcupine."""
    access_key = os.getenv("PICOVOICE_ACCESS_KEY", "")
    if not access_key:
        print("[voice_loop] PICOVOICE_ACCESS_KEY not set. Wake word disabled.")
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
            print("[voice_loop] Using 'Hey Google' as placeholder wake word.")

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

        print(f"[voice_loop] Wake word active (sensitivity={sensitivity})")

        while not _stop_event.is_set():
            if get_state() != VoiceState.IDLE:
                time.sleep(0.1)
                continue

            pcm = recorder.read()
            result = porcupine.process(pcm)

            if result >= 0:
                print("[voice_loop] Wake word detected!")
                _handle_wake_activation()

    except Exception as e:
        print(f"[voice_loop] Wake word error: {e}")
    finally:
        if recorder is not None:
            try:
                recorder.stop()
                recorder.delete()
            except Exception:
                pass
        if porcupine is not None:
            try:
                porcupine.delete()
            except Exception:
                pass


def _handle_wake_activation() -> None:
    """Handle a wake word activation."""
    hub.publish_threadsafe({
        "type": "wake_word",
        "created_at": __import__("datetime").datetime.utcnow().isoformat(),
    })

    _set_state(VoiceState.LISTENING)

    try:
        text = _capture_speech()
    except Exception as e:
        print(f"[voice_loop] STT error: {e}")
        from . import tts_manager
        tts_manager.speak("I didn't catch that.")
        _set_state(VoiceState.IDLE)
        return

    if not text.strip():
        from . import tts_manager
        tts_manager.speak("I didn't hear anything.")
        _set_state(VoiceState.IDLE)
        return

    print(f"[voice_loop] Heard: {text}")
    _process_and_respond(text)


# ── Manual Trigger ───────────────────────────────────────────

def trigger_manual() -> Dict[str, Any]:
    """Manually trigger voice capture (from mic button click)."""
    if get_state() != VoiceState.IDLE:
        return {"speak": "I'm already busy.", "actions": [], "face": "IDLE", "action_results": []}

    _set_state(VoiceState.LISTENING)

    try:
        text = _capture_speech()
    except Exception as e:
        _set_state(VoiceState.IDLE)
        return {"speak": "", "actions": [], "face": "IDLE", "action_results": [], "stt_error": str(e)}

    if not text.strip():
        _set_state(VoiceState.IDLE)
        return {"speak": "I didn't hear anything.", "actions": [], "face": "IDLE", "action_results": []}

    result = _process_and_respond(text)

    return {
        "text": text,
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
    """Start the voice loop. Uses passive listening by default, wake word if configured."""
    global _listen_thread

    if _listen_thread is not None and _listen_thread.is_alive():
        return

    _stop_event.clear()

    # Choose listening mode
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
