from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

import serial
from serial.tools import list_ports


FACES = {"IDLE", "HAPPY", "FOCUS", "SLEEPY", "REMINDER", "LISTENING", "SURPRISED", "THINKING", "SPEAKING"}


@dataclass(frozen=True)
class SerialStatus:
    connected: bool
    port: Optional[str]
    baud: int
    last_face: Optional[str]
    last_error: Optional[str]


def _port_score(p: list_ports.ListPortInfo) -> int:
    desc = (p.description or "").lower()
    manuf = (p.manufacturer or "").lower()
    hwid = (p.hwid or "").lower()

    score = 0
    if "cp210" in desc or "cp210" in manuf or "cp210" in hwid:
        score += 100
    if "ch340" in desc or "ch340" in manuf or "ch340" in hwid:
        score += 80
    if "usb serial" in desc or "usb-serial" in desc or "usb" in hwid:
        score += 25
    if "esp" in desc or "esp" in manuf:
        score += 50
    return score


def _autodetect_port() -> Optional[str]:
    ports = list(list_ports.comports())
    if not ports:
        return None
    ports.sort(key=_port_score, reverse=True)
    if _port_score(ports[0]) <= 0:
        return ports[0].device  # best-effort
    return ports[0].device


class SerialManager:
    def __init__(self, port: Optional[str] = None, baud: int = 115200) -> None:
        self._preferred_port = port
        self._baud = baud
        self._lock = threading.RLock()
        self._ser: Optional[serial.Serial] = None
        self._connected_port: Optional[str] = None
        self._last_face: Optional[str] = None
        self._last_error: Optional[str] = None

        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def baud(self) -> int:
        return self._baud

    def set_preferred_port(self, port: Optional[str]) -> None:
        with self._lock:
            self._preferred_port = port
            self._disconnect_locked()

    def get_status(self) -> SerialStatus:
        with self._lock:
            return SerialStatus(
                connected=self._ser is not None and self._ser.is_open,
                port=self._connected_port,
                baud=self._baud,
                last_face=self._last_face,
                last_error=self._last_error,
            )

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            self._disconnect_locked()

    def send_command(self, cmd: str) -> None:
        """Send an arbitrary rich-protocol command (e.g. ``FACE:HAPPY``,
        ``TEXT:1:Hello``) over serial.  The command is transmitted as-is
        with a trailing newline."""
        with self._lock:
            if self._ser is None or not self._ser.is_open:
                raise RuntimeError("Serial not connected")
            self._ser.write((cmd + "\n").encode("utf-8"))
            self._ser.flush()

    def send_face(self, face: str, timeout_s: float = 1.5) -> None:
        face = face.strip().upper()
        if face not in FACES:
            raise ValueError(f"Unknown face: {face}")

        with self._lock:
            if self._ser is None or not self._ser.is_open:
                raise RuntimeError("Serial not connected")

            try:
                self._ser.reset_input_buffer()
            except Exception:
                pass

            protocol = os.getenv("DISPLAY_PROTOCOL", "").lower()
            if protocol == "rich":
                self._ser.write((f"FACE:{face}\n").encode("utf-8"))
            else:
                self._ser.write((face + "\n").encode("utf-8"))
            self._ser.flush()

            self._ser.timeout = timeout_s
            line = self._ser.readline().decode("utf-8", errors="ignore").strip()
            # Many sketches don't echo an OK line. Treat missing or malformed
            # replies as best-effort instead of hard errors so the HTTP API
            # stays responsive.
            if not line:
                self._last_face = face
                self._last_error = None
                return

            if line.startswith("OK:"):
                ok_face = line.split(":", 1)[1].strip().upper()
                self._last_face = ok_face or face
                self._last_error = None
                return

            # Non-empty but unexpected line: record it for status but don't fail the call.
            self._last_face = face
            self._last_error = f"Unexpected reply: {line!r}"

    def send_text(self, line: int, content: str) -> None:
        """Send a ``TEXT:<line>:<content>`` command to the display."""
        self.send_command(f"TEXT:{line}:{content}")

    def send_notify(self, msg: str) -> None:
        """Send a ``NOTIFY:<msg>`` command to the display."""
        self.send_command(f"NOTIFY:{msg}")

    def send_mode(self, mode: str) -> None:
        """Send a ``MODE:<mode>`` command to the display."""
        self.send_command(f"MODE:{mode}")

    def send_anim(self, name: str) -> None:
        """Send an ``ANIM:<name>`` command to the display."""
        self.send_command(f"ANIM:{name}")

    def _disconnect_locked(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None
        self._connected_port = None

    def _connect_locked(self, port: str) -> bool:
        try:
            ser = serial.Serial(port=port, baudrate=self._baud, timeout=1.0)
        except Exception as e:
            self._last_error = str(e)
            return False

        self._ser = ser
        self._connected_port = port
        self._last_error = None
        return True

    def _pick_port_locked(self) -> Optional[str]:
        if self._preferred_port:
            return self._preferred_port
        env_port = os.getenv("SERIAL_PORT")
        if env_port:
            return env_port
        return _autodetect_port()

    def _run(self) -> None:
        backoff_s = 0.5
        while not self._stop.is_set():
            with self._lock:
                connected = self._ser is not None and self._ser.is_open
                if connected:
                    backoff_s = 0.5
                else:
                    port = self._pick_port_locked()
                    if port:
                        ok = self._connect_locked(port)
                        if ok:
                            backoff_s = 0.5

            time.sleep(backoff_s)
            backoff_s = min(backoff_s * 1.5, 5.0)


_serial_manager_singleton: Optional[SerialManager] = None
_serial_manager_lock = threading.Lock()


def get_serial_manager() -> SerialManager:
    global _serial_manager_singleton
    with _serial_manager_lock:
        if _serial_manager_singleton is None:
            baud = int(os.getenv("SERIAL_BAUD", "115200"))
            port = os.getenv("SERIAL_PORT")
            _serial_manager_singleton = SerialManager(port=port, baud=baud)
        return _serial_manager_singleton

