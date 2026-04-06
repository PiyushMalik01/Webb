from __future__ import annotations

import os
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

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
_wake_thread: Optional[threading.Thread] = None
_on_state_change: Optional[Callable[[VoiceState], None]] = None


def get_state() -> VoiceState:
    with _state_lock:
        return _state


def _set_state(new_state: VoiceState) -> None:
    global _state
    with _state_lock:
        _state = new_state

    # Publish state change
    hub.publish_threadsafe({
        "type": "voice_state",
        "state": new_state.value,
        "created_at": __import__("datetime").datetime.utcnow().isoformat(),
    })

    # Update face on ESP32
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


def _process_and_respond(text: str) -> None:
    """Process speech through AI brain, execute actions, speak response."""
    from . import ai_manager
    from . import tts_manager

    # AI processing
    _set_state(VoiceState.PROCESSING)
    result = ai_manager.process_message(text)

    speak_text = result.get("speak", "")
    face = result.get("face", "HAPPY")

    # Execute any actions
    if result.get("action_results"):
        _set_state(VoiceState.EXECUTING)
        time.sleep(0.5)  # Brief pause for action execution visibility

    # Set face from AI response
    try:
        from .serial_manager import get_serial_manager
        get_serial_manager().send_face(face)
    except Exception:
        pass

    # Speak response
    if speak_text:
        _set_state(VoiceState.SPEAKING)
        tts_manager.speak_sync(speak_text)

    _set_state(VoiceState.IDLE)


def _wake_word_loop() -> None:
    """Main wake word detection loop using Picovoice Porcupine."""
    access_key = os.getenv("PICOVOICE_ACCESS_KEY", "")
    if not access_key:
        print("[voice_loop] PICOVOICE_ACCESS_KEY not set. Wake word disabled. Use mic button.")
        return

    try:
        import pvporcupine
        import pvrecorder
    except ImportError:
        print("[voice_loop] pvporcupine/pvrecorder not installed. Wake word disabled.")
        return

    porcupine = None
    recorder = None

    try:
        # Try custom "Hey Webb" keyword, fall back to built-in "Hey Google" for testing
        keyword_paths = None
        keywords = None

        custom_keyword = os.getenv("WAKE_WORD_PATH")
        if custom_keyword and os.path.exists(custom_keyword):
            keyword_paths = [custom_keyword]
        else:
            # Use a built-in keyword for testing
            keywords = ["hey google"]
            print("[voice_loop] No custom wake word file. Using 'Hey Google' as placeholder.")
            print("[voice_loop] Get a custom 'Hey Webb' keyword at console.picovoice.ai")

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

        print(f"[voice_loop] Wake word detection active (sensitivity={sensitivity})")

        while not _stop_event.is_set():
            if get_state() != VoiceState.IDLE:
                time.sleep(0.1)
                continue

            pcm = recorder.read()
            result = porcupine.process(pcm)

            if result >= 0:
                print("[voice_loop] Wake word detected!")
                _handle_activation()

    except Exception as e:
        print(f"[voice_loop] Error: {e}")
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


def _handle_activation() -> None:
    """Handle a wake word detection or manual activation."""
    # Publish wake event
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


def trigger_manual() -> Dict[str, Any]:
    """Manually trigger voice capture (from mic button click). Returns AI result."""
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

    # Process through AI
    _set_state(VoiceState.PROCESSING)
    from . import ai_manager
    result = ai_manager.process_message(text)

    # Execute actions
    if result.get("action_results"):
        _set_state(VoiceState.EXECUTING)
        time.sleep(0.3)

    # Speak response
    speak_text = result.get("speak", "")
    if speak_text:
        _set_state(VoiceState.SPEAKING)
        from . import tts_manager
        tts_manager.speak(speak_text)  # Non-blocking for manual trigger

    _set_state(VoiceState.IDLE)

    return {
        "text": text,
        "speak": speak_text,
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


def start() -> None:
    """Start the voice loop (wake word detection thread)."""
    global _wake_thread

    if os.getenv("WAKE_WORD_ENABLED", "0") != "1":
        print("[voice_loop] Wake word disabled. Set WAKE_WORD_ENABLED=1 to enable.")
        return

    if _wake_thread is not None and _wake_thread.is_alive():
        return

    _stop_event.clear()
    _wake_thread = threading.Thread(target=_wake_word_loop, daemon=True)
    _wake_thread.start()


def stop() -> None:
    """Stop the voice loop."""
    _stop_event.set()
    if _wake_thread is not None:
        _wake_thread.join(timeout=3.0)
