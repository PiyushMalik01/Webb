from __future__ import annotations

import struct

from ..serial_manager import get_serial_manager

CMD_FULL_FRAME = 0x10
MAX_JPEG_SIZE = 20_000


def send_image(jpeg_bytes: bytes) -> None:
    """Send a JPEG image to ESP32 via binary serial protocol.

    Wire format: [0x10] [4-byte big-endian length] [JPEG data]
    """
    if len(jpeg_bytes) > MAX_JPEG_SIZE:
        raise ValueError(f"JPEG too large: {len(jpeg_bytes)} > {MAX_JPEG_SIZE}")

    header = struct.pack(">BI", CMD_FULL_FRAME, len(jpeg_bytes))
    sm = get_serial_manager()
    sm.send_raw(header + jpeg_bytes)
