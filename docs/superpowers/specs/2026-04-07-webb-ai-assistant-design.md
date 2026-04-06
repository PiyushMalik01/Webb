# Webb AI Assistant — Full Ecosystem Design

> Webb is a physical desk bot (ESP32 + ILI9341 2.8" TFT 240x320) connected to a laptop via USB serial. This spec transforms Webb from a productivity dashboard into a full AI assistant — voice-activated, conversational, system-controlling, and context-aware. Think Jarvis, named Webb.

## Hardware

- **MCU**: ESP32 38-pin
- **Display**: ILI9341 2.8" TFT, 240x320, SPI at 40MHz
- **Pins**: MISO=19, MOSI=23, SCLK=18, CS=5, DC=27, RST=33
- **Library**: TFT_eSPI with TFT_eSprite for flicker-free rendering
- **Connection**: USB serial at 115200 baud (CP2102 USB-UART)
- **Audio**: Laptop mic + laptop speakers (no hardware audio on ESP32)

## Architecture

```
[User Voice] → [Laptop Mic]
                    ↓
            ┌──────────────────────────────────────┐
            │         LAPTOP (The Brain)           │
            │                                      │
            │  Wake Word ──→ STT ──→ AI Brain     │
            │  (Picovoice)  (Whisper) (OpenAI)    │
            │                           │          │
            │              ┌────────────┼────────┐ │
            │              ↓            ↓        ↓ │
            │         System Ctrl   Task/Timer  TTS│
            │         (pyautogui)   (FastAPI)  (OpenAI)
            │              │            │        │ │
            │              ↓            ↓        ↓ │
            │         OS Actions    Database  Speaker│
            │                                      │
            │  Serial Manager ──→ ESP32 Display    │
            │  Activity Monitor (window tracking)  │
            │  Web Dashboard (React)               │
            └──────────────────────────────────────┘
                    ↓
            [ESP32 + TFT Display]
```

## 1. Voice Pipeline

### 1a. Wake Word Detection

**Library**: `pvporcupine` (Picovoice) — lightweight, local, low CPU.

- Runs as a daemon thread from backend startup
- Continuously listens through the default mic using `pvrecorder`
- Wake word: **"Hey Webb"** (custom keyword via Picovoice console, free tier allows 3)
- On detection:
  1. Publish `wake_word` event via NotificationsHub
  2. Send `FACE:LISTENING` to ESP32
  3. Hand off to speech capture

**Fallback wake word**: If Picovoice key not set, use the existing mic button (manual trigger) as fallback. The system works both ways — voice-activated and click-activated.

**Environment**:
- `PICOVOICE_ACCESS_KEY` — required for wake word (free at picovoice.ai)
- `WAKE_WORD_ENABLED=1` — enable/disable background listening
- `WAKE_WORD_SENSITIVITY=0.5` — detection sensitivity (0.0 to 1.0)

### 1b. Speech Capture & STT

**Reuses existing** `voice_manager.py` Whisper integration, with modifications:

- After wake word fires, capture audio for up to 7 seconds (or until silence detected)
- Transcribe via OpenAI Whisper (`gpt-4o-mini-transcribe`)
- If transcription empty/failed → speak "I didn't catch that" → return to IDLE
- On success → pass text to AI Brain

### 1c. Text-to-Speech (TTS)

**Provider**: OpenAI TTS API
- Model: `tts-1` (low latency) for quick responses, `tts-1-hd` for longer speech
- Voice: `fable` (configurable via `OPENAI_TTS_VOICE` env var)
- Output format: `mp3` streamed to temp file, played via `pygame.mixer`

**Implementation** — new file `backend/tts_manager.py`:
- `speak(text: str) -> None` — generate audio, play through speakers
- `speak_async(text: str) -> None` — non-blocking version for use in async context
- While speaking: face shows contextual expression (HAPPY, neutral, etc.)
- After speaking: face returns to IDLE
- Queue-based: if multiple speak calls, they queue and play in order
- Interrupt: new wake word detection cancels current speech

**Environment**:
- `OPENAI_TTS_VOICE=fable` — voice selection
- `OPENAI_TTS_MODEL=tts-1` — model (tts-1 or tts-1-hd)
- `TTS_ENABLED=1` — enable/disable speech output

### 1d. Continuous Listening Loop

**State machine** managed by new `backend/voice_loop.py`:

```
IDLE → [wake word] → LISTENING → [speech captured] →
PROCESSING → [AI response + action] → SPEAKING → [TTS done] → IDLE
```

States and corresponding display:
| State | ESP32 Face | App Face | What happens |
|-------|-----------|----------|-------------|
| IDLE | Blinking idle face | IDLE | Wake word detector active |
| LISTENING | Big eyes + sound waves | LISTENING | Capturing speech |
| PROCESSING | Thinking dots animation | SURPRISED | AI processing |
| SPEAKING | Contextual expression | HAPPY/IDLE | TTS playing |
| EXECUTING | Focus face | FOCUS | System action running |

**API endpoint** for manual trigger still works:
- `POST /api/voice/once` — existing one-shot (skip wake word)
- `GET /api/voice/status` — returns current voice loop state
- `POST /api/voice/interrupt` — cancel current speech/action

## 2. System Controller

New file `backend/system_controller.py` — executes OS-level actions on Windows.

### 2a. App Launcher

**App registry** stored in `backend/app_registry.json`:
```json
{
  "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "vscode": "code",
  "spotify": "spotify",
  "explorer": "explorer",
  "notepad": "notepad",
  "calculator": "calc"
}
```

- Auto-discovery: on first run, scan Start Menu shortcuts and Program Files to populate
- `launch_app(name: str) -> str` — fuzzy match name against registry, launch via `subprocess.Popen`
- Returns confirmation text: "Opening Chrome" or "I don't know that app"
- User can add apps via Settings page or voice: "Remember that Figma is at C:\path\figma.exe"

### 2b. Window Management

Uses `pygetwindow` and `win32gui`:

- `switch_to(app_name: str)` — find window by title substring, bring to front
- `minimize_active()` / `maximize_active()` / `close_active()` — control active window
- `show_desktop()` — Win+D shortcut
- `list_windows() -> list[str]` — return titles of all open windows (for AI context)

### 2c. System Actions

| Command | Implementation |
|---------|---------------|
| Volume up/down | `pycaw` ISimpleAudioVolume, step ±10% |
| Mute/unmute | `pycaw` toggle mute |
| Media play/pause | `pyautogui.press('playpause')` |
| Next/prev track | `pyautogui.press('nexttrack')` / `pyautogui.press('prevtrack')` |
| Screenshot | `mss` capture → save to `~/Pictures/Screenshots/` |
| Lock screen | `ctypes.windll.user32.LockWorkStation()` |
| Brightness up/down | WMI `WmiMonitorBrightness` (laptop only) |
| Sleep/shutdown | Confirm with user first, then `subprocess` |

### 2d. Web & Search

- `web_search(query: str)` — opens default browser with `https://www.google.com/search?q={query}`
- `open_url(url: str)` — opens URL in default browser via `webbrowser.open()`
- Common shortcuts: "open YouTube" → youtube.com, "open GitHub" → github.com

### 2e. Typing & Dictation

- `type_text(text: str)` — `pyautogui.write(text, interval=0.02)` into active window
- **Dictation mode**: enter with "start dictation" / "dictate"
  - Continuous STT → type output → until "stop dictation" / "that's all"
  - Face shows LISTENING throughout
  - Small pause between sentences

### 2f. File Operations

- `open_folder(name: str)` — maps known folders: Downloads, Documents, Desktop, Pictures
- `open_recent_file(folder: str, ext: str)` — finds most recent file matching criteria
- `open_file(path: str)` — `os.startfile(path)` 

### 2g. Action Registry

All actions are registered in a central `ACTIONS` dict that the AI Brain can reference:

```python
ACTIONS = {
    "launch_app": {"fn": launch_app, "desc": "Open an application by name", "params": ["app_name"]},
    "switch_to": {"fn": switch_to, "desc": "Switch to an open window", "params": ["app_name"]},
    "volume": {"fn": set_volume, "desc": "Set volume level or mute", "params": ["action"]},
    "web_search": {"fn": web_search, "desc": "Search Google", "params": ["query"]},
    "type_text": {"fn": type_text, "desc": "Type text into active window", "params": ["text"]},
    "screenshot": {"fn": take_screenshot, "desc": "Take a screenshot", "params": []},
    "lock_screen": {"fn": lock_screen, "desc": "Lock the computer", "params": []},
    # ... etc
}
```

The AI Brain receives this registry as part of its system prompt, so it knows exactly what Webb can do.

## 3. AI Brain — Conversational Intelligence

### 3a. Conversation Manager

New file `backend/conversation_manager.py`:

- Maintains a rolling conversation history (last 20 turns)
- Each turn: `{role: "user"|"assistant", content: str, timestamp: str}`
- History is per-session (resets on backend restart)
- Injected into every AI call as message history

### 3b. System Prompt

The AI receives a rich system prompt that defines Webb's personality and capabilities:

```
You are Webb, a personal AI desk assistant. You sit on {user_name}'s desk
as a physical bot with a display face.

Your personality: helpful, concise, slightly witty. You're eager but not
annoying. Keep responses under 2 sentences for actions, up to 4 for
conversation.

Current context:
- Time: {current_time}
- Date: {current_date}  
- Active window: {active_window_title}
- Open apps: {running_apps}
- Tasks: {active_task_count} active, {completed_today} completed today
- Timer: {timer_state}
- Next reminder: {next_reminder}

Available actions you can perform:
{action_registry_descriptions}

When the user asks you to do something:
1. Determine which action(s) to call
2. Return a JSON response with actions AND a spoken response

Response format:
{
  "speak": "Opening Chrome for you",
  "actions": [{"name": "launch_app", "params": {"app_name": "chrome"}}],
  "face": "HAPPY"
}

For pure conversation (jokes, questions, chat), just return:
{
  "speak": "your response here",
  "actions": [],
  "face": "HAPPY"
}

For multi-step actions, chain them:
{
  "speak": "Opening Chrome and searching for weather",
  "actions": [
    {"name": "launch_app", "params": {"app_name": "chrome"}},
    {"name": "web_search", "params": {"query": "weather today"}}
  ],
  "face": "FOCUS"
}

If you can't do something, say so honestly. Never make up capabilities.
```

### 3c. Context Injection

Before every AI call, `backend/context_builder.py` gathers:
- Current time and date
- Active window title (from activity monitor)
- List of open windows
- Task count and upcoming reminders (from database)
- Timer status
- Last 20 conversation turns

This is injected into the system prompt dynamically.

### 3d. Response Processing

After AI returns JSON:
1. Parse `speak` → send to TTS
2. Parse `actions` → execute sequentially via system controller
3. Parse `face` → send to ESP32
4. Store the exchange in conversation history
5. Push events to frontend via NotificationsHub

### 3e. Existing Feature Integration

The AI can also trigger existing Webb features:
- "Add a task called review PR" → creates task via database
- "Start a 25 minute timer" → starts Pomodoro
- "Set a reminder for 3pm to call mom" → creates reminder
- "What's on my todo list?" → reads tasks from DB, speaks them
- "How much time is left on my timer?" → reads timer state, speaks it

These go through the same action registry — the AI calls them just like system actions.

## 4. Activity Monitor

New file `backend/activity_monitor.py`:

### 4a. Active Window Tracking

- Background thread polls active window every 2 seconds
- Uses `win32gui.GetForegroundWindow()` + `GetWindowText()`
- Stores: `{title: str, process: str, since: datetime}`
- Exposed via `GET /api/activity/current`
- Injected into AI context on every voice command

### 4b. Screen Context (On-Demand)

- Triggered by: "What's on my screen?" / "Read this" / "What am I looking at?"
- Takes screenshot via `mss`
- Sends to OpenAI GPT-4o Vision API with prompt: "Describe what you see on this screen. Be concise."
- AI receives the description and can act on it
- "Read this error" → captures, AI reads error, suggests fix

### 4c. Smart Suggestions

Proactive nudges based on activity:
- Idle too long → "Want me to start a focus timer?"
- Timer finished → "Nice session! You knocked out 2 tasks. Break time?"
- Reminder triggered → Webb speaks it aloud instead of just toast
- Been in YouTube for 30+ min → gentle nudge (configurable, not annoying)

These extend the existing `idle_manager.py` with richer context awareness.

## 5. TFT Display Protocol

### 5a. Command Format

All commands are newline-terminated strings over serial at 115200 baud:

```
COMMAND:PAYLOAD\n
```

| Command | Payload | Description |
|---------|---------|-------------|
| `FACE` | `IDLE\|HAPPY\|FOCUS\|SLEEPY\|REMINDER\|LISTENING\|SURPRISED\|THINKING\|SPEAKING` | Set face expression |
| `TEXT` | `<line>:<content>` | Set text on line 1-4 (below face in dashboard mode) |
| `STATUS` | `<json>` | Update status bar: `{"tasks":3,"timer":"12:30","wifi":"ok"}` |
| `ANIM` | `LISTENING\|THINKING\|SPEAKING` | Start looping animation |
| `PROGRESS` | `<0-100>` | Show/update circular progress ring |
| `NOTIFY` | `<message>` | Show temporary notification banner (3s auto-dismiss) |
| `MODE` | `FACE\|DASHBOARD\|NOTIFY` | Switch display layout |
| `CLEAR` | (none) | Clear screen to black |
| `BRIGHTNESS` | `<0-255>` | Set backlight brightness |

### 5b. Display Modes

**FACE mode** (default):
- Full 240x320 display dedicated to animated face
- Face centered, large (approximately 200x160 drawing area)
- Status text below face (1 line, e.g., "Listening..." / "3 tasks left")
- Smooth transitions between expressions using sprite buffer

**DASHBOARD mode**:
- Top half: smaller face (120x100)
- Bottom half: status info
  - Active tasks count
  - Timer countdown (if running)
  - Next reminder
  - Current time

**NOTIFY mode**:
- Face continues showing
- Bottom 80px: notification banner with text
- Auto-returns to previous mode after 3 seconds

### 5c. Face Animations (ESP32 Firmware)

Using `TFT_eSprite` for flicker-free double-buffered rendering:

**New faces added:**
- `THINKING` — eyes looking up-right, animated dots below (. .. ...)
- `SPEAKING` — mouth opens/closes in a simple animation loop

**Animation details:**
- Idle blink: random interval 3-6s, eyes close for 150ms
- Listening: sound wave bars animate beside face (3 bars, oscillating heights)
- Thinking: three dots cycle below face
- Speaking: mouth shape alternates between open/closed every 200ms
- All animations run at ~15 FPS via sprite buffer swap

### 5d. ESP32 Firmware Structure

New directory: `firmware/` in the repo root.

```
firmware/
├── firmware.ino          # Main Arduino sketch
├── faces.h               # Face drawing functions (eyes, mouth, expressions)
├── animations.h          # Animation loops (blink, waves, dots)
├── display_modes.h       # FACE, DASHBOARD, NOTIFY layout renderers
├── serial_protocol.h     # Command parser
└── config.h              # Pin definitions, display settings
```

**firmware.ino loop:**
1. Check serial for incoming commands
2. Parse command → update state
3. Render current state (face + mode + animation)
4. Repeat at ~15 FPS

### 5e. App ↔ Display Sync

- Backend `serial_manager.py` sends display commands
- Same state is also pushed via WebSocket to the frontend
- `WebbPreview` component in the React app mirrors exactly what the TFT shows
- New `DisplayState` type shared between backend and frontend:
  ```
  {mode: "FACE"|"DASHBOARD"|"NOTIFY", face: Face, text: string[], animation: string|null}
  ```

## 6. API Changes

### New Endpoints

```
POST /api/voice/interrupt      — Cancel current speech/processing
GET  /api/voice/status         — Current voice loop state (idle/listening/processing/speaking)
GET  /api/activity/current     — Active window info
POST /api/activity/screenshot  — Take screenshot, return AI description
GET  /api/display/state        — Current display state (mode, face, text)
POST /api/display/mode         — Switch display mode
POST /api/tts/speak            — Speak text through TTS (for testing)
GET  /api/system/apps          — List known apps in registry
POST /api/system/apps          — Add app to registry
```

### Modified Endpoints

- `POST /api/webb/face` — now sends rich `FACE:name` command instead of bare `HAPPY\n`. During development, `serial_manager.py` supports both formats: if firmware is not yet flashed, falls back to old bare format. A `DISPLAY_PROTOCOL=rich|legacy` env var controls this.
- `GET /api/webb/status` — includes display mode and animation state
- `POST /api/voice/once` — now routes through AI Brain (conversation-aware) instead of simple intent parser

## 7. Frontend Changes

### Dashboard Updates
- Webb face preview mirrors TFT display mode
- Voice state indicator (IDLE/LISTENING/PROCESSING/SPEAKING) shown under face
- "Webb is listening..." / "Webb is thinking..." status text

### New Settings Sections
- **Voice**: wake word toggle, sensitivity slider, TTS voice preview
- **System Control**: app registry editor (add/remove apps)
- **Display**: mode selector, brightness slider

### Voice Indicator Enhancement
- Shows voice loop state (not just one-shot)
- Animated when Webb is speaking
- Click to interrupt speech

## 8. Dependencies

### New Python Packages
```
pvporcupine>=3.0        # Wake word detection
pvrecorder>=1.2         # Audio recording for Picovoice
pygame>=2.5             # Audio playback for TTS
pyautogui>=0.9          # Keyboard/mouse automation
pygetwindow>=0.0.9      # Window management
pycaw>=20230407         # Windows audio control
mss>=9.0                # Fast screenshots
comtypes>=1.2           # Windows COM (needed by pycaw)
Pillow>=10.0            # Image handling for screenshots
```

### Environment Variables (new)
```
PICOVOICE_ACCESS_KEY=...          # Wake word (free at picovoice.ai)
WAKE_WORD_ENABLED=1               # Toggle wake word
WAKE_WORD_SENSITIVITY=0.5         # 0.0 to 1.0
OPENAI_TTS_VOICE=fable            # TTS voice name
OPENAI_TTS_MODEL=tts-1            # tts-1 or tts-1-hd
TTS_ENABLED=1                     # Toggle TTS
WEBB_USER_NAME=Piyush             # User's name for personality
SCREEN_CONTEXT_ENABLED=1          # Toggle screen awareness
```

## 9. File Structure — New & Modified

### New Files
| File | Responsibility |
|------|---------------|
| `backend/tts_manager.py` | TTS generation and audio playback |
| `backend/voice_loop.py` | Wake word + continuous listening state machine |
| `backend/system_controller.py` | OS-level actions (apps, windows, volume, etc.) |
| `backend/activity_monitor.py` | Active window tracking, screen context |
| `backend/conversation_manager.py` | Conversation history and context |
| `backend/context_builder.py` | Gathers system context for AI prompts |
| `backend/action_registry.py` | Central registry of all actions AI can call |
| `backend/app_registry.json` | Known application paths |
| `firmware/firmware.ino` | ESP32 main sketch |
| `firmware/faces.h` | Face rendering functions |
| `firmware/animations.h` | Animation loops |
| `firmware/display_modes.h` | Layout renderers |
| `firmware/serial_protocol.h` | Command parser |
| `firmware/config.h` | Hardware configuration |

### Modified Files
| File | Changes |
|------|---------|
| `backend/main.py` | Start voice loop, activity monitor; new route registrations |
| `backend/ai_manager.py` | Replace intent parser with conversational AI Brain |
| `backend/serial_manager.py` | Rich command protocol (`FACE:X` instead of `X`) |
| `backend/voice_manager.py` | Integrate with voice loop, remove standalone one-shot logic |
| `backend/idle_manager.py` | Add smart suggestions, speak nudges via TTS |
| `backend/notifications_hub.py` | New event types: `wake_word`, `voice_state`, `action_executed` |
| `backend/routes/voice.py` | New endpoints: `/status`, `/interrupt` |
| `backend/routes/webb.py` | Display mode/state endpoints |
| `frontend/src/pages/DashboardPage.tsx` | Voice state indicator, mirrored display |
| `frontend/src/pages/SettingsPage.tsx` | Voice, system control, display sections |
| `frontend/src/components/VoiceIndicator.tsx` | Voice loop state, interrupt button |
| `frontend/src/components/WebbPreview.tsx` | Mirror TFT display modes |
| `frontend/src/lib/types.ts` | New types for display state, voice state |
| `requirements.txt` | New dependencies |
