from __future__ import annotations

import os
import queue
import tempfile
import threading
from typing import Optional

from openai import OpenAI


_tts_queue: queue.Queue[Optional[str]] = queue.Queue()
_playback_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_speaking_event = threading.Event()


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key, timeout=30.0)


def _init_pygame() -> None:
    """Initialize pygame mixer if not already done."""
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=2048)
    except Exception as e:
        print(f"[tts] pygame mixer init failed: {e}")


def _playback_loop() -> None:
    """Background thread that processes the TTS queue."""
    _init_pygame()

    while not _stop_event.is_set():
        try:
            text = _tts_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if text is None:
            break

        try:
            _speaking_event.set()
            _generate_and_play(text)
        except Exception as e:
            print(f"[tts] error: {e}")
        finally:
            _speaking_event.clear()
            _tts_queue.task_done()


def _generate_and_play(text: str) -> None:
    """Generate TTS audio via OpenAI and play it."""
    import pygame

    voice = os.getenv("OPENAI_TTS_VOICE", "fable")
    model = os.getenv("OPENAI_TTS_MODEL", "tts-1")

    client = _get_client()

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name

    with client.audio.speech.with_streaming_response.create(
        model=model,
        voice=voice,
        input=text,
        response_format="mp3",
    ) as response:
        with open(tmp_path, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)

    try:
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            if _stop_event.is_set():
                pygame.mixer.music.stop()
                break
            pygame.time.wait(50)
    finally:
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def speak(text: str) -> None:
    """Queue text for TTS playback. Non-blocking."""
    if os.getenv("TTS_ENABLED", "1") != "1":
        print(f"[tts] (disabled) Would say: {text}")
        return

    text = text.strip()
    if not text:
        return

    _ensure_thread()
    _tts_queue.put(text)


def speak_sync(text: str) -> None:
    """Speak text and block until done."""
    speak(text)
    _tts_queue.join()


def is_speaking() -> bool:
    """Return True if TTS is currently playing audio."""
    return _speaking_event.is_set()


def interrupt() -> None:
    """Stop current playback and clear the queue."""
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass

    # Drain the queue
    while not _tts_queue.empty():
        try:
            _tts_queue.get_nowait()
            _tts_queue.task_done()
        except queue.Empty:
            break

    _speaking_event.clear()


def _ensure_thread() -> None:
    """Start the playback thread if not running."""
    global _playback_thread
    if _playback_thread is not None and _playback_thread.is_alive():
        return
    _stop_event.clear()
    _playback_thread = threading.Thread(target=_playback_loop, daemon=True)
    _playback_thread.start()


def shutdown() -> None:
    """Stop the playback thread cleanly."""
    _stop_event.set()
    _tts_queue.put(None)
    if _playback_thread is not None:
        _playback_thread.join(timeout=3.0)
