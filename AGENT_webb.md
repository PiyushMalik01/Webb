# Webb Desktop App — Agent Spec

## Project Overview
Build a cross-platform desktop productivity companion app called **Webb** that connects to an ESP32 + OLED hardware device via USB Serial. The app has a clean minimal UI (Notion-like), a Python backend for voice/AI/serial, and an Electron shell to package it as a native desktop app.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop shell | Electron |
| Frontend UI | React + Tailwind CSS |
| Backend | Python + FastAPI |
| Voice input | SpeechRecognition (Google STT or Whisper local) |
| Voice output | pyttsx3 (offline TTS) |
| AI | Anthropic Claude API (claude-sonnet-4-20250514) |
| Database | SQLite via SQLAlchemy |
| Serial (ESP32) | pyserial |
| Frontend-Backend | HTTP REST + WebSocket (for real-time face updates) |

---

## Project Structure

```
webb/
├── electron/
│   ├── main.js               # Electron entry point
│   ├── preload.js            # Context bridge
│   └── package.json
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── Tasks.jsx
│   │   │   ├── Timer.jsx
│   │   │   ├── Reminders.jsx
│   │   │   └── Settings.jsx
│   │   ├── components/
│   │   │   ├── Sidebar.jsx
│   │   │   ├── WebbPreview.jsx   # Shows current OLED face in app
│   │   │   ├── TaskCard.jsx
│   │   │   └── VoiceIndicator.jsx  # Shows when mic is active
│   │   └── main.jsx
│   ├── index.html
│   └── package.json
├── backend/
│   ├── main.py               # FastAPI app entry point
│   ├── serial_manager.py     # ESP32 serial communication
│   ├── voice_manager.py      # Mic listening + TTS (runs as background thread)
│   ├── ai_manager.py         # Claude API integration
│   ├── reminder_manager.py   # Scheduled reminders (APScheduler)
│   ├── models.py             # SQLAlchemy models
│   ├── database.py           # SQLite setup
│   ├── routes/
│   │   ├── tasks.py
│   │   ├── reminders.py
│   │   ├── timer.py
│   │   └── webb.py         # Face/serial control endpoints
│   └── requirements.txt
└── README.md
```

---

## Backend — Python FastAPI

### Serial Manager (`serial_manager.py`)
- Auto-detect ESP32 COM port on startup (scan ports for CP2102)
- Send face commands to ESP32: `IDLE`, `HAPPY`, `FOCUS`, `SLEEPY`, `REMINDER`, `LISTENING`, `SURPRISED`
- Each command is sent as a newline-terminated string e.g. `HAPPY\n`
- Reconnect automatically if serial disconnects
- Expose current connection status via `/api/webb/status`

### Voice Manager (`voice_manager.py`)
- Run as a **background thread** — always listening even when app is minimized
- Wake word: **"hey webb"** using SpeechRecognition
- On wake word detected:
  1. Send `LISTENING` face command to ESP32
  2. Capture full voice command
  3. Send to AI manager for intent parsing
  4. Execute action (add task, start timer, set reminder, etc.)
  5. Speak response back via pyttsx3
  6. Return ESP32 to previous face
- Expose voice status via WebSocket `/ws/voice` so frontend can show mic indicator

### AI Manager (`ai_manager.py`)
- Use Claude API to parse voice commands into structured intents
- System prompt: You are Webb, a helpful desk companion. Parse user voice commands into JSON actions.
- Supported intents:
  - `add_task` → { title, priority, due_date }
  - `complete_task` → { task_id or title }
  - `start_timer` → { duration_minutes }
  - `set_reminder` → { message, time }
  - `list_tasks` → {}
  - `general_chat` → { response: string }
- Also handle idle detection: if no keyboard/mouse activity for 20 minutes, Claude generates a motivational nudge and Webb speaks it

### Reminder Manager (`reminder_manager.py`)
- Use APScheduler for scheduled reminders
- On reminder trigger:
  1. Send `REMINDER` face to ESP32
  2. Speak reminder text via TTS
  3. Show notification in frontend via WebSocket
  4. Mark reminder as triggered in DB

### Database Models (`models.py`)
```python
Task:
  - id, title, priority (low/medium/high), due_date, completed, created_at

Reminder:
  - id, message, trigger_time, repeat (none/daily/weekly), triggered, created_at

PomodoroSession:
  - id, duration_minutes, completed, started_at, ended_at
```

### API Routes

**Tasks** (`/api/tasks`)
- GET `/` — list all tasks (filter: completed, priority)
- POST `/` — create task `{ title, priority, due_date }`
- PATCH `/{id}` — update task
- DELETE `/{id}` — delete task
- POST `/{id}/complete` — mark complete → triggers HAPPY face on ESP32

**Reminders** (`/api/reminders`)
- GET `/` — list reminders
- POST `/` — create reminder `{ message, trigger_time, repeat }`
- DELETE `/{id}` — delete reminder

**Timer** (`/api/timer`)
- POST `/start` — start pomodoro `{ duration_minutes: 25 }` → sends FOCUS face
- POST `/pause` — pause timer
- POST `/stop` — stop timer → sends IDLE face
- GET `/status` — current timer state (running/paused/idle, seconds_remaining)
- WebSocket `/ws/timer` — real-time countdown updates to frontend

**Webb** (`/api/webb`)
- POST `/face` — manually set face `{ face: "HAPPY" }`
- GET `/status` — serial connection status
- POST `/speak` — make Webb speak `{ text: "..." }`

---

## Frontend — React + Tailwind

### Design System
- Font: Inter
- Colors: White background, gray-50 sidebar, gray-900 text, indigo-500 accents
- Minimal, clean — no gradients, no shadows except subtle card shadows
- Style reference: Notion / Linear

### Pages

**Tasks Page (`/tasks`)**
- List of tasks grouped by: Today / Upcoming / Completed
- Each task card: checkbox, title, priority badge, due date
- Add task button → inline input form (no modal)
- Completing a task triggers confetti animation + HAPPY face sent to ESP32
- Filter bar: All / High / Medium / Low priority

**Timer Page (`/timer`)**
- Large circular countdown display
- Start / Pause / Stop buttons
- Pomodoro presets: 25/5, 50/10, custom
- Session history (today's sessions)
- When running: FOCUS face on ESP32, ring pulses on screen

**Reminders Page (`/reminders`)**
- List of upcoming reminders with time and message
- Add reminder: message input + time picker + repeat dropdown
- Past/triggered reminders shown in muted style

**Settings Page (`/settings`)**
- Serial port selector (dropdown of available ports)
- Wake word toggle on/off
- TTS voice selector
- Claude API key input
- Idle detection timeout slider (5–60 mins)
- Test buttons: "Test Face", "Test Voice", "Test Serial"

### Components

**WebbPreview** (shown in sidebar)
- SVG face animation matching current ESP32 state
- Faces: idle (blinking eyes), happy (curved eyes + smile), focus (narrow eyes), sleepy (half eyes + zzz), reminder (raised brow), listening (big eyes + waves)
- Smooth CSS transitions between faces

**VoiceIndicator**
- Floating mic icon bottom-right
- Pulses when listening
- Shows last spoken command as tooltip
- Click to manually trigger listening

**Sidebar**
- Webb face preview (top)
- Nav links: Tasks, Timer, Reminders, Settings
- Bottom: Serial connection status dot (green/red)
- Voice status indicator

---

## Voice Flow (Background — Always Running)

```
Python thread starts on app launch
         │
         ▼
Continuously listen for wake word "hey webb"
         │
    detected?
         │ yes
         ▼
Send LISTENING to ESP32
Record voice command (5 second window)
         │
         ▼
Send to Claude API for intent parsing
         │
         ▼
Execute intent:
  add_task     → POST /api/tasks, say "Task added!"
  start_timer  → POST /api/timer/start, say "Starting focus timer"
  set_reminder → POST /api/reminders, say "Reminder set for {time}"
  list_tasks   → GET /api/tasks, say "You have {n} tasks today"
  general_chat → say Claude's response
         │
         ▼
Send previous face back to ESP32
Broadcast voice event to frontend via WebSocket
```

---

## Idle Detection

- Track last user activity (keyboard/mouse) using `pynput`
- If idle for > threshold (default 20 mins):
  1. Generate motivational message via Claude
  2. Send REMINDER face to ESP32
  3. Speak message via TTS e.g. "Hey, you've been away for a while. Ready to get back to it?"
  4. Show notification in frontend
- Reset on any user activity

---

## ESP32 Serial Protocol

Simple newline-terminated commands sent from Python to ESP32:

```
IDLE\n       → idle blinking face
HAPPY\n      → happy curved eyes + smile
FOCUS\n      → narrow focused eyes + "FOCUS MODE" text
SLEEPY\n     → half closed eyes + zzz
REMINDER\n   → raised eyebrow + "! REMINDER !" text
LISTENING\n  → big round eyes + "listening" text
SURPRISED\n  → wide eyes + O mouth
```

ESP32 responds with `OK:FACENAME\n` to confirm.

---

## Setup & Run Instructions (for README)

### Prerequisites
- Node.js 20+
- Python 3.11+
- Arduino IDE with ESP32 + Adafruit SSD1306 libraries

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
python main.py
# Runs on http://localhost:8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

### Electron Setup
```bash
cd electron
npm install
npm start
# Opens desktop app window pointing to frontend
```

### requirements.txt
```
fastapi
uvicorn
pyserial
SpeechRecognition
pyttsx3
anthropic
APScheduler
SQLAlchemy
pynput
pyaudio
websockets
python-dotenv
```

---

## Environment Variables (`.env` in backend/)

```
ANTHROPIC_API_KEY=your_key_here
SERIAL_PORT=COM7          # or /dev/ttyUSB0 on Linux/Mac
SERIAL_BAUD=115200
IDLE_THRESHOLD_MINS=20
WAKE_WORD=hey webb

```

---

## Build Order for Cursor

Build in this exact order so each step is testable:

1. **Backend skeleton** — FastAPI app, SQLite models, basic routes (no voice yet)
2. **Serial manager** — connect to ESP32, send face commands, test via `/api/webb/face`
3. **Frontend skeleton** — Electron + React + Tailwind, sidebar, routing between pages
4. **Tasks page** — full CRUD, completing task triggers HAPPY face
5. **Timer page** — pomodoro countdown, WebSocket updates, FOCUS face
6. **Reminders page** — create/list/delete, APScheduler triggers, TTS speaks reminder
7. **Voice manager** — background thread, wake word, intent parsing via Claude
8. **Idle detection** — pynput tracking, motivational nudges
9. **Settings page** — port selector, API key, toggles
10. **Polish** — WebbPreview SVG animations, transitions, packaging

---

## Notes for Cursor

- Keep backend and frontend completely separate processes — backend is a Python FastAPI server, frontend is React served by Vite, Electron loads the Vite URL in development and a built index.html in production
- All ESP32 serial communication goes through the Python backend only — never from Electron/JS directly
- Voice listener must run as a daemon thread so it doesn't block the FastAPI event loop — use `threading.Thread(daemon=True)`
- Use SQLite with SQLAlchemy ORM — no external database needed
- pyttsx3 is offline TTS — no API key needed for speaking
- For Claude API calls keep a conversation history per session for context-aware responses
- Frontend should reconnect WebSocket automatically if backend restarts
- On Windows, pyaudio requires special installation — add note in README to install via pipwin or use `pip install pipwin && pipwin install pyaudio`
