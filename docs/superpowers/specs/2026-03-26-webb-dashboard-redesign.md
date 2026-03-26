# Webb Dashboard Redesign — UI/UX + Core Features

> Webb is a physical desk bot (Arduino + TFT screen) that sits on your desk showing faces and reacting to your workflow. This desktop app is its **control dashboard** — the brain that manages tasks, timers, reminders, voice commands, and syncs state to the hardware bot via serial.

## 1. Color Palette & Visual Identity

### Palette

| Token           | Value                        | Usage                          |
|-----------------|------------------------------|--------------------------------|
| `--bg-base`     | `#0f0f0f`                    | App background                 |
| `--bg-surface`  | `#1a1a1a`                    | Cards, sidebar                 |
| `--bg-elevated` | `#252525`                    | Inputs, hover states           |
| `--border`      | `rgba(255,255,255,0.06)`     | Panel/card borders             |
| `--border-focus`| `rgba(124,154,146,0.5)`      | Input focus rings              |
| `--text-primary`| `#f5f5f5`                    | Headings, primary text         |
| `--text-secondary`| `#a0a0a0`                  | Body text, labels              |
| `--text-muted`  | `#666666`                    | Timestamps, hints              |
| `--accent`      | `#e8e4df`                    | Active nav, selected states    |
| `--accent-color`| `#7c9a92`                    | Interactive highlights (sage)  |
| `--danger`      | `#c47070`                    | Delete, overdue (muted red)    |
| `--success`     | `#7c9a7c`                    | Completion, connected (muted green) |

### Typography
- Keep **Outfit** (body) and **Sora** (headings) — they work well.
- Remove letter-spacing tightening on body text; keep it only on h1/h2.

### Buttons
- **Default**: Flat, `--bg-elevated` background, `--border` border, `--text-primary` text. Subtle hover brightening.
- **Primary CTA** (Add task, Start timer): Keep the 3D cube effect as a signature, but restyle — cube faces use `#333` (top) and `#1a1a1a` (right) instead of red. Button face uses `--accent-color` text on `--bg-elevated`.
- **Destructive** (Delete): Flat button, `--danger` text, no fill. Hover adds subtle `--danger` background.
- **Remove** the global `button` CSS that forces cube pseudo-elements on every button. Cube is opt-in via `.btn-cube` class only.

### Background
- Solid `--bg-base`. Remove the colored blur orbs from App.tsx.
- No glassmorphism blur. Panels differentiated by background shade only.

### Cards
- Background: `--bg-surface`
- Border: `1px solid var(--border)`
- Border-radius: `12px`
- No backdrop-filter, no box-shadow. Clean flat cards.

## 2. Layout & Navigation

### Sidebar (240px fixed, collapsible on mobile)
- **Top**: Webb face preview — larger than current (~100x80 viewBox render)
- **Nav**: Icon + label for each route. Icons are simple SVG line icons (no library needed, hand-coded like the mic icon).
  - Home (dashboard) — grid/home icon
  - Tasks — checkbox icon
  - Timer — clock icon
  - Reminders — bell icon
  - Settings — gear icon
- **Active state**: Left accent bar (3px `--accent-color`), text becomes `--accent`
- **Bottom**: Connection status — small dot + "Bot connected" / "Bot offline" text
- **Mobile**: Horizontal bottom nav bar with icons only

### New Dashboard Page (`/` — Home)
This replaces the current redirect to `/tasks`.

- **Webb face**: Large SVG (~160x120), centered. Animated idle blink.
- **Status line** below face: Contextual text based on current state
  - Timer running: "Focusing... 12:30 left"
  - Tasks pending: "3 tasks to go today"
  - Idle: "All clear. Ready when you are."
  - Bot offline: "Running in software mode"
- **Quick stats row**: 3 compact cards side by side
  - Active tasks count
  - Timer status (idle / Xm remaining)
  - Next reminder (relative time or "None set")
- **Quick actions**: "Add task" and "Start timer" shortcut buttons

### Page Structure (Tasks, Timer, Reminders, Settings)
- Page title left-aligned, filters/controls right
- Content area: stack of cards with `12px` gap
- Empty states: Muted secondary text, centered. e.g. "No tasks yet."
- Error states: Inline below the relevant form, `--danger` colored text

## 3. Core Feature Fixes

### 3a. Reminder Auto-Triggering (Backend)

**Current problem**: Reminders are stored in the database but never fire.

**Solution**: Add a background async task that runs every 30 seconds on the FastAPI event loop.

- On startup, launch an `asyncio` background task (no new dependency needed — use `asyncio.create_task` in the lifespan)
- Every 30s: query for reminders where `trigger_time <= now` and `triggered = False`
- For each match:
  1. Set `triggered = True` in DB
  2. Push `reminder_triggered` event via NotificationsHub (with reminder message + id)
  3. Send `REMINDER` face to serial manager
- **Repeating reminders**: After triggering, if `repeat = "daily"`, create a new reminder with `trigger_time + 24h`. Same for `"weekly"` (+7 days). The original stays `triggered = True`.
- Frontend: NotificationCenter already listens to WebSocket events — add handling for `reminder_triggered` event type to show a toast with the reminder message.

### 3b. Timer Completion Feedback

**Current problem**: Timer hits 0 and just stops. No celebration, no notification.

**Solution**:
- Backend: When timer reaches 0, push a `timer_complete` event via NotificationsHub. Set Webb face to `HAPPY`.
- Frontend TimerPage: On receiving `timer_complete` via WebSocket or detecting `seconds_remaining = 0` after running:
  - Fire `confetti()` (already imported in TasksPage, reuse it)
  - Show toast: "Pomodoro complete!"
  - Request browser `Notification` permission on first timer start; fire native notification on complete
- Add a **session counter**: Track completed sessions today in component state (resets on page load). Display "Session N today" below the timer ring.

### 3c. Task Improvements

- **Delete button**: Add a delete/trash icon button on each task card (both active and completed). Calls `DELETE /api/tasks/{id}`.
- **Due date input**: Add an optional date picker to the add-task form. Display due dates on task cards.
- **Overdue highlight**: If `due_date < today` and `!completed`, show a subtle `--danger` left border on the task card.

### 3d. Settings Page Cleanup

Group into sections with clear headings:

1. **Webb Connection**: Serial status, port, baud rate, last face. "Test Face" dropdown + send button.
2. **Timer**: Default duration input (saves to localStorage).
3. **Voice**: Enable/disable toggle.
4. **Developer** (collapsed by default, expandable): Raw idle/voice disable toggles, debug info.

## 4. Webb Personality & Presence

### Idle Blink Animation
- When face is `IDLE`, every 4-5 seconds, eyes briefly close (thin lines) for ~200ms then reopen.
- Implemented as a CSS animation on the eye elements, triggered by a React interval.

### Contextual Face Sync (Frontend-only, no hardware needed)
The sidebar face reacts to app state automatically:

| Context                     | Face        | Duration     |
|-----------------------------|-------------|-------------|
| Default / Dashboard         | IDLE        | Persistent   |
| Timer running               | FOCUS       | While running |
| Task completed              | HAPPY       | 3 seconds    |
| Reminder triggered          | REMINDER    | 5 seconds    |
| Voice listening             | LISTENING   | While active |
| Voice processing            | SURPRISED   | While active |
| Timer complete              | HAPPY       | 5 seconds    |

This is managed via a simple React context (`WebbFaceContext`) that any component can push face changes to, with automatic timeout resets to IDLE.

### Status Text Under Face
Replace the static face label badge with a dynamic contextual line:
- Pull from timer state, task count, next reminder time
- Updates every few seconds via existing WebSocket data
- Gives Webb a "voice" in the UI without TTS

## 5. File Changes Summary

### New Files
- `frontend/src/pages/DashboardPage.tsx` — New home/dashboard page
- `frontend/src/context/WebbFaceContext.tsx` — Shared face state context

### Modified Files
- `frontend/src/index.css` — New palette, remove red theme, restructure button system
- `frontend/src/App.tsx` — Add dashboard route, remove blur orbs, wrap in face context
- `frontend/src/components/Sidebar.tsx` — Icons, new styling, larger face, bottom status
- `frontend/src/components/WebbPreview.tsx` — Blink animation, larger size option, status text
- `frontend/src/components/VoiceIndicator.tsx` — Restyle to match muted palette
- `frontend/src/components/NotificationCenter.tsx` — Handle `reminder_triggered` + `timer_complete` events
- `frontend/src/pages/TasksPage.tsx` — Delete button, due date, overdue highlight, restyled
- `frontend/src/pages/TimerPage.tsx` — Completion confetti/notification, session counter, restyled
- `frontend/src/pages/RemindersPage.tsx` — Restyled
- `frontend/src/pages/SettingsPage.tsx` — Grouped sections, developer collapse
- `backend/main.py` — Add reminder checker background task in lifespan
- `backend/notifications_hub.py` — Add `reminder_triggered` and `timer_complete` event types
- `backend/routes/timer.py` — Push `timer_complete` event + `HAPPY` face on completion

### Not Changed
- `backend/models.py`, `backend/database.py` — Schema is sufficient as-is
- `backend/serial_manager.py` — Works fine, no changes needed
- `backend/ai_manager.py` — Out of scope for this iteration
- `electron/` — No changes needed for this scope
