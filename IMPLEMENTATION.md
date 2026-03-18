# Webb — Implementation Snapshot

This file summarizes what has been implemented in the `f:\Webb1` workspace so far, and how to run it.

## What’s implemented

### Backend (FastAPI + SQLite)
- **FastAPI app**: `backend/main.py`
  - CORS enabled for Vite dev (`http://localhost:5173`)
  - DB tables created on startup (SQLite via SQLAlchemy)
  - Routers mounted:
    - `/api/tasks/*`
    - `/api/reminders/*`
    - `/api/timer/*` (includes WebSocket)
    - `/api/webb/*` (ESP32 face control)
    - `/api/voice/*` (one-shot voice)
    - `/api/notifications/*` (notifications list + WebSocket)
- **SQLite models**: `backend/models.py`
  - `Task`, `Reminder`, `PomodoroSession`
- **Serial (ESP32) face control**: `backend/serial_manager.py`
  - Autodetects likely port, reconnect loop
  - Sends newline-terminated face commands (e.g. `HAPPY\n`)
  - Backend tolerates missing/unknown ESP32 replies (best-effort)
- **Tasks API**: `backend/routes/tasks.py`
  - CRUD + `POST /{id}/complete` (tries to send `HAPPY` face)
- **Reminders API**: `backend/routes/reminders.py`
  - CRUD (scheduler is not wired yet; these are stored in DB)
- **Timer API + WS ticks**: `backend/routes/timer.py`
  - Start/pause/stop/status
  - WebSocket: `ws://127.0.0.1:8000/api/timer/ws`
  - Start -> tries `FOCUS`, Stop/end -> tries `IDLE`
- **Webb API**: `backend/routes/webb.py`
  - Status + face command endpoint
  - Face endpoint returns `ok=false` + `error` on serial failures (HTTP remains responsive)
- **Voice MVP (button-activated, one-shot)**:
  - `backend/voice_manager.py` captures mic audio (SpeechRecognition), transcribes via OpenAI, parses intent via OpenAI, and applies basic actions (task/reminder summaries).
  - `backend/ai_manager.py` parses text → JSON intent using OpenAI Chat.
- **Idle nudges + notifications**:
  - `backend/idle_manager.py` uses `pynput` for activity tracking and publishes `idle_nudge` events.
  - `backend/notifications_hub.py` in-memory event hub.
  - `backend/routes/notifications.py` exposes `GET /api/notifications/` and WS `/api/notifications/ws`.

### Frontend (Vite + React + Tailwind)
- App shell + routing: `frontend/src/App.tsx`
  - Pages:
    - `TasksPage` (`/tasks`)
    - `TimerPage` (`/timer`) with WS subscription
    - `RemindersPage` (`/reminders`)
    - `SettingsPage` (`/settings`)
- Sidebar + face preview: `frontend/src/components/Sidebar.tsx`, `WebbPreview.tsx`
- **VoiceIndicator** (bottom-right mic button): `frontend/src/components/VoiceIndicator.tsx`
  - Calls `POST /api/voice/once` and shows toast with recognized text + result summary.
- **NotificationCenter** (top-right toasts): `frontend/src/components/NotificationCenter.tsx`
  - Connects to `ws://127.0.0.1:8000/api/notifications/ws`
- API helper: `frontend/src/lib/api.ts`

### Electron
- Electron shell: `electron/main.js`, `electron/preload.js`
  - Dev loads `http://localhost:5173`
  - Prod loads `frontend/dist/index.html`

## Environment variables
Create `backend/.env` (not committed) with at least:

```
OPENAI_API_KEY=...
```

Optional:

```
OPENAI_MODEL=gpt-4.1-mini
OPENAI_WHISPER_MODEL=gpt-4o-mini-transcribe
IDLE_THRESHOLD_MINS=20
IDLE_COOLDOWN_SECS=600
VOICE_DISABLED=1
IDLE_DISABLED=1
SERIAL_PORT=COM7
SERIAL_BAUD=115200
```

## How to run (one command)
From the repo root:

```powershell
cd f:\Webb1
npm run dev
```

This starts:
- backend on `http://127.0.0.1:8000`
- frontend on `http://127.0.0.1:5173`
- electron app in dev mode

## Notes / Known gaps
- Reminders are stored and listed, but **do not trigger** automatically yet (APScheduler/TTS pending).
- Voice intent execution is MVP-level (task/reminder creation works; timer start is currently returned as a guidance string).
