from __future__ import annotations

import os
import socket
import struct

CMD_FULL_FRAME = 0x10
MAX_JPEG_SIZE = 40_000
TCP_PORT = 3456
TCP_TIMEOUT = 5.0


def _get_esp32_host() -> str | None:
    host = os.getenv("ESP32_HOST")
    if host:
        return host
    try:
        return socket.gethostbyname("webb.local")
    except socket.gaierror:
        return None


def send_image(jpeg_bytes: bytes) -> None:
    """Send a JPEG image to ESP32 via WiFi TCP (preferred) or serial fallback.

    Wire format: [0x10] [4-byte big-endian length] [JPEG data]
    """
    if len(jpeg_bytes) > MAX_JPEG_SIZE:
        raise ValueError(f"JPEG too large: {len(jpeg_bytes)} > {MAX_JPEG_SIZE}")

    header = struct.pack(">BI", CMD_FULL_FRAME, len(jpeg_bytes))

    host = _get_esp32_host()
    if host:
        try:
            _send_tcp(host, header + jpeg_bytes)
            return
        except Exception as e:
            print(f"[display] WiFi failed ({host}:{TCP_PORT}): {e}, trying serial...")

    _send_serial(header, jpeg_bytes)


def send_command(cmd: str) -> None:
    """Send a text command (FACE:HAPPY, NOTIFY:Hello, etc.) via WiFi TCP.
    Raises if WiFi is unavailable — caller handles serial fallback."""
    host = _get_esp32_host()
    if not host:
        raise RuntimeError("ESP32 WiFi host not found")
    _send_tcp(host, (cmd + "\n").encode("utf-8"))


def _send_tcp(host: str, data: bytes) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(TCP_TIMEOUT)
        s.connect((host, TCP_PORT))
        s.sendall(data)
        response = s.recv(64).decode("utf-8", errors="ignore").strip()
        if not response.startswith("OK"):
            raise RuntimeError(f"ESP32: {response}")


def _send_serial(header: bytes, jpeg_bytes: bytes) -> None:
    import time
    from ..serial_manager import get_serial_manager

    sm = get_serial_manager()
    sm.send_raw(header)
    for offset in range(0, len(jpeg_bytes), 512):
        chunk = jpeg_bytes[offset:offset + 512]
        sm.send_raw(chunk)
        if offset + 512 < len(jpeg_bytes):
            time.sleep(0.01)
