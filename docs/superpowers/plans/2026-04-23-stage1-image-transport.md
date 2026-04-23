# Stage 1 — Image Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend can push a dynamically-generated JPEG image to the ESP32 display via USB serial, while all existing text commands continue working.

**Architecture:** Add a binary image command (`0x10` prefix) to the existing serial protocol. ESP32 firmware receives JPEG bytes, decodes them with TJpgDec, and draws directly to the TFT. Backend gets a new `display/` subpackage with a PIL renderer and serial transport. A test API endpoint proves the full round trip.

**Tech Stack:** Python (PIL/Pillow, struct), Arduino C++ (TJpgDec + TFT_eSPI), FastAPI

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `backend/serial_manager.py` | Add `send_raw()` method for binary data |
| Create | `backend/display/__init__.py` | Package init, `push_test_image()` convenience |
| Create | `backend/display/renderer.py` | PIL image generation + JPEG conversion |
| Create | `backend/display/transport.py` | Binary frame protocol + serial send |
| Create | `backend/routes/display.py` | API endpoints for display testing |
| Modify | `backend/main.py` | Register display router |
| Modify | `firmware/firmware.ino` | Binary serial reader + TJpgDec JPEG decode |

---

### Task 1: Add `send_raw()` to SerialManager

**Files:**
- Modify: `backend/serial_manager.py:90-98` (after `send_command`, before `send_face`)

- [ ] **Step 1: Add `send_raw` method**

Add this method right after `send_command` (after line 98) in `backend/serial_manager.py`:

```python
def send_raw(self, data: bytes) -> None:
    """Write raw bytes to serial without newline. Used for binary protocols."""
    with self._lock:
        if self._ser is None or not self._ser.is_open:
            raise RuntimeError("Serial not connected")
        self._ser.write(data)
        self._ser.flush()
```

- [ ] **Step 2: Verify backend still starts**

Run: `python -c "from backend.serial_manager import SerialManager; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/serial_manager.py
git commit -m "feat(serial): add send_raw() for binary data transport"
```

---

### Task 2: Create `backend/display/renderer.py`

**Files:**
- Create: `backend/display/__init__.py`
- Create: `backend/display/renderer.py`

- [ ] **Step 1: Create the display package**

Create `backend/display/__init__.py`:

```python
from __future__ import annotations
```

- [ ] **Step 2: Create `renderer.py`**

Create `backend/display/renderer.py`:

```python
from __future__ import annotations

import io
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

DISPLAY_W = 320
DISPLAY_H = 240


def render_test_card() -> Image.Image:
    """Generate a 320x240 test card with gradient, text, and timestamp."""
    img = Image.new("RGB", (DISPLAY_W, DISPLAY_H))
    draw = ImageDraw.Draw(img)

    for y in range(DISPLAY_H):
        r = int(20 + (y / DISPLAY_H) * 40)
        g = int(10 + (y / DISPLAY_H) * 30)
        b = int(60 + (y / DISPLAY_H) * 120)
        draw.line([(0, y), (DISPLAY_W, y)], fill=(r, g, b))

    try:
        font_large = ImageFont.truetype("arial", 28)
        font_small = ImageFont.truetype("arial", 16)
    except OSError:
        font_large = ImageFont.load_default()
        font_small = font_large

    draw.text(
        (DISPLAY_W // 2, 80),
        "WEBB DISPLAY",
        fill=(255, 255, 255),
        font=font_large,
        anchor="mm",
    )

    draw.text(
        (DISPLAY_W // 2, 120),
        f"{DISPLAY_W}x{DISPLAY_H} JPEG Transport",
        fill=(180, 180, 180),
        font=font_small,
        anchor="mm",
    )

    timestamp = datetime.now().strftime("%H:%M:%S")
    draw.text(
        (DISPLAY_W // 2, 160),
        timestamp,
        fill=(100, 200, 255),
        font=font_small,
        anchor="mm",
    )

    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]):
        x = 30 + i * 45
        draw.rectangle([x, 200, x + 35, 225], fill=color)

    return img


def image_to_jpeg(img: Image.Image, quality: int = 60) -> bytes:
    """Convert a PIL Image to JPEG bytes."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def resize_for_display(img: Image.Image) -> Image.Image:
    """Resize and crop any image to 320x240, maintaining aspect ratio."""
    target_ratio = DISPLAY_W / DISPLAY_H
    src_ratio = img.width / img.height

    if src_ratio > target_ratio:
        new_h = img.height
        new_w = int(new_h * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, new_h))
    elif src_ratio < target_ratio:
        new_w = img.width
        new_h = int(new_w / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, new_w, top + new_h))

    return img.resize((DISPLAY_W, DISPLAY_H), Image.LANCZOS)
```

- [ ] **Step 3: Verify renderer works offline**

Run:
```bash
python -c "
from backend.display.renderer import render_test_card, image_to_jpeg
img = render_test_card()
img.save('test_card.png')
jpeg = image_to_jpeg(img)
print(f'Test card: {img.size}, JPEG: {len(jpeg)} bytes')
"
```
Expected: `Test card: (320, 240), JPEG: NNNNN bytes` (should be 8000-18000 bytes) and a `test_card.png` file you can open to visually verify.

- [ ] **Step 4: Commit**

```bash
git add backend/display/__init__.py backend/display/renderer.py
git commit -m "feat(display): add renderer with test card and JPEG conversion"
```

---

### Task 3: Create `backend/display/transport.py`

**Files:**
- Create: `backend/display/transport.py`

- [ ] **Step 1: Create transport module**

Create `backend/display/transport.py`:

```python
from __future__ import annotations

import struct
import time

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
```

- [ ] **Step 2: Add convenience function to `__init__.py`**

Update `backend/display/__init__.py`:

```python
from __future__ import annotations

from .renderer import render_test_card, image_to_jpeg
from .transport import send_image


def push_test_image() -> int:
    """Render a test card, convert to JPEG, push to ESP32. Returns JPEG size."""
    img = render_test_card()
    jpeg = image_to_jpeg(img)
    send_image(jpeg)
    return len(jpeg)
```

- [ ] **Step 3: Verify import chain**

Run: `python -c "from backend.display import push_test_image; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/display/transport.py backend/display/__init__.py
git commit -m "feat(display): add binary serial transport and push_test_image"
```

---

### Task 4: Create API route `backend/routes/display.py`

**Files:**
- Create: `backend/routes/display.py`
- Modify: `backend/main.py:14,84` (add import and router registration)

- [ ] **Step 1: Create the display route**

Create `backend/routes/display.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, UploadFile, File

from ..display import push_test_image
from ..display.renderer import image_to_jpeg, resize_for_display
from ..display.transport import send_image

router = APIRouter()


@router.post("/test")
def display_test() -> dict:
    """Render a test card and push to ESP32."""
    try:
        size = push_test_image()
        return {"ok": True, "size_bytes": size}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/push")
async def display_push(file: UploadFile = File(...)) -> dict:
    """Accept an image upload, resize to 320x240, push as JPEG."""
    try:
        from PIL import Image
        import io

        data = await file.read()
        img = Image.open(io.BytesIO(data))
        img = resize_for_display(img)
        jpeg = image_to_jpeg(img)
        send_image(jpeg)
        return {"ok": True, "size_bytes": len(jpeg)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

- [ ] **Step 2: Register the router in main.py**

In `backend/main.py`, add the import after line 25 (after `from .routes.system import ...`):

```python
from .routes.display import router as display_router
```

Add the router registration after line 84 (after `app.include_router(system_router, ...)`):

```python
    app.include_router(display_router, prefix="/api/display", tags=["display"])
```

- [ ] **Step 3: Verify server starts**

Run: `python -m uvicorn backend.main:app --port 8000`
Check: `http://127.0.0.1:8000/docs` should show the new `/api/display/test` and `/api/display/push` endpoints.

- [ ] **Step 4: Test the test endpoint (without ESP32)**

Run:
```bash
curl -X POST http://127.0.0.1:8000/api/display/test
```
Expected: `{"ok": false, "error": "Serial not connected"}` (correct — no ESP32 plugged in, but proves the route and renderer work)

- [ ] **Step 5: Commit**

```bash
git add backend/routes/display.py backend/main.py
git commit -m "feat(display): add /api/display/test and /push endpoints"
```

---

### Task 5: Update ESP32 firmware with JPEG receive

**Files:**
- Modify: `firmware/firmware.ino`

This is the firmware side. The user must install TJpgDec via Arduino Library Manager and flash the updated firmware manually.

- [ ] **Step 1: Add TJpgDec include and JPEG buffer**

At the top of `firmware/firmware.ino`, after line 23 (`#include <TFT_eSPI.h>`), add:

```cpp
#include <TJpg_Decoder.h>
```

After line 38 (`int displayMode = MODE_FACE;`), add the image mode constant and JPEG buffer:

```cpp
#define MODE_IMAGE     3

// ── JPEG receive buffer ────────────────────────────────────
#define JPEG_BUF_SIZE 20000
uint8_t jpegBuf[JPEG_BUF_SIZE];
```

- [ ] **Step 2: Add TJpgDec callback and decode function**

Before the `processSerial()` function (before line 589), add:

```cpp
// ── JPEG decode callback ───────────────────────────────────

bool tjpg_output(int16_t x, int16_t y, uint16_t w, uint16_t h, uint16_t *bitmap) {
  tft.pushImage(x, y, w, h, bitmap);
  return true;  // continue decoding
}

void displayJpeg(uint8_t *data, uint32_t len) {
  tft.fillScreen(TFT_BLACK);
  TJpgDec.setJpgScale(1);
  TJpgDec.setCallback(tjpg_output);
  TJpgDec.drawJpg(0, 0, data, len);
  displayMode = MODE_IMAGE;
  webbControlled = true;
  lastSerialCmd = millis();
}
```

- [ ] **Step 3: Modify `processSerial()` to handle binary commands**

Replace the `processSerial()` function (lines 589-602) with:

```cpp
void processSerial() {
  while (Serial.available()) {
    uint8_t peek = Serial.peek();

    // Binary command: 0x10 = FULL_FRAME JPEG
    if (peek == 0x10) {
      Serial.read();  // consume command byte

      // Read 4-byte big-endian length
      uint8_t lenBuf[4];
      unsigned long t0 = millis();
      int got = 0;
      while (got < 4 && (millis() - t0) < 2000) {
        if (Serial.available()) {
          lenBuf[got++] = Serial.read();
        }
      }
      if (got < 4) {
        Serial.println("ERR:IMG:TIMEOUT_LEN");
        return;
      }

      uint32_t jpegLen = ((uint32_t)lenBuf[0] << 24) |
                         ((uint32_t)lenBuf[1] << 16) |
                         ((uint32_t)lenBuf[2] << 8)  |
                         ((uint32_t)lenBuf[3]);

      if (jpegLen > JPEG_BUF_SIZE) {
        Serial.printf("ERR:IMG:TOO_BIG:%u\n", jpegLen);
        // Drain the incoming bytes we can't store
        while (jpegLen > 0 && (millis() - t0) < 10000) {
          if (Serial.available()) { Serial.read(); jpegLen--; }
        }
        return;
      }

      // Read JPEG data
      uint32_t received = 0;
      t0 = millis();
      while (received < jpegLen && (millis() - t0) < 5000) {
        if (Serial.available()) {
          jpegBuf[received++] = Serial.read();
        }
      }

      if (received == jpegLen) {
        displayJpeg(jpegBuf, jpegLen);
        Serial.printf("OK:IMG:%u\n", jpegLen);
      } else {
        Serial.printf("ERR:IMG:SHORT:%u/%u\n", received, jpegLen);
      }
      return;
    }

    // Text command: accumulate until newline
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdIdx > 0) {
        cmdBuf[cmdIdx] = '\0';
        handleSerialCommand(String(cmdBuf));
        cmdIdx = 0;
      }
    } else if (cmdIdx < CMD_BUF_SIZE - 1) {
      cmdBuf[cmdIdx++] = c;
    }
  }
}
```

- [ ] **Step 4: Update the `loop()` to handle MODE_IMAGE**

In the `loop()` function, update the display mode switch (around line 793). Replace:

```cpp
  switch (displayMode) {
    case MODE_DASHBOARD:
      drawDashboardOverlay();
      break;
    case MODE_NOTIFY:
      drawNotifyOverlay();
      break;
    case MODE_FACE:
    default:
      drawTextOverlay();
      break;
  }
```

With:

```cpp
  if (displayMode != MODE_IMAGE) {
    switch (displayMode) {
      case MODE_DASHBOARD:
        drawDashboardOverlay();
        break;
      case MODE_NOTIFY:
        drawNotifyOverlay();
        break;
      case MODE_FACE:
      default:
        drawTextOverlay();
        break;
    }
  }
```

Also in `loop()`, skip the Tabbie rendering when in image mode. Wrap the `tick() / updateAll() / render()` block (around lines 788-790):

```cpp
  if (displayMode != MODE_IMAGE) {
    tick();
    updateAll();
    render();
  }
```

- [ ] **Step 5: Update `handleSerialCommand` to exit image mode on FACE command**

In `handleSerialCommand()`, inside the `FACE` / `ANIM` block (around line 542), add `displayMode = MODE_FACE;` so that receiving a face command switches back from image mode:

```cpp
  if (cmdType == "FACE" || cmdType == "ANIM") {
    int newMood = webbFaceToMood(payload);
    setMoodTargets(newMood);
    lookTX = lookTY = 0;
    displayMode = MODE_FACE;
    Serial.println("OK:" + payload);
  }
```

Also update the `MODE` handler to support `MODE:IMAGE`:

```cpp
  else if (cmdType == "MODE") {
    payload.toUpperCase();
    if (payload == "DASHBOARD") displayMode = MODE_DASHBOARD;
    else if (payload == "NOTIFY") displayMode = MODE_NOTIFY;
    else if (payload == "IMAGE") displayMode = MODE_IMAGE;
    else displayMode = MODE_FACE;
    Serial.println("OK:MODE:" + payload);
  }
```

- [ ] **Step 6: Add TJpgDec init in `setup()`**

In the `setup()` function, after `tft.fillScreen(TFT_BLACK);` (after line 748), add:

```cpp
  TJpgDec.setJpgScale(1);
  TJpgDec.setCallback(tjpg_output);
```

- [ ] **Step 7: Commit firmware changes**

```bash
git add firmware/firmware.ino
git commit -m "feat(firmware): add JPEG receive and display via TJpgDec"
```

---

### Task 6: End-to-end test

**Prerequisites:** User has installed TJpgDec in Arduino IDE and flashed the updated firmware.

- [ ] **Step 1: Generate test card to disk (no ESP32 needed)**

Run:
```bash
python -c "
from backend.display.renderer import render_test_card, image_to_jpeg
img = render_test_card()
img.save('test_card.png')
jpeg = image_to_jpeg(img)
print(f'PNG saved. JPEG size: {len(jpeg)} bytes')
assert 5000 < len(jpeg) < 20000, f'JPEG size out of range: {len(jpeg)}'
print('PASS: renderer works')
"
```
Expected: `PASS: renderer works` and viewable `test_card.png`

- [ ] **Step 2: Start backend and test the API**

Run: `python -m uvicorn backend.main:app --port 8000`

In another terminal:
```bash
curl -X POST http://127.0.0.1:8000/api/display/test
```
Expected (with ESP32 connected): `{"ok": true, "size_bytes": NNNNN}`
Expected (without ESP32): `{"ok": false, "error": "Serial not connected"}`

- [ ] **Step 3: Verify image appears on ESP32 display**

With ESP32 connected and firmware flashed, run:
```bash
curl -X POST http://127.0.0.1:8000/api/display/test
```
Visual check: ESP32 shows gradient background, "WEBB DISPLAY" text, timestamp, color bars.

- [ ] **Step 4: Verify mode switching — image to face**

After the image is displayed, switch back to face mode:
```bash
curl -X POST http://127.0.0.1:8000/api/webb/face -H "Content-Type: application/json" -d "{\"face\": \"HAPPY\"}"
```
Visual check: Tabbie eyes return with happy expression, animated blinking resumes.

- [ ] **Step 5: Verify mode switching — face back to image**

Push another test image:
```bash
curl -X POST http://127.0.0.1:8000/api/display/test
```
Visual check: Image replaces eyes again.

- [ ] **Step 6: Verify existing voice commands still work**

Say "Hey Webb, what time is it?" or trigger any voice command.
Check: Webb responds normally, face changes work, no errors in console.

- [ ] **Step 7: Clean up and final commit**

Delete the test file:
```bash
rm -f test_card.png
```

```bash
git add -A
git commit -m "feat: Stage 1 complete — hybrid image transport working"
```

---

## Manual Setup (User's Side)

Before Task 5's firmware can be flashed:

1. **Install TJpgDec library:**
   - Arduino IDE → Sketch → Include Library → Manage Libraries
   - Search **"TJpgDec"** by Bodmer → Install (latest version)

2. **Flash the updated firmware:**
   - Open `firmware/firmware.ino` in Arduino IDE
   - Select board: ESP32 Dev Module
   - Select correct COM port
   - Upload

3. **Verify ESP32 connects:**
   - Open Serial Monitor at 115200 baud
   - Should see `=== Webb Desk Bot ===` and `OK:READY`
   - Send `FACE:HAPPY` → should see `OK:HAPPY` and eyes change

No changes to wiring, baud rate, or any other hardware config. Everything else is backend Python that runs on your laptop.
