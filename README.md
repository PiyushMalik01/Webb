# Webb - AI Desk Assistant

A physical AI desk assistant built with an ESP32 microcontroller, 2.8" ILI9341 TFT display, voice control, and Windows automation. Webb sits on your desk, listens to voice commands, controls your PC, and displays rich animated content including a Spotify now-playing widget.

## Architecture

```
User Voice --> AudioEngine (VAD) --> VoiceEngine (STT) --> AIManager (OpenAI) --> Actions + TTS
                                                              |
Electron App <--> FastAPI Backend <--> ESP32 (WiFi TCP / USB Serial)
                       |
              Spotify API / External Sources
```

**Three-layer stack:**
- **Electron App** — Desktop UI dashboard for tasks, reminders, timers, and system controls
- **FastAPI Backend** — AI brain, voice pipeline, display renderer, action dispatch
- **ESP32 + TFT** — Physical display surface with animated Tabbie eyes and JPEG image transport

## Features

### Voice Control
- Passive wake-word listening with Silero VAD
- Speech-to-text via OpenAI Whisper
- Natural language commands via GPT function calling
- Streaming TTS responses via OpenAI

### Windows Automation
- Volume and media control
- App launching and window management
- Multi-monitor awareness
- System commands (lock, sleep, screenshot)

### Display Pipeline
- **Tabbie Eyes** — Animated expressive avatar on ESP32 (local rendering, zero latency)
- **JPEG Transport** — Push any image/animation to ESP32 over WiFi TCP or USB serial
- **GIF Playback** — Animated GIFs with frame skipping and persistent TCP connections
- **Spotify Player** — Real-time now-playing widget with:
  - Rotating vinyl disc / album art alternating display
  - Animated equalizer bars
  - Scrolling marquee for long track names
  - Wavy animated progress line
  - Dark/light theme switching
  - Embedded video element card
- **Idle Video** — Ambient animation when nothing is playing (triggers after 10s idle)

### Task Management
- Create, complete, and manage tasks via voice or UI
- Reminders with scheduled notifications
- Focus timers with ESP32 display integration

## Project Structure

```
Webb/
  backend/
    main.py                   # FastAPI app, startup/shutdown
    ai_manager.py             # OpenAI chat + function calling
    voice_engine.py           # Voice state machine
    audio_engine.py           # Microphone capture + VAD
    serial_manager.py         # ESP32 serial/WiFi communication
    system_controller.py      # Windows automation actions
    windows_api.py            # pywinauto + multi-monitor
    action_registry.py        # Function registry for LLM tools
    streaming_tts.py          # OpenAI TTS via pygame
    context_builder.py        # Dynamic system prompt builder
    spotify_auth.py           # Spotify OAuth flow
    spotify_player.py         # Now-playing poller + display driver
    display/
      renderer.py             # PIL image -> JPEG conversion
      transport.py            # WiFi TCP + serial image transport
      gif_player.py           # Animated GIF playback
      idle_player.py          # Idle state video playback
      spotify_renderer.py     # Spotify player card renderer
    routes/
      spotify.py              # Spotify API endpoints
      display.py              # Display push/test endpoints
      voice.py, tasks.py, reminders.py, timer.py, etc.
  firmware/
    firmware.ino              # ESP32 Arduino firmware (TFT_eSPI + TJpgDec)
  frontend/
    src/
      pages/DashboardPage.tsx # Main dashboard UI
      assets/                 # Media assets (GIFs, videos)
  electron/                   # Electron desktop wrapper
```

## Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **Arduino IDE** with ESP32 board support
- **Windows 10/11** (required for system automation features)
- **OpenAI API key** (for voice, chat, and TTS)
- **Spotify Developer App** (optional, for now-playing display)

### Hardware
- ESP32 dev board (ESP32-WROOM or similar)
- 2.8" ILI9341 TFT display (320x240, SPI)

### Arduino Libraries
- TFT_eSPI (configured for ILI9341)
- TJpgDec (JPEG decoding)
- ESPmDNS
- WiFi

## Setup

### 1. Clone and install

```bash
git clone https://github.com/PiyushMalik01/Webb.git
cd Webb

# Backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r backend/requirements.txt
pip install opencv-python-headless requests

# Frontend
cd frontend && npm install && cd ..

# Root (for concurrently)
npm install
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
# Required
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_WHISPER_MODEL=whisper-1
OPENAI_TTS_VOICE=fable

# Voice
VOICE_MODE=passive
VAD_THRESHOLD=0.5

# ESP32 WiFi (update to your ESP32's IP)
ESP32_HOST=172.16.212.200
SERIAL_BAUD=115200
DISPLAY_PROTOCOL=rich

# Spotify (optional)
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/api/spotify/callback

# User
WEBB_USER_NAME=YourName
ENV=dev
```

### 3. Flash ESP32 firmware

1. Open `firmware/firmware.ino` in Arduino IDE
2. Update WiFi credentials (`WIFI_SSID`, `WIFI_PASS`) at the top
3. Update the static IP, gateway, and subnet to match your network
4. Select your ESP32 board and COM port
5. Upload

The ESP32 will print its IP on the serial monitor at boot.

### 4. Spotify setup (optional)

1. Create an app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Set redirect URI to `http://127.0.0.1:8000/api/spotify/callback`
3. Select **Web API**
4. Add client ID and secret to `.env`
5. Start the backend, then visit `http://127.0.0.1:8000/api/spotify/login` to authorize
6. Play a song — the display updates automatically

## Running

```bash
# Start everything (backend + frontend + electron)
npm run dev

# Or individually
npm run dev:backend            # FastAPI on :8000
npm run dev:frontend           # Vite on :5173
npm run dev:electron           # Electron app
```

## API Endpoints

### Display
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/display/test` | Push a test card to ESP32 |
| POST | `/api/display/push` | Upload image/GIF to display |
| POST | `/api/display/stop` | Stop GIF playback |

### Spotify
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/spotify/login` | Start Spotify OAuth flow |
| GET | `/api/spotify/status` | Check auth and poller status |
| POST | `/api/spotify/start` | Start the now-playing poller |
| POST | `/api/spotify/stop` | Stop the poller |
| POST | `/api/spotify/theme` | Toggle dark/light theme |
| POST | `/api/spotify/theme?theme=dark` | Set specific theme |

### Voice, Tasks, Reminders, Timer
See `backend/routes/` for full endpoint documentation.

## Display Pipeline Stages

The display system is being built in stages. Current progress:

- [x] **Stage 1** — Hybrid transport + JPEG image protocol (WiFi TCP + serial fallback)
- [x] **Stage 1.5** — GIF playback, Spotify player, idle video
- [ ] **Stage 2** — Simple compositor (priority tiers: INTERRUPT > ACTIVE > AMBIENT)
- [ ] **Stage 3** — Migrate avatars into source model
- [ ] **Stage 4** — External sources (weather, Claude Code hooks)
- [ ] **Stage 5** — Polish (dirty-rect optimization, transitions)

See `dynamic_display_implementation_plan.md` for the full roadmap.

## ESP32 Protocol

The ESP32 accepts two types of commands over WiFi TCP (port 3456) or USB serial (115200 baud):

**Text commands** (newline-terminated):
- `FACE:<mood>` — Set avatar expression (HAPPY, IDLE, THINKING, etc.)
- `TEXT:<line>:<message>` — Set text overlay
- `NOTIFY:<message>` — Show notification banner
- `MODE:<mode>` — Switch display mode
- `CLEAR` — Clear display

**Binary commands:**
- `0x10 [4-byte length] [JPEG data]` — Push a JPEG frame to display

## License

Private project. All rights reserved.
