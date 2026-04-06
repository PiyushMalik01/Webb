from __future__ import annotations

import io
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
_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=api_key, timeout=15.0)
    return _client


def _init_pygame() -> None:
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=1024)
    except Exception as e:
        print(f"[tts] mixer init failed: {e}")


def _playback_loop() -> None:
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
    """Generate TTS and play immediately — optimized for low latency."""
    import pygame

    voice = os.getenv("OPENAI_TTS_VOICE", "fable")

    client = _get_client()

    # Use pcm format for lowest latency — no mp3 decode overhead
    # Stream directly to a buffer
    tmp_path = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()

        with client.audio.speech.with_streaming_response.create(
            model="tts-1",  # Always tts-1 for speed (tts-1-hd is 2x slower)
            voice=voice,
            input=text,
            response_format="mp3",
            speed=1.05,  # Slightly faster speech
        ) as response:
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=4096):
                    f.write(chunk)

        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            if _stop_event.is_set():
                pygame.mixer.music.stop()
                break
            pygame.time.wait(30)
    finally:
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def speak(text: str) -> None:
    if os.getenv("TTS_ENABLED", "1") != "1":
        return
    text = text.strip()
    if not text:
        return
    _ensure_thread()
    _tts_queue.put(text)


def speak_sync(text: str) -> None:
    speak(text)
    _tts_queue.join()


def is_speaking() -> bool:
    return _speaking_event.is_set()


def interrupt() -> None:
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass
    while not _tts_queue.empty():
        try:
            _tts_queue.get_nowait()
            _tts_queue.task_done()
        except queue.Empty:
            break
    _speaking_event.clear()


def _ensure_thread() -> None:
    global _playback_thread
    if _playback_thread is not None and _playback_thread.is_alive():
        return
    _stop_event.clear()
    _playback_thread = threading.Thread(target=_playback_loop, daemon=True)
    _playback_thread.start()


def shutdown() -> None:
    _stop_event.set()
    _tts_queue.put(None)
    if _playback_thread is not None:
        _playback_thread.join(timeout=3.0)
