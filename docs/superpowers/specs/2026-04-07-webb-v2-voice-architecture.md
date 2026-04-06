# Webb v2 — Professional Voice AI Architecture

> This spec replaces the current voice pipeline, AI brain, and action system with a production-grade architecture. Webb becomes a true AI agent — fast, smart, safe, and agentic. The target is human-like conversation speed (~2-3s response time) with full system + app control.

## Hardware

- **MCU**: ESP32 38-pin + ILI9341 2.8" TFT 240x320
- **Audio**: Laptop microphone + laptop speakers (no hardware audio on ESP32)
- **Connection**: USB serial 115200 baud (CP2102)

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         WEBB CORE                                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   VOICE ENGINE                           │   │
│  │  sounddevice → ring buffer → Silero VAD → capture        │   │
│  │  → Whisper STT → Brain → streaming TTS → speaker         │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                   BRAIN (LLM)                            │   │
│  │  System prompt + context + tools + conversation memory   │   │
│  │  Streaming responses, function calling                   │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                   ACTION ENGINE                          │   │
│  │  Safety Guard → execute → report                         │   │
│  │  GREEN (instant) / YELLOW (confirm) / RED (refuse)       │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│               ┌──────────────┼──────────────┐                    │
│          ┌────▼────┐   ┌────▼────┐   ┌─────▼─────┐             │
│          │ Internal│   │   OS    │   │  Safety   │             │
│          │ App Ctrl│   │ Control │   │  Guard    │             │
│          └─────────┘   └─────────┘   └───────────┘             │
│                                                                  │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │  Activity   │ │   Context    │ │ Conversation │             │
│  │  Monitor    │ │   Builder    │ │   Memory     │             │
│  └─────────────┘ └──────────────┘ └──────────────┘             │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   EVENT BUS (NotificationsHub)           │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────┬────────────────────┬────────────────────┬───────────────┘
    ┌────▼────┐          ┌────▼────┐          ┌────▼────┐
    │ Laptop  │          │ ESP32   │          │ Web     │
    │ Mic+Spk │          │ + TFT   │          │ Dashboard│
    └─────────┘          └─────────┘          └─────────┘
```

---

## 1. Voice Engine

### 1a. Audio Capture — sounddevice + Ring Buffer

Replace `SpeechRecognition` library with `sounddevice` for non-blocking, callback-based audio.

```python
# Continuous audio stream at 16kHz mono
# Callback pushes frames into a thread-safe ring buffer
# VAD reads from the ring buffer
# Zero CPU when silent (callback only fires when audio arrives)
```

**Config:**
- Sample rate: 16000 Hz
- Channels: 1 (mono)
- Chunk size: 512 samples (32ms per frame)
- Ring buffer: 30 seconds (480,000 samples)
- Format: 16-bit PCM (int16)

### 1b. Voice Activity Detection — Silero VAD

Runs on every audio frame (~32ms). Purely local, <1ms per frame.

```python
# For each frame:
#   probability = silero_vad(frame)
#   if probability > 0.5: speech detected
#   if probability < 0.3 for 300ms+: speech ended
```

**VAD responsibilities:**
1. Detect speech start → begin accumulating audio into a capture buffer
2. Detect speech end → finalize capture buffer, hand off to STT
3. During SPEAKING state → mute (ignore all audio, prevent echo)
4. During FOLLOW_UP state → shorter silence threshold (user is in conversation)

**Tuning:**
- Speech start threshold: 0.5
- Speech end threshold: 0.3
- Silence duration to end speech: 800ms (normal), 500ms (follow-up mode)
- Min speech duration: 300ms (ignore clicks, pops, coughs)

### 1c. Gate — When to Process Speech

After VAD captures a complete utterance, the Gate decides whether to process it.

**Three activation modes (all active simultaneously):**

1. **Push-to-talk**: Keyboard shortcut (configurable, default: F2). Bypasses all filtering — everything you say gets processed. Best for noisy environments.

2. **Passive listening**: VAD captures speech → send to fast classifier. The classifier is a two-stage filter:
   - **Stage 1 (instant, local)**: Check for trigger keywords in the first ~2 words. If "Webb", "hey", "open", "start", "set", "what", "how", etc. → activate immediately, skip Stage 2.
   - **Stage 2 (fast AI, ~300ms)**: If no keyword match, send to `gpt-4.1-nano` with the classification prompt. Returns WEBB or IGNORE. Only called for ambiguous speech.

3. **Follow-up window**: After Webb finishes speaking, a 5-second window opens where ALL speech is processed without any gate check. Enables natural multi-turn conversation. Window closes after 5s of silence.

### 1d. Speech-to-Text — Whisper API

After gate activation, send the captured audio buffer to OpenAI Whisper.

- Model: `gpt-4o-mini-transcribe`
- Language: `en` (forced English)
- Audio sent as WAV from the ring buffer (no temp file needed — use in-memory bytes)
- Target latency: 1-1.5s

**Optimization: in-memory WAV encoding**
```python
# Instead of writing to a temp file:
import io, wave
buf = io.BytesIO()
with wave.open(buf, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes(audio_bytes)
buf.seek(0)
# Send buf directly to Whisper API
```

No temp file = no disk I/O = no Windows permission errors.

### 1e. Text-to-Speech — Streaming Sentence Pipeline

**The biggest speed improvement.** Instead of generating the full response then speaking it, we stream sentence by sentence:

```
LLM streams: "Opening Chrome for you. | I've also started your timer."
                        ↓                          ↓
              TTS generates sentence 1    TTS generates sentence 2
                        ↓                          ↓
              Play immediately            Play right after sentence 1
```

**Implementation:**
1. LLM response streams token by token
2. Accumulate tokens into a sentence buffer
3. When a sentence boundary is detected (`. ` `! ` `? ` `\n`), send the sentence to TTS
4. TTS generates audio, playback starts immediately
5. While sentence 1 plays, sentence 2 is already being generated

**Mute-on-speak:**
- When entering SPEAKING state, set a flag that makes VAD ignore all audio
- When TTS playback finishes + 300ms grace period, unmute
- Simple, reliable, prevents echo loops

### 1f. Acknowledgment — Instant Feedback

The moment VAD detects speech has ended:
1. Face changes to THINKING (instant, ~50ms)
2. A short acknowledgment sound plays (optional, a soft chime)
3. User knows Webb heard them before STT even starts

### 1g. State Machine

```
IDLE ──[VAD: speech + gate pass]──→ LISTENING
IDLE ──[push-to-talk key]─────────→ LISTENING
LISTENING ──[VAD: speech ended]───→ PROCESSING
PROCESSING ──[first sentence]─────→ SPEAKING
SPEAKING ──[TTS done]─────────────→ FOLLOW_UP
FOLLOW_UP ──[VAD: speech]─────────→ LISTENING (no gate check)
FOLLOW_UP ──[5s silence]──────────→ IDLE
SPEAKING ──[interrupt key]────────→ IDLE (stop TTS)
ANY ──[error]─────────────────────→ IDLE
```

---

## 2. Brain — LLM with Function Calling

### 2a. Model & Streaming

- Model: `gpt-4.1-mini` (fast, smart enough for actions)
- Streaming: `stream=True` — receive tokens as they're generated
- Function calling: OpenAI tools format
- Max tokens: 256 (keeps responses concise and fast)

### 2b. System Prompt

Dynamic system prompt built by Context Builder. Includes:
- Webb's personality (concise, witty, helpful)
- Current time and date
- Active window and open apps
- Task count, timer status, next reminder
- Conversation history (last 20 turns)
- Available tools (auto-generated from action registry)
- Language: English only
- Response style: short for actions (1 sentence), longer for conversation (up to 3 sentences)

### 2c. Tools (Function Calling)

Instead of asking the LLM to return custom JSON, use OpenAI's native **tools/function calling**:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "launch_app",
            "description": "Open an application by name",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the app to open"}
                },
                "required": ["app_name"]
            }
        }
    },
    # ... all other actions as tools
]
```

**Why this is better than custom JSON:**
- LLM is specifically trained to use this format — fewer parsing errors
- Structured output guaranteed — no JSON parsing failures
- Can call multiple tools in one response
- Tool results can be fed back for multi-step reasoning

### 2d. Multi-Step Agent Loop

For complex requests, the Brain uses a tool-call loop:

```
User: "Set up my morning routine"
  ↓
LLM response: tool_calls: [
  {name: "add_task", args: {title: "Review emails", priority: "high"}},
  {name: "add_task", args: {title: "Stand-up prep", priority: "medium"}},
  {name: "set_reminder", args: {message: "Stand-up", time: "09:30"}},
  {name: "start_timer", args: {minutes: 25}},
  {name: "launch_app", args: {app_name: "chrome"}}
]
  ↓
Action Engine executes all 5 actions
  ↓
Feed results back to LLM
  ↓
LLM generates spoken summary: "Morning routine set — 2 tasks created, reminder at 9:30, 25 minute timer started, and Chrome is open."
  ↓
Stream to TTS → speak
```

### 2e. Fast-Path Bypass

Some commands don't need the LLM at all. A local pattern matcher catches these and executes directly:

| Pattern | Action | Response |
|---------|--------|----------|
| "volume up/down/mute" | `set_volume()` | "Done" (precached audio) |
| "pause/play/next/previous" | `media_control()` | silence (just do it) |
| "stop/cancel" | `interrupt()` | silence |
| "screenshot" | `take_screenshot()` | "Screenshot saved" |
| "start [N] minute timer" | `start_timer(N)` | "Timer started, N minutes" |
| "what time is it" | `datetime.now()` | speak the time directly |

These respond in **<500ms** — no API calls at all.

---

## 3. Action Engine

### 3a. Action Registry with Safety Tiers

Every action is registered with:
```python
@dataclass
class Action:
    name: str
    description: str
    parameters: dict          # JSON schema for OpenAI tools format
    fn: Callable              # The function to execute
    safety: str               # "green", "yellow", "red"
    category: str             # "app", "system", "web", "productivity", "files"
    needs_confirmation: bool  # Derived from safety == "yellow"
```

### 3b. Safety Guard

Enforced in code, not in the AI prompt. The AI can suggest any action — the Safety Guard validates before execution.

```python
def execute_action(name: str, params: dict) -> ActionResult:
    action = registry.get(name)
    if action is None:
        return ActionResult(ok=False, message=f"Unknown action: {name}")
    
    # RED — refuse
    if action.safety == "red":
        return ActionResult(ok=False, message=f"I can't do that — {action.refuse_reason}")
    
    # YELLOW — needs confirmation (handled by Brain, which asks user)
    if action.safety == "yellow":
        return ActionResult(ok=False, needs_confirmation=True, 
                          message=f"Should I {action.description}?")
    
    # GREEN — execute
    try:
        result = action.fn(**params)
        return ActionResult(ok=True, message=result)
    except Exception as e:
        return ActionResult(ok=False, message=f"Failed: {e}")
```

**Path validation for file operations:**
```python
BLOCKED_PATHS = [
    "C:\\Windows", "C:\\Program Files", "C:\\ProgramData",
    "System32", "boot.ini", ".ssh", ".gnupg",
    ".env", "credentials", "secrets",
]

def validate_file_path(path: str) -> bool:
    for blocked in BLOCKED_PATHS:
        if blocked.lower() in path.lower():
            return False
    return True
```

### 3c. Full Action List

**GREEN — Instant execution:**

*Productivity (Internal App Control):*
- `start_timer(minutes)` — directly calls timer module's start function
- `pause_timer()` — directly pauses
- `stop_timer()` — directly stops
- `get_timer_status()` — returns current state
- `add_task(title, priority, due_date)` — direct DB insert
- `complete_task(title)` — fuzzy match + mark complete
- `delete_task(title)` — fuzzy match + delete
- `list_tasks(filter)` — query DB, return list
- `add_reminder(message, time, repeat)` — direct DB insert
- `delete_reminder(message)` — fuzzy match + delete
- `list_reminders()` — query DB
- `navigate_app(page)` — push route to frontend via WebSocket ("/tasks", "/timer", etc.)

*System:*
- `launch_app(name)` — open by name from registry
- `switch_to(name)` — focus window
- `minimize()` / `maximize()` / `show_desktop()`
- `volume(action)` — up/down/mute/unmute/percentage
- `media(action)` — play/pause/next/prev
- `brightness(action)` — up/down/percentage
- `screenshot()` — capture and save
- `type_text(text)` — type into active window
- `press_key(keys)` — keyboard shortcut (e.g., "ctrl+s")
- `web_search(query)` — Google search
- `open_url(url)` — open in browser
- `open_folder(name)` — known folders
- `open_file(path)` — open a file (after path validation)
- `get_active_window()` — return current window info
- `list_windows()` — return all open windows
- `read_screen()` — screenshot + GPT-4o vision description

*Webb Control:*
- `set_face(face)` — change ESP32 display
- `set_display_mode(mode)` — FACE/DASHBOARD/NOTIFY
- `show_notification(text)` — display on TFT
- `set_display_text(line, text)` — set text line on TFT

**YELLOW — Confirm first:**
- `close_window()` — "Close this window? You might have unsaved work."
- `delete_file(path)` — "Delete [filename]? This can't be undone."
- `move_file(src, dst)` — "Move [file] to [folder]?"
- `shutdown()` / `restart()` / `sleep()` — "Shut down your computer?"
- `empty_trash()` — "Empty the recycle bin?"
- `run_command(cmd)` — "Run terminal command: [cmd]?"
- `install_app(name)` — "Install [app]?"

**RED — Always refuse:**
- Any path containing Windows/System32/Program Files
- Registry edits
- Firewall/antivirus changes
- Credential/password access
- Formatting drives
- User account modifications
- Running obfuscated scripts

### 3d. Confirmation Flow

When an action is YELLOW:

```
Brain calls tool → Safety Guard returns needs_confirmation
  ↓
Brain speaks: "Should I close this window? You might have unsaved work."
  ↓
State → FOLLOW_UP (listening for yes/no)
  ↓
User says "yes" or "no"
  ↓
If yes: execute action, report result
If no: "Okay, I won't."
```

The Brain handles this naturally through conversation — no special UI needed.

---

## 4. Internal App Control (Agentic)

### 4a. Direct Timer Control

Webb's brain calls timer functions directly, not through HTTP:

```python
# In action handlers:
from backend.routes.timer import _timer, _timer_lock, _broadcast, _ensure_tick_task_started

async def start_timer_direct(minutes: int) -> str:
    await _ensure_tick_task_started()
    async with _timer_lock:
        _timer.state = "running"
        _timer.duration_seconds = minutes * 60
        _timer.seconds_remaining = minutes * 60
        _timer.last_tick_monotonic = time.monotonic()
    # Broadcast to all WebSocket clients (updates frontend live)
    await _broadcast(_current_status())
    return f"Timer started: {minutes} minutes"
```

The frontend updates in real-time because the WebSocket broadcast fires. No page navigation needed.

### 4b. Frontend Navigation via WebSocket

Webb can tell the frontend to switch pages:

```python
# Push navigation event
hub.publish_threadsafe({
    "type": "navigate",
    "path": "/timer",
})
```

Frontend listens for this event and calls `navigate('/timer')`. Webb can say "Let me show you" and the app switches to the relevant page.

### 4c. Task/Reminder Direct Control

All task and reminder operations go through direct DB calls (already implemented). The key addition is that results are broadcast via WebSocket so the frontend updates live:

```python
def add_task_direct(title, priority, due_date) -> str:
    with SessionLocal() as db:
        task = Task(title=title, priority=priority, due_date=due_date)
        db.add(task)
        db.commit()
    
    # Notify frontend to refresh
    hub.publish_threadsafe({"type": "task_changed"})
    return f"Added task: {title}"
```

---

## 5. Latency Optimizations

### 5a. Streaming TTS Pipeline

```python
async def stream_and_speak(llm_stream):
    sentence_buffer = ""
    
    for chunk in llm_stream:
        token = chunk.choices[0].delta.content or ""
        sentence_buffer += token
        
        # Check for sentence boundary
        if any(sentence_buffer.rstrip().endswith(p) for p in ['. ', '! ', '? ', '.\n']):
            sentence = sentence_buffer.strip()
            sentence_buffer = ""
            
            # Send sentence to TTS immediately
            # (plays while next sentence is still being generated)
            tts_manager.speak(sentence)  # non-blocking, queues for playback
    
    # Flush remaining buffer
    if sentence_buffer.strip():
        tts_manager.speak(sentence_buffer.strip())
```

### 5b. Fast-Path Matcher

```python
FAST_PATTERNS = {
    r"^volume\s+(up|down|mute|unmute|\d+)": ("volume", lambda m: {"action": m.group(1)}),
    r"^(pause|play|next|previous|stop)\s*(music|track)?$": ("media", lambda m: {"action": m.group(1)}),
    r"^screenshot$": ("screenshot", lambda m: {}),
    r"^(start|set)\s+(?:a\s+)?(\d+)\s*(?:min|minute)": ("start_timer", lambda m: {"minutes": int(m.group(2))}),
    r"^what\s+time\s+is\s+it": ("tell_time", lambda m: {}),
    r"^lock\s*(?:screen|computer)?$": ("lock_screen", lambda m: {}),
    r"^(mute|unmute)$": ("volume", lambda m: {"action": m.group(1)}),
    r"^stop\s*timer$": ("stop_timer", lambda m: {}),
    r"^pause\s*timer$": ("pause_timer", lambda m: {}),
}

def try_fast_path(text: str) -> Optional[ActionResult]:
    lower = text.lower().strip()
    for pattern, (action_name, param_fn) in FAST_PATTERNS.items():
        match = re.match(pattern, lower)
        if match:
            params = param_fn(match)
            return action_registry.execute(action_name, params)
    return None
```

### 5c. Parallel Execution

Actions execute in parallel with TTS:
```python
# Don't: execute action → wait → speak
# Do: speak + execute simultaneously

import concurrent.futures

with concurrent.futures.ThreadPoolExecutor() as pool:
    # Start speaking
    speak_future = pool.submit(tts_manager.speak_sync, "Opening Chrome for you")
    # Start action simultaneously
    action_future = pool.submit(action_registry.execute, "launch_app", {"app_name": "chrome"})
    # Both complete roughly the same time
```

### 5d. Client Caching

OpenAI client is created once and reused (already implemented). No reconnect overhead per call.

### 5e. In-Memory Audio Processing

No temp files for STT. Audio stays in memory as bytes:
```python
# WAV encoding in memory
buf = io.BytesIO()
with wave.open(buf, 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes(audio_int16_bytes)
buf.seek(0)
buf.name = "audio.wav"  # OpenAI SDK needs a .name attribute
client.audio.transcriptions.create(model=..., file=buf)
```

---

## 6. Activity Monitor

### 6a. Active Window Tracking
- Background thread, polls every 2 seconds
- Stores: window title, process name, timestamp
- Fed into Brain context on every voice command

### 6b. Screen Context (on-demand)
- Triggered by "What's on my screen?" / "Read this"
- Takes screenshot → sends to GPT-4o Vision
- Returns text description that Brain can reason about

### 6c. Usage Patterns (future)
- Track which apps are used when
- Learn daily routines
- Enable proactive suggestions

---

## 7. Conversation Memory

### 7a. Rolling History
- Last 20 turns stored in memory
- Sent with every LLM call as conversation context
- Enables: "What did I just say?", "Do that again", "Actually make it high priority"

### 7b. Session Scope
- History resets on backend restart
- No persistent conversation storage (privacy-first)
- Future: optional persistent memory for learned preferences

---

## 8. Display Sync

### 8a. Face ↔ State Mapping

| Voice State | ESP32 Face | Meaning |
|-------------|-----------|---------|
| IDLE | IDLE (blinking, looking around) | Waiting |
| LISTENING | LISTENING (wide eyes) | Hearing you |
| PROCESSING | THINKING (looking up) | Working on it |
| SPEAKING | HAPPY / contextual | Responding |
| EXECUTING | FOCUS (intense) | Doing something |
| FOLLOW_UP | IDLE (attentive) | Waiting for more |

### 8b. Web Dashboard Sync
- Frontend polls `/api/voice/status` for voice state
- Webb face preview mirrors ESP32 face
- Actions show as activity feed
- Tasks/timer/reminders update live via WebSocket

---

## 9. Dependencies

### Replace
- `SpeechRecognition` → `sounddevice` + manual Whisper API calls
- `pyaudio` → `sounddevice` (cleaner, non-blocking)

### Add
- `sounddevice` — audio I/O
- `silero-vad` — voice activity detection (via `torch` or ONNX)
- `numpy` — audio buffer operations
- `torch` — for Silero VAD model (or `onnxruntime` for lighter weight)

### Keep
- `openai` — STT, LLM, TTS
- `pygame` — audio playback
- `pyautogui` — system control
- `pycaw` — volume control
- `mss` — screenshots
- `pynput` — idle detection

### Remove
- `SpeechRecognition` — replaced by direct sounddevice + Whisper
- `pyaudio` — replaced by sounddevice
- `pvporcupine` / `pvrecorder` — replaced by Silero VAD + keyword check

---

## 10. File Structure — New & Modified

### New Files
| File | Responsibility |
|------|---------------|
| `backend/audio_engine.py` | sounddevice stream, ring buffer, Silero VAD |
| `backend/voice_engine.py` | Voice state machine, gate, capture, STT orchestration (replaces voice_loop.py + voice_manager.py) |
| `backend/fast_path.py` | Regex-based fast command matcher, bypasses LLM |
| `backend/safety_guard.py` | Action safety validation, path checking, tier enforcement |
| `backend/streaming_tts.py` | Sentence-level streaming TTS pipeline (replaces tts_manager.py) |

### Major Rewrites
| File | Changes |
|------|---------|
| `backend/ai_manager.py` | Use OpenAI tools/function calling instead of custom JSON. Streaming responses. Remove `is_directed_at_webb` (moved to gate). |
| `backend/action_registry.py` | Add safety tiers, OpenAI tools schema generation, confirmation flow |
| `backend/system_controller.py` | Add safety levels to all actions, add `press_key`, `run_command` |
| `backend/context_builder.py` | Cleaner context, shorter prompt for speed |

### Delete
| File | Reason |
|------|--------|
| `backend/voice_loop.py` | Replaced by `voice_engine.py` |
| `backend/voice_manager.py` | Replaced by `voice_engine.py` + `audio_engine.py` |
| `backend/tts_manager.py` | Replaced by `streaming_tts.py` |

### Modified
| File | Changes |
|------|---------|
| `backend/main.py` | Wire new modules, remove old imports |
| `backend/routes/voice.py` | Use voice_engine instead of voice_loop |
| `backend/routes/webb.py` | Use streaming_tts |
| `backend/requirements.txt` | Add sounddevice, numpy, torch/onnxruntime; remove SpeechRecognition, pyaudio, pvporcupine, pvrecorder |
| `frontend/src/lib/notifications.ts` | Add `navigate`, `task_changed` event types |
| `frontend/src/App.tsx` | Listen for `navigate` events and push routes |

---

## 11. Environment Variables

```env
# Voice Engine
VOICE_MODE=passive             # passive | push_to_talk | disabled
PTT_KEY=f2                     # Push-to-talk hotkey
VAD_THRESHOLD=0.5              # Silero VAD speech detection threshold
VAD_SILENCE_MS=800             # ms of silence to end speech
FOLLOW_UP_TIMEOUT_MS=5000      # ms to wait for follow-up before going idle

# STT
OPENAI_WHISPER_MODEL=gpt-4o-mini-transcribe

# Brain
OPENAI_MODEL=gpt-4.1-mini
WEBB_USER_NAME=Piyush

# TTS
OPENAI_TTS_VOICE=fable
TTS_ENABLED=1
TTS_SPEED=1.05

# Safety
SAFETY_CONFIRM_TIMEOUT_S=10   # Seconds to wait for yes/no on YELLOW actions
```
