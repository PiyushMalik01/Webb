from __future__ import annotations

import collections
import os
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import torch

# ── Silero VAD ───────────────────────────────────────────────

_vad_model = None
_vad_lock = threading.Lock()


def _get_vad():
    global _vad_model
    with _vad_lock:
        if _vad_model is None:
            from silero_vad import load_silero_vad
            _vad_model = load_silero_vad()
        return _vad_model


# ── Ring Buffer ──────────────────────────────────────────────

class RingBuffer:
    """Thread-safe ring buffer for audio samples."""

    def __init__(self, max_seconds: float = 30.0, sample_rate: int = 16000):
        self._buf = np.zeros(int(max_seconds * sample_rate), dtype=np.int16)
        self._write_pos = 0
        self._lock = threading.Lock()
        self._sr = sample_rate

    def write(self, data: np.ndarray) -> None:
        with self._lock:
            n = len(data)
            end = self._write_pos + n
            if end <= len(self._buf):
                self._buf[self._write_pos:end] = data
            else:
                first = len(self._buf) - self._write_pos
                self._buf[self._write_pos:] = data[:first]
                self._buf[:n - first] = data[first:]
            self._write_pos = end % len(self._buf)

    def get_last(self, seconds: float) -> np.ndarray:
        with self._lock:
            n = int(seconds * self._sr)
            if n > len(self._buf):
                n = len(self._buf)
            start = (self._write_pos - n) % len(self._buf)
            if start < self._write_pos:
                return self._buf[start:self._write_pos].copy()
            else:
                return np.concatenate([self._buf[start:], self._buf[:self._write_pos]]).copy()


# ── Audio Engine ─────────────────────────────────────────────

class AudioEngine:
    """
    Continuous audio capture with Silero VAD.
    Detects speech start/end and delivers complete utterances.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        vad_threshold: float = 0.5,
        silence_ms: int = 800,
        min_speech_ms: int = 300,
        on_speech: Optional[Callable[[np.ndarray], None]] = None,
    ):
        self._sr = sample_rate
        self._vad_threshold = vad_threshold
        self._silence_samples = int(silence_ms * sample_rate / 1000)
        self._min_speech_samples = int(min_speech_ms * sample_rate / 1000)
        self._on_speech = on_speech

        self._ring = RingBuffer(max_seconds=30.0, sample_rate=sample_rate)
        self._stream: Optional[sd.InputStream] = None
        self._running = False
        self._muted = False
        self._mute_lock = threading.Lock()

        # VAD state
        self._in_speech = False
        self._speech_buf: list[np.ndarray] = []
        self._silence_counter = 0
        self._speech_counter = 0

        # Chunk size for VAD (512 samples = 32ms at 16kHz)
        self._chunk_size = 512

        # Accumulation buffer for incoming audio
        self._acc_buf = np.array([], dtype=np.int16)
        self._acc_lock = threading.Lock()

        # Processing thread
        self._proc_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def muted(self) -> bool:
        with self._mute_lock:
            return self._muted

    def mute(self) -> None:
        with self._mute_lock:
            self._muted = True
        # Reset speech state when muting
        self._in_speech = False
        self._speech_buf.clear()
        self._silence_counter = 0
        self._speech_counter = 0

    def unmute(self) -> None:
        with self._mute_lock:
            self._muted = False

    def start(self) -> None:
        if self._running:
            return

        self._stop_event.clear()
        self._running = True

        # Start audio stream
        self._stream = sd.InputStream(
            samplerate=self._sr,
            channels=1,
            dtype='int16',
            blocksize=self._chunk_size,
            callback=self._audio_callback,
        )
        self._stream.start()

        # Start processing thread
        self._proc_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._proc_thread.start()

        print(f"[audio] Engine started (sr={self._sr}, vad_threshold={self._vad_threshold})")

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if self._proc_thread is not None:
            self._proc_thread.join(timeout=3.0)

    def _audio_callback(self, indata, frames, time_info, status):
        """sounddevice callback — runs in audio thread."""
        if status:
            pass  # Ignore xruns silently

        samples = indata[:, 0].copy()  # mono
        self._ring.write(samples)

        # Accumulate for processing thread
        with self._acc_lock:
            self._acc_buf = np.concatenate([self._acc_buf, samples])

    def _process_loop(self):
        """Processing thread — runs VAD on accumulated audio."""
        vad = _get_vad()

        while not self._stop_event.is_set():
            # Get accumulated audio
            with self._acc_lock:
                if len(self._acc_buf) < self._chunk_size:
                    pass  # Not enough data
                else:
                    chunk = self._acc_buf[:self._chunk_size].copy()
                    self._acc_buf = self._acc_buf[self._chunk_size:]

                    if not self.muted:
                        self._process_chunk(vad, chunk)
                    continue  # Process next chunk immediately if available

            time.sleep(0.01)  # Only sleep when no data available

    def _process_chunk(self, vad, chunk: np.ndarray):
        """Process a single audio chunk through VAD."""
        # Convert to float32 for Silero
        audio_float = chunk.astype(np.float32) / 32768.0
        tensor = torch.from_numpy(audio_float)

        try:
            prob = vad(tensor, self._sr).item()
        except Exception as e:
            print(f"[audio] VAD error: {e}")
            return

        if prob >= self._vad_threshold:
            # Speech detected
            self._speech_counter += len(chunk)
            self._silence_counter = 0

            if not self._in_speech:
                self._in_speech = True
                self._speech_buf.clear()
                # Include a small look-back for the start of speech
                lookback = self._ring.get_last(0.3)
                self._speech_buf.append(lookback)

            self._speech_buf.append(chunk)

        else:
            # Silence
            if self._in_speech:
                self._silence_counter += len(chunk)
                self._speech_buf.append(chunk)  # Keep silence in buffer (natural pause)

                if self._silence_counter >= self._silence_samples:
                    # Speech ended
                    self._in_speech = False
                    total_speech = self._speech_counter

                    if total_speech >= self._min_speech_samples:
                        # Deliver complete utterance
                        audio = np.concatenate(self._speech_buf)
                        duration_s = len(audio) / self._sr
                        print(f"[audio] Speech captured: {duration_s:.1f}s ({len(audio)} samples)")
                        self._speech_buf.clear()
                        self._speech_counter = 0
                        self._silence_counter = 0

                        if self._on_speech is not None:
                            self._on_speech(audio)
                        else:
                            print("[audio] WARNING: no on_speech callback set!")
                    else:
                        # Too short — discard (click, cough, etc.)
                        self._speech_buf.clear()
                        self._speech_counter = 0
                        self._silence_counter = 0

    def set_silence_duration(self, ms: int) -> None:
        """Change silence duration threshold (e.g., shorter for follow-up mode)."""
        self._silence_samples = int(ms * self._sr / 1000)


# ── Singleton ────────────────────────────────────────────────

_engine: Optional[AudioEngine] = None


def get_audio_engine() -> AudioEngine:
    global _engine
    if _engine is None:
        _engine = AudioEngine(
            vad_threshold=float(os.getenv("VAD_THRESHOLD", "0.5")),
            silence_ms=int(os.getenv("VAD_SILENCE_MS", "800")),
        )
    return _engine
