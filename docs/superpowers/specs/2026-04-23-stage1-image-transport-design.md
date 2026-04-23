# Stage 1 — Hybrid Image Transport

## Goal

Prove the backend can push a dynamically-generated JPEG image to the ESP32 display via USB serial, while keeping all existing text commands (FACE, TEXT, NOTIFY, MODE) working. This is the transport foundation for the full dynamic display pipeline.

## Wire Protocol

Binary command byte prefix mixed with existing text protocol on the same serial line.

| First byte | Meaning | What follows |
|---|---|---|
| ASCII (0x20-0x7E) | Text command (existing) | Accumulate until `\n`, dispatch |
| `0x10` | FULL_FRAME image | 4-byte length (big-endian) + JPEG bytes |

ESP32 serial reader checks each incoming byte:
- Printable ASCII → existing text path (`FACE:HAPPY\n`, `NOTIFY:Hello\n`, etc.)
- `0x10` → binary path: read 4-byte length, then read N bytes of JPEG data

Backwards-compatible. No existing command starts with a non-printable byte.

### Image Specs

- Resolution: 320x240 pixels (landscape, matching current display orientation)
- Format: JPEG, quality 60
- Typical size: 10-15KB
- Transfer time at 115200 baud: ~1-1.5 seconds (acceptable for ambient content)
- Max buffer: 20KB (static allocation on ESP32)

## Firmware Changes (firmware.ino)

### New dependency

**TJpgDec** library (by Bodmer) — JPEG decoder designed for TFT_eSPI. Decodes in 16KB MCU blocks directly to display, no full-frame buffer needed. Install via Arduino Library Manager.

### Serial reader modification

Current: accumulates bytes into `cmdBuf` until `\n`, then dispatches.

New: check first byte of each message.
```
loop():
  if Serial.available():
    byte = Serial.peek()
    if byte == 0x10:
      Serial.read()  // consume command byte
      read 4 bytes → length (big-endian uint32)
      read `length` bytes → jpegBuf[]
      decode JPEG via TJpgDec → pushImage to TFT
      set displayMode = MODE_IMAGE
    else:
      // existing text accumulation path (unchanged)
```

### New display mode

Add `MODE_IMAGE = 3` alongside existing `MODE_FACE`, `MODE_DASHBOARD`, `MODE_NOTIFY`.

- When JPEG arrives → `displayMode = MODE_IMAGE`, display shows decoded image
- When `FACE:<mood>` arrives → `displayMode = MODE_FACE`, Tabbie eyes resume
- When `MODE:FACE` arrives → same, eyes resume

This enables the Stage 2 compositor to freely switch between avatar and image content.

### What stays untouched

- Entire Tabbie eye animation engine (blink, look, mood, eyebrows, mouth, effects)
- All text serial commands (FACE, TEXT, NOTIFY, MODE, STATUS, CLEAR, ANIM)
- Dashboard mode rendering
- Notification banner system
- Auto-mood fallback behavior

### Memory budget

| Component | RAM |
|---|---|
| Existing firmware | ~80-100KB |
| JPEG receive buffer (static) | 20KB |
| TJpgDec work area | ~3.1KB |
| Remaining (of ~320KB) | ~195KB |

Safe margin. No PSRAM needed.

## Backend Changes

### New subpackage: `backend/display/`

```
backend/display/
  __init__.py          — push_test_image() convenience
  renderer.py          — PIL image → JPEG bytes
  transport.py         — binary frame send via serial_manager
```

### `renderer.py`

Pure functions, no side effects.

- `render_test_card() -> PIL.Image` — 320x240 test pattern: color gradient background, "WEBB DISPLAY" centered text, timestamp, resolution info
- `image_to_jpeg(img: PIL.Image, quality: int = 60) -> bytes` — PIL Image → JPEG bytes
- `resize_for_display(img: PIL.Image) -> PIL.Image` — resize/crop any image to 320x240

### `transport.py`

- `send_image(jpeg_bytes: bytes) -> None` — builds binary frame: `0x10` + 4-byte big-endian length + JPEG data, writes via `serial_manager.send_raw()`
- Uses existing `get_serial_manager()` singleton
- Thread-safe via serial_manager's existing RLock

### Serial manager addition

Add `send_raw(data: bytes)` method to `SerialManager` class — writes raw bytes without newline appending. Used only by display transport.

### New route: `backend/routes/display.py`

- `POST /api/display/test` — render test card → JPEG → push to ESP32, return `{"ok": true, "size_bytes": N}`
- `POST /api/display/push` — accept image upload (multipart), resize to 320x240, push as JPEG
- `GET /api/display/status` — return `{"mode": "image"|"face"|"idle", "last_push": timestamp}`

Registered in `main.py` with prefix `/api/display`.

### New dependency

`Pillow` is already in requirements.txt (`Pillow>=10.0,<11`). No new pip dependencies needed.

## How This Enables the Full Plan

| Plan component | What Stage 1 delivers | What plugs in later |
|---|---|---|
| Wire protocol `0x10` | Binary image transport, tested | Same protocol for all future image content |
| Renderer | `image_to_jpeg()` core function | Templates (clock, Spotify, notification) use this |
| Transport | `send_image()` via serial | Stage 5 adds WiFi WebSocket as second path |
| Display mode switching | `MODE_IMAGE` ↔ `MODE_FACE` | Compositor toggles in Stage 2 |
| Text commands | Fully preserved, working | Stage 3 avatar source still uses `FACE:` |
| Serial manager | `send_raw()` for binary data | Used by all future frame pushes |

## Test Criteria

Stage 1 passes when:

1. `POST /api/display/test` generates a test card and ESP32 displays it (colors correct, text readable, fills 320x240)
2. Sending `FACE:HAPPY` after an image switches back to animated Tabbie eyes
3. Sending another test image switches back to image display
4. All existing voice commands, face changes, and notifications still work
5. Backend generates test card PNG to disk for offline verification (no ESP32 needed)

## Manual Setup Required

Before flashing updated firmware:

1. Open Arduino IDE → Sketch → Include Library → Manage Libraries
2. Search "TJpgDec" by Bodmer → Install
3. Flash updated firmware.ino to ESP32
4. Verify ESP32 connects on its COM port (same as before)

No other manual setup needed. Backend changes are pure Python additions.
