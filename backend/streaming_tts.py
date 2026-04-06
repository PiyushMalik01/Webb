from __future__ import annotations

import os
import queue
import tempfile
import threading
from typing import Callable, Optional

from openai import OpenAI


_tts_queue: queue.Queue[Optional[str]] = queue.Queue()
_playback_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_speaking = threading.Event()
_client: Optional[OpenAI] = None

# Callbacks for mute-on-speak
_on_speak_start: Optional[Callable] = None
_on_speak_end: Optional[Callable] = None


def set_callbacks(on_start: Callable, on_end: Callable) -> None:
    """Set callbacks for mute/unmute coordination with audio engine."""
    global _on_speak_start, _on_speak_end
    _on_speak_start = on_start
    _on_speak_end = on_end


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


def _play_audio_file(path: str) -> None:
    """Play an audio file and block until done."""
    import pygame

    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            if _stop_event.is_set():
                pygame.mixer.music.stop()
                break
            pygame.time.wait(20)
    finally:
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass


def _generate_audio(text: str) -> Optional[str]:
    """Generate TTS audio and return temp file path. Returns None on failure."""
    voice = os.getenv("OPENAI_TTS_VOICE", "fable")
    speed = float(os.getenv("TTS_SPEED", "1.05"))

    client = _get_client()

    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
            speed=speed,
        ) as response:
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=4096):
                    f.write(chunk)
                    if _stop_event.is_set():
                        break
        return tmp_path
    except Exception as e:
        print(f"[tts] generation error: {e}")
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return None


def _playback_loop() -> None:
    """Background thread — processes TTS queue."""
    _init_pygame()

    while not _stop_event.is_set():
        try:
            text = _tts_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        if text is None:
            break

        try:
            _speaking.set()
            if _on_speak_start:
                _on_speak_start()

            path = _generate_audio(text)
            if path and not _stop_event.is_set():
                _play_audio_file(path)
                try:
                    os.unlink(path)
                except Exception:
                    pass

        except Exception as e:
            print(f"[tts] error: {e}")
        finally:
            _speaking.clear()
            if _on_speak_end:
                _on_speak_end()
            _tts_queue.task_done()


def speak(text: str) -> None:
    """Queue text for TTS. Non-blocking."""
    if os.getenv("TTS_ENABLED", "1") != "1":
        return
    text = text.strip()
    if not text:
        return
    _ensure_thread()
    _tts_queue.put(text)


def speak_sync(text: str) -> None:
    """Speak and block until done."""
    speak(text)
    _tts_queue.join()


def speak_streamed(sentences: list[str]) -> None:
    """Queue multiple sentences for sequential playback."""
    for s in sentences:
        s = s.strip()
        if s:
            speak(s)


def is_speaking() -> bool:
    return _speaking.is_set()


def interrupt() -> None:
    """Stop current playback and clear queue."""
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

    _speaking.clear()
    if _on_speak_end:
        _on_speak_end()


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
