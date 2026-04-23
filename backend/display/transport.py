from __future__ import annotations

import struct
import time

from ..serial_manager import get_serial_manager

CMD_FULL_FRAME = 0x10
MAX_JPEG_SIZE = 20_000
CHUNK_SIZE = 1024
CHUNK_DELAY = 0.005


def send_image(jpeg_bytes: bytes) -> None:
    """Send a JPEG image to ESP32 via binary serial protocol.

    Wire format: [0x10] [4-byte big-endian length] [JPEG data]
    Sends in 1KB chunks with 5ms inter-chunk delay to prevent
    ESP32 serial RX buffer overflow.
    """
    if len(jpeg_bytes) > MAX_JPEG_SIZE:
        raise ValueError(f"JPEG too large: {len(jpeg_bytes)} > {MAX_JPEG_SIZE}")

    header = struct.pack(">BI", CMD_FULL_FRAME, len(jpeg_bytes))
    sm = get_serial_manager()

    sm.send_raw(header)
    for offset in range(0, len(jpeg_bytes), CHUNK_SIZE):
        chunk = jpeg_bytes[offset:offset + CHUNK_SIZE]
        sm.send_raw(chunk)
        if offset + CHUNK_SIZE < len(jpeg_bytes):
            time.sleep(CHUNK_DELAY)
