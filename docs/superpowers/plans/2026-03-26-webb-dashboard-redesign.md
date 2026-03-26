# Webb Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul Webb's desktop dashboard with a minimal dark aesthetic, fix core features (reminder auto-trigger, timer completion, task delete), and add Webb personality (contextual faces, idle blink, status text).

**Architecture:** Frontend-first approach — retheme CSS/components first so all subsequent feature work renders correctly. Then backend fixes (reminder scheduler, timer events). Then new pages and personality system. Each task produces a working, committable state.

**Tech Stack:** React 19, Tailwind CSS 3, TypeScript, FastAPI, SQLAlchemy, WebSocket

**Spec:** `docs/superpowers/specs/2026-03-26-webb-dashboard-redesign.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/context/WebbFaceContext.tsx` | Shared face state (React context + provider) |
| `frontend/src/pages/DashboardPage.tsx` | Home page with large Webb face, stats, quick actions |
| `backend/reminder_scheduler.py` | Background async task that checks & triggers reminders |

### Modified Files
| File | Changes |
|------|---------|
| `frontend/src/index.css` | New palette, button system, remove red/glass theme |
| `frontend/src/App.tsx` | Remove blur orbs, add dashboard route, wrap in face context |
| `frontend/src/components/Sidebar.tsx` | Icons, new styling, larger face, bottom connection status |
| `frontend/src/components/WebbPreview.tsx` | Blink animation, size prop, status text |
| `frontend/src/components/VoiceIndicator.tsx` | Restyle to muted palette |
| `frontend/src/components/NotificationCenter.tsx` | Handle `reminder_triggered` + `timer_complete` events |
| `frontend/src/components/DesktopTopBar.tsx` | Restyle to match new palette |
| `frontend/src/pages/TasksPage.tsx` | Delete button, due date input, overdue highlight, restyled |
| `frontend/src/pages/TimerPage.tsx` | Completion confetti/notification, session counter, restyled |
| `frontend/src/pages/RemindersPage.tsx` | Restyled to new palette |
| `frontend/src/pages/SettingsPage.tsx` | Grouped sections, developer collapse |
| `frontend/src/lib/notifications.ts` | Add `reminder_triggered` and `timer_complete` to type union |
| `backend/main.py` | Start reminder scheduler in startup, stop in shutdown |
| `backend/routes/timer.py` | Publish `timer_complete` event + `HAPPY` face on countdown end |
| `backend/notifications_hub.py` | No schema change needed — already accepts any dict |

---

## Task 1: Retheme CSS — New Palette & Button System

**Files:**
- Modify: `frontend/src/index.css`

This is the foundation — every subsequent task depends on these styles being in place.

- [ ] **Step 1: Replace CSS custom properties and body styles**

Replace the entire `:root` block and `html, body` rules in `frontend/src/index.css` with:

```css
:root {
  --bg-base: #0f0f0f;
  --bg-surface: #1a1a1a;
  --bg-elevated: #252525;
  --border: rgba(255, 255, 255, 0.06);
  --border-focus: rgba(124, 154, 146, 0.5);
  --text-primary: #f5f5f5;
  --text-secondary: #a0a0a0;
  --text-muted: #666666;
  --accent: #e8e4df;
  --accent-color: #7c9a92;
  --danger: #c47070;
  --success: #7c9a7c;
}

html,
body {
  height: 100%;
  margin: 0;
  background: var(--bg-base);
}

body {
  font-family: Outfit, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
  color: var(--text-primary);
}
```

- [ ] **Step 2: Replace heading styles**

Replace the `h1, h2, h3, h4` block with:

```css
h1,
h2,
h3,
h4 {
  font-family: Sora, Outfit, ui-sans-serif, system-ui;
  letter-spacing: -0.02em;
  font-weight: 700;
  color: var(--text-primary);
}
```

- [ ] **Step 3: Replace `#app` and utility classes**

Replace `#app`, `.glass-panel`, `.glass-panel-strong`, `.surface-title`, `.theme-text`, `.theme-text-soft`, `.theme-muted` with:

```css
#app {
  min-height: 100%;
  background: transparent;
}

.card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
}

.card-elevated {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 12px;
}

.text-primary {
  color: var(--text-primary);
}

.text-secondary {
  color: var(--text-secondary);
}

.text-muted {
  color: var(--text-muted);
}
```

- [ ] **Step 4: Replace button classes**

Remove the entire global `button` block (lines ~144-214 in the current file — everything from `/* Global button shape system */` through `button:focus-visible`). Also remove `.cube-link` and all its variants (lines ~216-313). Also remove `.accent-button`, `.subtle-button`.

Replace with:

```css
/* Base button reset */
button {
  border-radius: 8px;
  transition: background 140ms ease, border-color 140ms ease, opacity 140ms ease;
}

button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
}

/* Primary button */
.btn-primary {
  background: var(--bg-elevated);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--accent);
  padding: 8px 16px;
  font-weight: 600;
  font-size: 0.875rem;
}

.btn-primary:hover {
  background: #2e2e2e;
  border-color: rgba(255, 255, 255, 0.15);
}

/* Secondary/ghost button */
.btn-ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 8px 16px;
  font-weight: 500;
  font-size: 0.875rem;
}

.btn-ghost:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

/* Danger button (text-only, no fill) */
.btn-danger {
  background: transparent;
  border: 1px solid transparent;
  color: var(--danger);
  padding: 8px 12px;
  font-weight: 500;
  font-size: 0.875rem;
}

.btn-danger:hover {
  background: rgba(196, 112, 112, 0.1);
}

/* Signature cube button — opt-in for primary CTAs only */
.btn-cube {
  --cube-depth: 5px;
  --cube-press-depth: 2px;
  --cube-press-ease: cubic-bezier(0.2, 0.82, 0.24, 1);
  position: relative;
  overflow: visible;
  background: var(--bg-elevated);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--accent-color);
  padding: 8px 16px;
  font-weight: 600;
  font-size: 0.875rem;
  border-radius: 0 !important;
  transition: transform 170ms var(--cube-press-ease), filter 170ms var(--cube-press-ease);
}

.btn-cube::before {
  content: '';
  position: absolute;
  left: 1px;
  right: 0;
  top: calc(var(--cube-depth) * -1);
  height: var(--cube-depth);
  background: linear-gradient(180deg, #444, #333);
  transform: skewX(-42deg);
  transform-origin: bottom;
  pointer-events: none;
  transition: top 170ms var(--cube-press-ease), height 170ms var(--cube-press-ease);
}

.btn-cube::after {
  content: '';
  position: absolute;
  top: 1px;
  right: calc(var(--cube-depth) * -1);
  width: var(--cube-depth);
  bottom: 0;
  background: linear-gradient(180deg, #333, #1a1a1a);
  transform: skewY(-42deg);
  transform-origin: left;
  pointer-events: none;
  transition: right 170ms var(--cube-press-ease), width 170ms var(--cube-press-ease);
}

.btn-cube:hover {
  filter: brightness(1.08);
}

.btn-cube:active {
  transform: translate(3px, -3px);
}

.btn-cube:active::before {
  height: var(--cube-press-depth);
  top: calc(var(--cube-press-depth) * -1);
}

.btn-cube:active::after {
  width: var(--cube-press-depth);
  right: calc(var(--cube-press-depth) * -1);
}
```

- [ ] **Step 5: Replace field-control and remaining utilities**

Replace `.field-control` and its variants with:

```css
.field-control {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-primary);
  border-radius: 8px;
}

.field-control::placeholder {
  color: var(--text-muted);
}

.field-control:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px rgba(124, 154, 146, 0.15);
}
```

Keep `.enter-up` and `@keyframes enter-up` as-is.

- [ ] **Step 6: Replace desktop-topbar styles**

Replace all `.desktop-topbar` rules with:

```css
.desktop-topbar {
  width: 100%;
  border-radius: 0;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.desktop-topbar__drag {
  -webkit-app-region: drag;
  padding-right: 150px;
}

.no-drag {
  -webkit-app-region: no-drag;
}

.desktop-topbar button {
  border-radius: 6px !important;
  background: transparent !important;
  border: 1px solid transparent !important;
}

.desktop-topbar button::after,
.desktop-topbar button::before {
  content: none !important;
}

.desktop-topbar button:hover {
  background: rgba(255, 255, 255, 0.06) !important;
}
```

- [ ] **Step 7: Verify the frontend compiles**

Run: `cd F:/Webb1/frontend && npx tsc --noEmit 2>&1 | head -20`

Expected: No CSS-related errors (component class name mismatches will be fixed in subsequent tasks).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/index.css
git commit -m "retheme: replace red/glass palette with minimal dark aesthetic"
```

---

## Task 2: Update App Shell & DesktopTopBar

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/DesktopTopBar.tsx`

- [ ] **Step 1: Remove blur orbs from App.tsx**

Replace the entire content of `frontend/src/App.tsx` with:

```tsx
import { Navigate, Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { RemindersPage } from './pages/RemindersPage'
import { SettingsPage } from './pages/SettingsPage'
import { TasksPage } from './pages/TasksPage'
import { TimerPage } from './pages/TimerPage'
import { VoiceIndicator } from './components/VoiceIndicator'
import { NotificationCenter } from './components/NotificationCenter'
import { DesktopTopBar } from './components/DesktopTopBar'

export default function App() {
  return (
    <div className="relative min-h-screen" style={{ background: 'var(--bg-base)', color: 'var(--text-primary)' }}>
      <div className="relative flex min-h-screen w-full flex-col">
        <DesktopTopBar />
        <div className="flex min-h-0 flex-1 flex-col md:flex-row md:gap-4 md:px-4 md:py-4">
          <Sidebar />
          <main className="flex-1 px-4 py-4 md:px-6 md:py-6">
            <Routes>
              <Route path="/" element={<Navigate to="/tasks" replace />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/timer" element={<TimerPage />} />
              <Route path="/reminders" element={<RemindersPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </main>
        </div>
      </div>
      <VoiceIndicator />
      <NotificationCenter />
    </div>
  )
}
```

Note: The `"/"` route will be changed to Dashboard in Task 9. For now keep redirect to `/tasks`.

- [ ] **Step 2: Restyle DesktopTopBar**

Replace the entire content of `frontend/src/components/DesktopTopBar.tsx` with:

```tsx
import { useEffect, useMemo, useState } from 'react'

type MenuAction = { label: string; action: string }
type MenuGroup = { label: string; items: MenuAction[] }

async function runAction(action: string) {
  try {
    await window.webb?.runAction?.(action)
  } catch {
    // no-op in browser mode
  }
}

export function DesktopTopBar() {
  const [openMenu, setOpenMenu] = useState<string | null>(null)

  useEffect(() => {
    function closeMenu() { setOpenMenu(null) }
    window.addEventListener('mousedown', closeMenu)
    return () => window.removeEventListener('mousedown', closeMenu)
  }, [])

  const menus = useMemo<MenuGroup[]>(
    () => [
      {
        label: 'File',
        items: [
          { label: 'New Window', action: 'app:new-window' },
          { label: 'Close Window', action: 'window:close' },
          { label: 'Quit', action: 'app:quit' },
        ],
      },
      {
        label: 'Edit',
        items: [
          { label: 'Undo', action: 'edit:undo' },
          { label: 'Redo', action: 'edit:redo' },
          { label: 'Cut', action: 'edit:cut' },
          { label: 'Copy', action: 'edit:copy' },
          { label: 'Paste', action: 'edit:paste' },
          { label: 'Select All', action: 'edit:select-all' },
        ],
      },
      {
        label: 'View',
        items: [
          { label: 'Reload', action: 'view:reload' },
          { label: 'Force Reload', action: 'view:force-reload' },
          { label: 'Toggle DevTools', action: 'view:devtools-toggle' },
          { label: 'Zoom In', action: 'view:zoom-in' },
          { label: 'Zoom Out', action: 'view:zoom-out' },
          { label: 'Reset Zoom', action: 'view:zoom-reset' },
          { label: 'Toggle Fullscreen', action: 'view:fullscreen-toggle' },
        ],
      },
      {
        label: 'Window',
        items: [
          { label: 'Minimize', action: 'window:minimize' },
          { label: 'Maximize / Restore', action: 'window:maximize-toggle' },
          { label: 'Close', action: 'window:close' },
        ],
      },
      { label: 'Help', items: [{ label: 'Project Home', action: 'help:project-home' }] },
    ],
    [],
  )

  return (
    <header className="desktop-topbar">
      <div className="desktop-topbar__drag flex h-10 items-center px-3">
        <div className="no-drag flex items-center gap-1">
          <div className="mr-3 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Webb</div>
          {menus.map((menu) => (
            <div key={menu.label} className="relative" onMouseDown={(e) => e.stopPropagation()}>
              <button
                type="button"
                className={[
                  'rounded-md px-2.5 py-1 text-sm font-medium transition',
                  openMenu === menu.label
                    ? 'bg-white/10 text-white'
                    : 'hover:bg-white/6',
                ].join(' ')}
                style={{ color: openMenu === menu.label ? 'var(--text-primary)' : 'var(--text-secondary)' }}
                onClick={(e) => {
                  e.stopPropagation()
                  setOpenMenu((x) => (x === menu.label ? null : menu.label))
                }}
              >
                {menu.label}
              </button>

              {openMenu === menu.label ? (
                <div
                  className="no-drag absolute left-0 top-full z-[70] mt-1 w-52 rounded-lg p-1"
                  style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                >
                  {menu.items.map((item) => (
                    <button
                      key={item.label}
                      type="button"
                      className="block w-full rounded-md px-3 py-2 text-left text-sm transition hover:bg-white/6"
                      style={{ color: 'var(--text-secondary)' }}
                      onClick={(e) => {
                        e.stopPropagation()
                        runAction(item.action)
                        setOpenMenu(null)
                      }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </header>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/DesktopTopBar.tsx
git commit -m "retheme: clean up App shell and DesktopTopBar"
```

---

## Task 3: Restyle Sidebar with Icons

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Rewrite Sidebar with icons, new styling, bottom connection status**

Replace the entire content of `frontend/src/components/Sidebar.tsx` with:

```tsx
import { NavLink } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import { apiGet } from '../lib/api'
import type { WebbStatus } from '../lib/types'
import { WebbPreview } from './WebbPreview'

function cn(...xs: Array<string | false | undefined | null>) {
  return xs.filter(Boolean).join(' ')
}

const navItems = [
  {
    to: '/tasks',
    label: 'Tasks',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
  {
    to: '/timer',
    label: 'Timer',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
  },
  {
    to: '/reminders',
    label: 'Reminders',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
    ),
  },
  {
    to: '/settings',
    label: 'Settings',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    ),
  },
]

export function Sidebar() {
  const [status, setStatus] = useState<WebbStatus | null>(null)
  const [backendOk, setBackendOk] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function refresh() {
      try {
        await apiGet<{ status: string }>('/health')
        if (!cancelled) setBackendOk(true)
      } catch {
        if (!cancelled) setBackendOk(false)
      }

      try {
        const s = await apiGet<WebbStatus>('/api/webb/status')
        if (!cancelled) setStatus(s)
      } catch {
        if (!cancelled) setStatus(null)
      }
    }

    refresh()
    const t = window.setInterval(refresh, 2500)
    return () => { cancelled = true; window.clearInterval(t) }
  }, [])

  const face = (status?.last_face as any) ?? 'IDLE'
  const dotColor = backendOk ? (status?.connected ? 'var(--success)' : 'var(--danger)') : 'var(--text-muted)'
  const connectionLabel = backendOk
    ? status?.connected ? 'Bot connected' : 'Bot offline'
    : 'Backend down'

  return (
    <aside
      className="enter-up w-full shrink-0 flex flex-col md:w-60"
      style={{ background: 'var(--bg-surface)', borderRight: '1px solid var(--border)' }}
    >
      <div className="p-4">
        <WebbPreview face={face} />
      </div>

      <nav className="flex-1 px-2 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
                isActive ? 'nav-active' : 'nav-inactive',
              )
            }
            style={({ isActive }) => ({
              background: isActive ? 'var(--bg-elevated)' : 'transparent',
              color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
              borderLeft: isActive ? '3px solid var(--accent-color)' : '3px solid transparent',
            })}
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-3" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: dotColor }}
          />
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {connectionLabel}
          </span>
        </div>
      </div>
    </aside>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "retheme: sidebar with icons, minimal styling, bottom status"
```

---

## Task 4: Restyle WebbPreview with Blink Animation

**Files:**
- Modify: `frontend/src/components/WebbPreview.tsx`

- [ ] **Step 1: Rewrite WebbPreview with blink animation and size prop**

Replace the entire content of `frontend/src/components/WebbPreview.tsx` with:

```tsx
import { useEffect, useState } from 'react'

type Face = 'IDLE' | 'HAPPY' | 'FOCUS' | 'SLEEPY' | 'REMINDER' | 'LISTENING' | 'SURPRISED'

function Eyes({ mood, blinking }: { mood: Face; blinking: boolean }) {
  if (blinking) {
    return (
      <>
        <path d="M14 18 L26 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M38 18 L50 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'FOCUS') {
    return (
      <>
        <path d="M14 18 L26 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M38 16 L50 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'SLEEPY') {
    return (
      <>
        <path d="M14 18 Q20 16 26 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M38 18 Q44 16 50 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'HAPPY') {
    return (
      <>
        <path d="M14 16 Q20 22 26 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M38 16 Q44 22 50 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'SURPRISED' || mood === 'LISTENING') {
    return (
      <>
        <circle cx="20" cy="18" r="3.2" stroke="currentColor" strokeWidth="2" fill="none" />
        <circle cx="44" cy="18" r="3.2" stroke="currentColor" strokeWidth="2" fill="none" />
      </>
    )
  }
  return (
    <>
      <circle cx="20" cy="18" r="2.5" stroke="currentColor" strokeWidth="2" fill="none" />
      <circle cx="44" cy="18" r="2.5" stroke="currentColor" strokeWidth="2" fill="none" />
    </>
  )
}

function Mouth({ mood }: { mood: Face }) {
  if (mood === 'HAPPY') {
    return <path d="M24 34 Q32 40 40 34" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
  }
  if (mood === 'SURPRISED') {
    return <circle cx="32" cy="35" r="3.6" stroke="currentColor" strokeWidth="2" fill="none" />
  }
  if (mood === 'SLEEPY') {
    return <path d="M26 36 Q32 34 38 36" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
  }
  if (mood === 'REMINDER') {
    return <path d="M24 36 Q32 32 40 36" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
  }
  return <path d="M26 36 L38 36" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
}

export function WebbPreview({ face = 'IDLE', large = false }: { face?: Face; large?: boolean }) {
  const [blinking, setBlinking] = useState(false)

  useEffect(() => {
    if (face !== 'IDLE') return
    const interval = setInterval(() => {
      setBlinking(true)
      setTimeout(() => setBlinking(false), 200)
    }, 4000 + Math.random() * 2000)
    return () => clearInterval(interval)
  }, [face])

  const width = large ? 160 : 100
  const height = large ? 120 : 80

  return (
    <div
      className="rounded-xl p-4 flex flex-col items-center"
      style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}
    >
      <svg
        width={width}
        height={height}
        viewBox="0 0 64 52"
        aria-hidden="true"
        style={{ color: 'var(--text-secondary)', transition: 'color 300ms ease' }}
      >
        <rect x="1" y="1" width="62" height="50" rx="12" stroke="currentColor" strokeOpacity="0.3" fill="rgba(0,0,0,0.2)" />
        <g style={{ transition: 'opacity 200ms ease' }}>
          <Eyes mood={face} blinking={blinking} />
          <Mouth mood={face} />
          {face === 'LISTENING' ? (
            <path
              d="M8 30 C6 33 6 37 8 40"
              stroke="var(--accent-color)"
              strokeWidth="2"
              strokeLinecap="round"
              fill="none"
            />
          ) : null}
        </g>
      </svg>
      <div className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>{face}</div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/WebbPreview.tsx
git commit -m "retheme: WebbPreview with blink animation and size prop"
```

---

## Task 5: Restyle TasksPage with Delete Button and Due Date

**Files:**
- Modify: `frontend/src/pages/TasksPage.tsx`

- [ ] **Step 1: Rewrite TasksPage**

Replace the entire content of `frontend/src/pages/TasksPage.tsx` with:

```tsx
import { useEffect, useMemo, useState } from 'react'
import confetti from 'canvas-confetti'
import { apiGet, apiSend } from '../lib/api'
import type { Task } from '../lib/types'

type Priority = 'all' | 'high' | 'medium' | 'low'

function badge(priority: Task['priority']) {
  const colors: Record<string, string> = {
    high: 'rgba(196,112,112,0.2)',
    medium: 'rgba(124,154,146,0.2)',
    low: 'rgba(255,255,255,0.08)',
  }
  const textColors: Record<string, string> = {
    high: 'var(--danger)',
    medium: 'var(--accent-color)',
    low: 'var(--text-secondary)',
  }
  return {
    background: colors[priority] ?? colors.low,
    color: textColors[priority] ?? textColors.low,
    borderRadius: '9999px',
    padding: '2px 8px',
    fontSize: '0.75rem',
    fontWeight: 500,
  }
}

function isOverdue(dueDate: string | null): boolean {
  if (!dueDate) return false
  return new Date(dueDate) < new Date(new Date().toDateString())
}

export function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<Task['priority']>('medium')
  const [dueDate, setDueDate] = useState('')
  const [filter, setFilter] = useState<Priority>('all')
  const [err, setErr] = useState<string | null>(null)

  async function refresh() {
    setErr(null)
    const query = filter === 'all' ? '' : `?priority=${filter}`
    const data = await apiGet<Task[]>(`/api/tasks/${query}`)
    setTasks(data)
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e)))
  }, [filter])

  const grouped = useMemo(() => {
    const completed = tasks.filter((t) => t.completed)
    const active = tasks.filter((t) => !t.completed)
    return { active, completed }
  }, [tasks])

  async function addTask() {
    const t = title.trim()
    if (!t) return
    setTitle('')
    setDueDate('')
    await apiSend<Task>('/api/tasks/', {
      method: 'POST',
      body: { title: t, priority, due_date: dueDate || null },
    })
    await refresh()
  }

  async function completeTask(id: number) {
    await apiSend<Task>(`/api/tasks/${id}/complete`, { method: 'POST' })
    confetti({ particleCount: 80, spread: 65, origin: { y: 0.75 } })
    await refresh()
  }

  async function deleteTask(id: number) {
    await apiSend<{ ok: boolean }>(`/api/tasks/${id}`, { method: 'DELETE' })
    await refresh()
  }

  return (
    <div className="enter-up">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Tasks</h1>
        <div className="flex items-center gap-2">
          {(['all', 'high', 'medium', 'low'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setFilter(p)}
              className={filter === p ? 'btn-primary' : 'btn-ghost'}
              style={{ padding: '4px 12px', fontSize: '0.8125rem' }}
            >
              {p === 'all' ? 'All' : p[0].toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="card mt-5 p-4">
        <div className="flex gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Add a task..."
            className="field-control w-full px-3 py-2 text-sm"
            onKeyDown={(e) => {
              if (e.key === 'Enter') addTask().catch((x) => setErr(String(x)))
            }}
          />
          <input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className="field-control px-3 py-2 text-sm"
          />
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as Task['priority'])}
            className="field-control px-3 py-2 text-sm"
          >
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <button
            onClick={() => addTask().catch((x) => setErr(String(x)))}
            className="btn-cube px-4 py-2 text-sm"
          >
            Add
          </button>
        </div>
        {err ? <div className="mt-3 text-sm" style={{ color: 'var(--danger)' }}>{err}</div> : null}
      </div>

      <div className="mt-6 space-y-6">
        <section>
          <div className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>Active</div>
          <div className="mt-3 space-y-2">
            {grouped.active.length === 0 ? (
              <div className="text-sm" style={{ color: 'var(--text-muted)' }}>No tasks yet.</div>
            ) : (
              grouped.active.map((t) => (
                <div
                  key={t.id}
                  className="card-elevated flex items-center justify-between px-4 py-3"
                  style={{
                    borderLeft: isOverdue(t.due_date) ? '3px solid var(--danger)' : '3px solid transparent',
                  }}
                >
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => completeTask(t.id).catch((x) => setErr(String(x)))}
                      className="h-5 w-5 rounded border flex-shrink-0"
                      style={{ borderColor: 'rgba(255,255,255,0.2)', background: 'transparent' }}
                      aria-label="Complete task"
                    />
                    <div>
                      <div className="text-sm font-medium">{t.title}</div>
                      <div className="mt-1 flex items-center gap-2">
                        <span style={badge(t.priority)}>{t.priority}</span>
                        {t.due_date ? (
                          <span className="text-xs" style={{ color: isOverdue(t.due_date) ? 'var(--danger)' : 'var(--text-muted)' }}>
                            {t.due_date}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => deleteTask(t.id).catch((x) => setErr(String(x)))}
                    className="btn-danger"
                    style={{ padding: '4px 8px' }}
                    aria-label="Delete task"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                  </button>
                </div>
              ))
            )}
          </div>
        </section>

        <section>
          <div className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>Completed</div>
          <div className="mt-3 space-y-2">
            {grouped.completed.length === 0 ? (
              <div className="text-sm" style={{ color: 'var(--text-muted)' }}>Nothing completed yet.</div>
            ) : (
              grouped.completed.map((t) => (
                <div key={t.id} className="card-elevated flex items-center justify-between px-4 py-3 opacity-60">
                  <div className="flex items-center gap-3">
                    <div className="h-5 w-5 rounded" style={{ background: 'var(--success)', opacity: 0.4 }} aria-hidden="true" />
                    <div className="text-sm line-through" style={{ color: 'var(--text-muted)' }}>{t.title}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span style={badge(t.priority)}>{t.priority}</span>
                    <button
                      onClick={() => deleteTask(t.id).catch((x) => setErr(String(x)))}
                      className="btn-danger"
                      style={{ padding: '4px 8px' }}
                      aria-label="Delete task"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/TasksPage.tsx
git commit -m "feat: restyle TasksPage, add delete button and due date input"
```

---

## Task 6: Restyle TimerPage with Session Counter

**Files:**
- Modify: `frontend/src/pages/TimerPage.tsx`

- [ ] **Step 1: Rewrite TimerPage with completion detection and session counter**

Replace the entire content of `frontend/src/pages/TimerPage.tsx` with:

```tsx
import { useEffect, useMemo, useRef, useState } from 'react'
import confetti from 'canvas-confetti'
import { apiGet, apiSend, apiWsUrl } from '../lib/api'
import type { TimerStatus } from '../lib/types'

function formatSeconds(total: number) {
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function TimerPage() {
  const [status, setStatus] = useState<TimerStatus>({ state: 'idle', seconds_remaining: 0, duration_seconds: 0 })
  const [minutes, setMinutes] = useState(25)
  const [err, setErr] = useState<string | null>(null)
  const [sessions, setSessions] = useState(0)
  const wasRunning = useRef(false)

  const progress = useMemo(() => {
    if (status.duration_seconds <= 0) return 0
    return 1 - status.seconds_remaining / status.duration_seconds
  }, [status.duration_seconds, status.seconds_remaining])

  useEffect(() => {
    // Detect timer completion: was running, now idle with 0 remaining
    if (wasRunning.current && status.state === 'idle' && status.seconds_remaining === 0 && status.duration_seconds === 0) {
      setSessions((n) => n + 1)
      confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } })
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Webb', { body: 'Pomodoro complete!' })
      }
    }
    wasRunning.current = status.state === 'running'
  }, [status])

  useEffect(() => {
    let cancelled = false
    setErr(null)

    async function bootstrap() {
      try {
        const s = await apiGet<TimerStatus>('/api/timer/status')
        if (!cancelled) setStatus(s)
      } catch (e) {
        if (!cancelled) setErr(String(e))
      }
    }

    bootstrap()

    const ws = new WebSocket(apiWsUrl('/api/timer/ws'))
    ws.onmessage = (ev) => {
      try {
        const next = JSON.parse(ev.data) as TimerStatus
        if (!cancelled) setStatus(next)
      } catch { /* ignore */ }
    }

    const poll = window.setInterval(() => {
      apiGet<TimerStatus>('/api/timer/status')
        .then((s) => { if (!cancelled) setStatus(s) })
        .catch(() => {})
    }, 3000)

    return () => {
      cancelled = true
      window.clearInterval(poll)
      try { ws.close() } catch { /* ignore */ }
    }
  }, [])

  async function start() {
    setErr(null)
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
    const s = await apiSend<TimerStatus>('/api/timer/start', { method: 'POST', body: { duration_minutes: minutes } })
    setStatus(s)
  }
  async function pause() {
    setErr(null)
    const s = await apiSend<TimerStatus>('/api/timer/pause', { method: 'POST' })
    setStatus(s)
  }
  async function stop() {
    setErr(null)
    const s = await apiSend<TimerStatus>('/api/timer/stop', { method: 'POST' })
    setStatus(s)
  }

  const radius = 92
  const circumference = 2 * Math.PI * radius
  const dash = circumference * (1 - progress)

  return (
    <div className="enter-up">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Timer</h1>
        <div className="flex items-center gap-2">
          {[25, 50].map((m) => (
            <button
              key={m}
              onClick={() => setMinutes(m)}
              className={minutes === m ? 'btn-primary' : 'btn-ghost'}
              style={{ padding: '4px 12px', fontSize: '0.8125rem' }}
            >
              {m}m
            </button>
          ))}
          <input
            type="number"
            min={1}
            max={240}
            value={minutes}
            onChange={(e) => setMinutes(Number(e.target.value))}
            className="field-control w-20 px-3 py-1.5 text-sm"
          />
        </div>
      </div>

      <div className="card mt-8 px-4 py-8">
        <div className="relative mx-auto flex max-w-md items-center justify-center">
          <svg width="240" height="240" viewBox="0 0 240 240">
            <circle cx="120" cy="120" r={radius} stroke="var(--bg-elevated)" strokeWidth="14" fill="none" />
            <circle
              cx="120"
              cy="120"
              r={radius}
              stroke="var(--accent-color)"
              strokeWidth="14"
              fill="none"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dash}
              transform="rotate(-90 120 120)"
              style={{ transition: 'stroke-dashoffset 1s linear' }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="text-5xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              {formatSeconds(status.seconds_remaining)}
            </div>
            <div
              className="mt-2 rounded-full px-3 py-1 text-xs font-semibold tracking-wide"
              style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}
            >
              {status.state.toUpperCase()}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-8 flex flex-col items-center gap-4">
        <div className="flex gap-3">
          <button onClick={() => start().catch((e) => setErr(String(e)))} className="btn-cube px-5 py-2.5 text-sm">
            Start
          </button>
          <button onClick={() => pause().catch((e) => setErr(String(e)))} className="btn-ghost px-5 py-2.5 text-sm">
            Pause
          </button>
          <button onClick={() => stop().catch((e) => setErr(String(e)))} className="btn-ghost px-5 py-2.5 text-sm">
            Stop
          </button>
        </div>
        {sessions > 0 ? (
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Session {sessions} today
          </div>
        ) : null}
      </div>

      {err ? <div className="mt-4 text-center text-sm" style={{ color: 'var(--danger)' }}>{err}</div> : null}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/TimerPage.tsx
git commit -m "feat: restyle TimerPage, add completion confetti/notification and session counter"
```

---

## Task 7: Restyle RemindersPage

**Files:**
- Modify: `frontend/src/pages/RemindersPage.tsx`

- [ ] **Step 1: Rewrite RemindersPage**

Replace the entire content of `frontend/src/pages/RemindersPage.tsx` with:

```tsx
import { useEffect, useState } from 'react'
import { apiGet, apiSend } from '../lib/api'
import type { Reminder } from '../lib/types'

export function RemindersPage() {
  const [items, setItems] = useState<Reminder[]>([])
  const [message, setMessage] = useState('')
  const [time, setTime] = useState('')
  const [repeat, setRepeat] = useState<Reminder['repeat']>('none')
  const [err, setErr] = useState<string | null>(null)

  async function refresh() {
    setErr(null)
    const data = await apiGet<Reminder[]>('/api/reminders/')
    setItems(data)
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e)))
  }, [])

  async function add() {
    const m = message.trim()
    if (!m || !time) return
    setMessage('')
    setTime('')
    await apiSend<Reminder>('/api/reminders/', {
      method: 'POST',
      body: {
        message: m,
        trigger_time: new Date(time).toISOString(),
        repeat,
      },
    })
    await refresh()
  }

  async function remove(id: number) {
    await apiSend<{ ok: boolean }>(`/api/reminders/${id}`, { method: 'DELETE' })
    await refresh()
  }

  return (
    <div className="enter-up">
      <h1 className="text-2xl font-bold">Reminders</h1>

      <div className="card mt-5 p-4">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Reminder message..."
            className="field-control px-3 py-2 text-sm md:col-span-2"
          />
          <input
            type="datetime-local"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            className="field-control px-3 py-2 text-sm"
          />
          <select
            value={repeat}
            onChange={(e) => setRepeat(e.target.value as Reminder['repeat'])}
            className="field-control px-3 py-2 text-sm"
          >
            <option value="none">No repeat</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </div>
        <div className="mt-3 flex justify-end">
          <button
            onClick={() => add().catch((e) => setErr(String(e)))}
            className="btn-cube px-4 py-2 text-sm"
          >
            Add reminder
          </button>
        </div>
        {err ? <div className="mt-3 text-sm" style={{ color: 'var(--danger)' }}>{err}</div> : null}
      </div>

      <div className="mt-6 space-y-2">
        {items.length === 0 ? (
          <div className="text-sm" style={{ color: 'var(--text-muted)' }}>No reminders yet.</div>
        ) : (
          items.map((r) => (
            <div
              key={r.id}
              className="card-elevated flex items-center justify-between px-4 py-3"
              style={{ opacity: r.triggered ? 0.5 : 1 }}
            >
              <div>
                <div className="text-sm font-medium">{r.message}</div>
                <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>
                  {new Date(r.trigger_time).toLocaleString()} · {r.repeat}
                </div>
              </div>
              <button
                onClick={() => remove(r.id).catch((e) => setErr(String(e)))}
                className="btn-danger text-sm"
              >
                Delete
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/RemindersPage.tsx
git commit -m "retheme: RemindersPage with minimal dark styling"
```

---

## Task 8: Restyle SettingsPage with Grouped Sections

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Rewrite SettingsPage with sections and collapsible developer panel**

Replace the entire content of `frontend/src/pages/SettingsPage.tsx` with:

```tsx
import { useEffect, useState } from 'react'
import { apiGet, apiSend } from '../lib/api'
import type { WebbStatus } from '../lib/types'

const faces = ['IDLE', 'HAPPY', 'FOCUS', 'SLEEPY', 'REMINDER', 'LISTENING', 'SURPRISED'] as const

export function SettingsPage() {
  const [status, setStatus] = useState<WebbStatus | null>(null)
  const [face, setFace] = useState<(typeof faces)[number]>('IDLE')
  const [err, setErr] = useState<string | null>(null)
  const [devOpen, setDevOpen] = useState(false)
  const [idleDisabled, setIdleDisabled] = useState(localStorage.getItem('idleDisabled') === '1')
  const [voiceDisabled, setVoiceDisabled] = useState(localStorage.getItem('voiceDisabled') === '1')

  useEffect(() => {
    let cancelled = false
    async function refresh() {
      try {
        const s = await apiGet<WebbStatus>('/api/webb/status')
        if (!cancelled) setStatus(s)
      } catch (e) {
        if (!cancelled) setErr(String(e))
      }
    }
    refresh()
    const t = window.setInterval(refresh, 2500)
    return () => { cancelled = true; window.clearInterval(t) }
  }, [])

  async function testFace() {
    setErr(null)
    await apiSend<{ ok: boolean; face: string; error: string }>('/api/webb/face', {
      method: 'POST',
      body: { face },
    })
    const s = await apiGet<WebbStatus>('/api/webb/status')
    setStatus(s)
  }

  return (
    <div className="enter-up">
      <h1 className="text-2xl font-bold">Settings</h1>

      <div className="mt-6 space-y-4">
        {/* Webb Connection */}
        <div className="card p-4">
          <div className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>Webb Connection</div>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Status: </span>
              <span className="font-medium">{status?.connected ? 'Connected' : 'Disconnected'}</span>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Port: </span>
              <span className="font-medium">{status?.port ?? '—'}</span>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Baud: </span>
              <span className="font-medium">{status?.baud ?? '—'}</span>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Last face: </span>
              <span className="font-medium">{status?.last_face ?? '—'}</span>
            </div>
          </div>
          {status?.last_error ? (
            <div className="mt-2 text-sm" style={{ color: 'var(--danger)' }}>Error: {status.last_error}</div>
          ) : null}

          <div className="mt-4 flex items-center gap-2">
            <select
              value={face}
              onChange={(e) => setFace(e.target.value as any)}
              className="field-control px-3 py-2 text-sm"
            >
              {faces.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
            <button
              onClick={() => testFace().catch((e) => setErr(String(e)))}
              className="btn-primary text-sm"
            >
              Test Face
            </button>
          </div>
        </div>

        {/* Timer Defaults */}
        <div className="card p-4">
          <div className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>Timer</div>
          <div className="mt-3 flex items-center gap-3">
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Default duration:</span>
            <input
              type="number"
              min={1}
              max={240}
              defaultValue={Number(localStorage.getItem('timerDefault') ?? 25)}
              onChange={(e) => localStorage.setItem('timerDefault', e.target.value)}
              className="field-control w-20 px-3 py-1.5 text-sm"
            />
            <span className="text-sm" style={{ color: 'var(--text-muted)' }}>minutes</span>
          </div>
        </div>

        {/* Developer */}
        <div className="card p-4">
          <button
            onClick={() => setDevOpen(!devOpen)}
            className="flex w-full items-center justify-between text-sm font-semibold"
            style={{ color: 'var(--text-secondary)', background: 'transparent', border: 'none', padding: 0 }}
          >
            Developer
            <span style={{ color: 'var(--text-muted)' }}>{devOpen ? '▲' : '▼'}</span>
          </button>
          {devOpen ? (
            <div className="mt-3 space-y-3">
              <label className="flex items-center justify-between gap-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
                <span>Disable idle nudges (requires restart)</span>
                <input
                  type="checkbox"
                  checked={idleDisabled}
                  onChange={(e) => {
                    const v = e.target.checked
                    setIdleDisabled(v)
                    localStorage.setItem('idleDisabled', v ? '1' : '0')
                  }}
                />
              </label>
              <label className="flex items-center justify-between gap-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
                <span>Disable voice (use sample command)</span>
                <input
                  type="checkbox"
                  checked={voiceDisabled}
                  onChange={(e) => {
                    const v = e.target.checked
                    setVoiceDisabled(v)
                    localStorage.setItem('voiceDisabled', v ? '1' : '0')
                  }}
                />
              </label>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Set env vars IDLE_DISABLED=1 and/or VOICE_DISABLED=1 on the backend to fully apply.
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {err ? <div className="mt-4 text-sm" style={{ color: 'var(--danger)' }}>{err}</div> : null}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "retheme: SettingsPage with grouped sections and collapsible developer panel"
```

---

## Task 9: Restyle VoiceIndicator and NotificationCenter

**Files:**
- Modify: `frontend/src/components/VoiceIndicator.tsx`
- Modify: `frontend/src/components/NotificationCenter.tsx`
- Modify: `frontend/src/lib/notifications.ts`

- [ ] **Step 1: Update notification event types**

Replace the entire content of `frontend/src/lib/notifications.ts` with:

```ts
import { apiWsUrl } from './api'

export type NotificationEvent =
  | { type: 'idle_nudge'; text: string; created_at: string }
  | { type: 'reminder_triggered'; text: string; reminder_id: number; created_at: string }
  | { type: 'timer_complete'; text: string; created_at: string }
  | { type: string; [k: string]: any }

export function connectNotifications(onEvent: (ev: NotificationEvent) => void) {
  let ws: WebSocket | null = null
  let stopped = false
  let backoffMs = 500
  let reconnectTimer: number | null = null

  const url = apiWsUrl('/api/notifications/ws')

  function start() {
    if (stopped) return
    ws = new WebSocket(url)

    ws.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data))
      } catch {
        // ignore
      }
    }

    ws.onclose = () => {
      if (stopped) return
      reconnectTimer = window.setTimeout(() => {
        backoffMs = Math.min(backoffMs * 1.6, 8000)
        start()
      }, backoffMs)
    }
  }

  start()

  return () => {
    stopped = true
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    try { ws?.close() } catch { /* ignore */ }
  }
}
```

- [ ] **Step 2: Restyle NotificationCenter with new event handling**

Replace the entire content of `frontend/src/components/NotificationCenter.tsx` with:

```tsx
import { useEffect, useState } from 'react'
import { connectNotifications, type NotificationEvent } from '../lib/notifications'

type Toast = NotificationEvent & { id: string }

function prettyTime(iso: string) {
  try { return new Date(iso).toLocaleTimeString() } catch { return '' }
}

function toastTitle(t: Toast): string {
  if (t.type === 'idle_nudge') return 'Idle nudge'
  if (t.type === 'reminder_triggered') return 'Reminder'
  if (t.type === 'timer_complete') return 'Timer complete'
  return t.type
}

export function NotificationCenter() {
  const [toasts, setToasts] = useState<Toast[]>([])

  useEffect(() => {
    const disconnect = connectNotifications((ev) => {
      const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
      const toast: Toast = { ...(ev as any), id }
      setToasts((xs) => [toast, ...xs].slice(0, 5))

      window.setTimeout(() => {
        setToasts((xs) => xs.filter((t) => t.id !== id))
      }, 7000)
    })
    return () => disconnect()
  }, [])

  if (toasts.length === 0) return null

  return (
    <div className="fixed right-5 top-14 z-50 flex w-[360px] flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className="card enter-up p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {toastTitle(t)}
            </div>
            <button
              onClick={() => setToasts((xs) => xs.filter((x) => x.id !== t.id))}
              style={{ color: 'var(--text-muted)', background: 'transparent', border: 'none', padding: '0 4px' }}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
          {'text' in t && t.text ? (
            <div className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>{String(t.text)}</div>
          ) : null}
          {'created_at' in t && t.created_at ? (
            <div className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>{prettyTime(String(t.created_at))}</div>
          ) : null}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Restyle VoiceIndicator**

Replace the entire content of `frontend/src/components/VoiceIndicator.tsx` with:

```tsx
import { useEffect, useState } from 'react'
import { apiSend } from '../lib/api'

type VoiceSummary = { text: string; intent: any; result_summary: string; stt_error: string }
type Phase = 'idle' | 'listening' | 'processing'

export function VoiceIndicator() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [toast, setToast] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!toast && !error) return
    const t = window.setTimeout(() => { setToast(null); setError(null) }, 4500)
    return () => window.clearTimeout(t)
  }, [toast, error])

  async function runOnce() {
    setError(null)
    setToast(null)
    setPhase('listening')
    try {
      const summary = await apiSend<VoiceSummary>('/api/voice/once', { method: 'POST' })
      setPhase('processing')

      if (summary.stt_error) {
        setError(`Mic/STT error: ${summary.stt_error}`)
        setPhase('idle')
        return
      }

      const heard = summary.text ? `Heard: "${summary.text}"` : 'Heard nothing.'
      const did = summary.result_summary ? `\n${summary.result_summary}` : ''
      setToast(`${heard}${did}`)
      setPhase('idle')
    } catch (e) {
      setError(String(e))
      setPhase('idle')
    }
  }

  const ringColor =
    phase === 'listening' ? 'var(--accent-color)' : phase === 'processing' ? '#c4a882' : 'rgba(255,255,255,0.1)'

  return (
    <>
      <button
        onClick={() => runOnce()}
        className="fixed bottom-5 right-5 z-50 flex h-14 w-14 items-center justify-center rounded-full transition"
        style={{
          background: 'var(--bg-elevated)',
          border: `2px solid ${ringColor}`,
          color: 'var(--text-secondary)',
          animation: phase !== 'idle' ? 'pulse 1.5s ease-in-out infinite' : 'none',
        }}
        aria-label="Voice command"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" />
          <path d="M19 11a7 7 0 0 1-14 0" />
          <path d="M12 18v3" />
        </svg>
      </button>

      {toast || error ? (
        <div
          className="card fixed bottom-24 right-5 z-50 w-[340px] whitespace-pre-line p-3 text-sm"
        >
          <div className="flex items-start justify-between gap-3">
            <div style={{ color: error ? 'var(--danger)' : 'var(--text-primary)' }}>{error ?? toast}</div>
            <button
              onClick={() => { setToast(null); setError(null) }}
              style={{ color: 'var(--text-muted)', background: 'transparent', border: 'none' }}
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
          <div className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>
            {phase === 'listening' ? 'Listening...' : phase === 'processing' ? 'Processing...' : 'Tap mic to talk'}
          </div>
        </div>
      ) : null}
    </>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/notifications.ts frontend/src/components/NotificationCenter.tsx frontend/src/components/VoiceIndicator.tsx
git commit -m "retheme: VoiceIndicator, NotificationCenter, add reminder/timer event types"
```

---

## Task 10: Backend — Reminder Auto-Trigger Scheduler

**Files:**
- Create: `backend/reminder_scheduler.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create reminder scheduler**

Create `backend/reminder_scheduler.py` with:

```python
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select

from .database import SessionLocal
from .models import Reminder
from .notifications_hub import hub
from .serial_manager import get_serial_manager


async def reminder_check_loop() -> None:
    """Background task: every 30s, trigger due reminders."""
    while True:
        await asyncio.sleep(30)
        try:
            _check_and_trigger()
        except Exception as exc:
            print(f"[reminder_scheduler] error: {exc}")


def _check_and_trigger() -> None:
    db = SessionLocal()
    try:
        now = datetime.utcnow().isoformat()
        stmt = select(Reminder).where(
            Reminder.triggered == False,  # noqa: E712
            Reminder.trigger_time <= now,
        )
        due = list(db.scalars(stmt).all())

        for reminder in due:
            reminder.triggered = True

            hub.publish_threadsafe({
                "type": "reminder_triggered",
                "text": reminder.message,
                "reminder_id": reminder.id,
                "created_at": datetime.utcnow().isoformat(),
            })

            try:
                get_serial_manager().send_face("REMINDER")
            except Exception:
                pass

            # Handle repeating reminders
            if reminder.repeat == "daily":
                _create_next(db, reminder, timedelta(days=1))
            elif reminder.repeat == "weekly":
                _create_next(db, reminder, timedelta(weeks=1))

        db.commit()
    finally:
        db.close()


def _create_next(db, original: Reminder, delta: timedelta) -> None:
    try:
        next_time = datetime.fromisoformat(original.trigger_time) + delta
    except ValueError:
        return
    new_reminder = Reminder(
        message=original.message,
        trigger_time=next_time.isoformat(),
        repeat=original.repeat,
    )
    db.add(new_reminder)
```

- [ ] **Step 2: Wire scheduler into main.py startup and shutdown**

In `backend/main.py`, add the import at the top with the other imports:

```python
from .reminder_scheduler import reminder_check_loop
```

Inside the `_startup` function, after `idle_manager.start()`, add:

```python
        app.state.reminder_task = asyncio.create_task(reminder_check_loop())
```

Inside the `_shutdown` function, before `idle_manager.stop()`, add:

```python
        reminder_task = getattr(app.state, "reminder_task", None)
        if reminder_task is not None:
            reminder_task.cancel()
            try:
                await reminder_task
            except asyncio.CancelledError:
                pass
```

- [ ] **Step 3: Commit**

```bash
git add backend/reminder_scheduler.py backend/main.py
git commit -m "feat: add background reminder auto-trigger scheduler"
```

---

## Task 11: Backend — Timer Completion Event

**Files:**
- Modify: `backend/routes/timer.py`

- [ ] **Step 1: Add timer completion event to tick loop**

In `backend/routes/timer.py`, add this import at the top:

```python
from ..notifications_hub import hub
```

In the `_tick_loop` function, find the block where `_timer.seconds_remaining <= 0` (inside the `async with _timer_lock:` block). Replace:

```python
            if _timer.seconds_remaining <= 0:
                _timer.state = "idle"
                _timer.duration_seconds = 0
                _timer.last_tick_monotonic = 0.0
                try:
                    get_serial_manager().send_face("IDLE")
                except Exception:
                    pass
                status = _current_status()
```

with:

```python
            if _timer.seconds_remaining <= 0:
                _timer.state = "idle"
                _timer.duration_seconds = 0
                _timer.last_tick_monotonic = 0.0
                try:
                    get_serial_manager().send_face("HAPPY")
                except Exception:
                    pass
                status = _current_status()
                await hub.publish({
                    "type": "timer_complete",
                    "text": "Pomodoro complete!",
                    "created_at": __import__("datetime").datetime.utcnow().isoformat(),
                })
```

- [ ] **Step 2: Commit**

```bash
git add backend/routes/timer.py
git commit -m "feat: publish timer_complete event and HAPPY face on countdown end"
```

---

## Task 12: Dashboard Page + Face Context + Final Wiring

**Files:**
- Create: `frontend/src/context/WebbFaceContext.tsx`
- Create: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create WebbFaceContext**

Create `frontend/src/context/WebbFaceContext.tsx` with:

```tsx
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

type Face = 'IDLE' | 'HAPPY' | 'FOCUS' | 'SLEEPY' | 'REMINDER' | 'LISTENING' | 'SURPRISED'

type FaceContextValue = {
  face: Face
  setFace: (face: Face, durationMs?: number) => void
}

const Ctx = createContext<FaceContextValue>({ face: 'IDLE', setFace: () => {} })

export function WebbFaceProvider({ children }: { children: ReactNode }) {
  const [face, setFaceState] = useState<Face>('IDLE')
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const setFace = useCallback((next: Face, durationMs?: number) => {
    if (timeout.current) clearTimeout(timeout.current)
    setFaceState(next)
    if (durationMs) {
      timeout.current = setTimeout(() => setFaceState('IDLE'), durationMs)
    }
  }, [])

  useEffect(() => {
    return () => { if (timeout.current) clearTimeout(timeout.current) }
  }, [])

  return <Ctx.Provider value={{ face, setFace }}>{children}</Ctx.Provider>
}

export function useWebbFace() {
  return useContext(Ctx)
}
```

- [ ] **Step 2: Create DashboardPage**

Create `frontend/src/pages/DashboardPage.tsx` with:

```tsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet } from '../lib/api'
import type { Task, TimerStatus, Reminder } from '../lib/types'
import { WebbPreview } from '../components/WebbPreview'

export function DashboardPage() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [timer, setTimer] = useState<TimerStatus>({ state: 'idle', seconds_remaining: 0, duration_seconds: 0 })
  const [reminders, setReminders] = useState<Reminder[]>([])

  useEffect(() => {
    apiGet<Task[]>('/api/tasks/').then(setTasks).catch(() => {})
    apiGet<TimerStatus>('/api/timer/status').then(setTimer).catch(() => {})
    apiGet<Reminder[]>('/api/reminders/').then(setReminders).catch(() => {})
  }, [])

  const activeTasks = tasks.filter((t) => !t.completed).length
  const timerText = timer.state === 'running'
    ? `${Math.floor(timer.seconds_remaining / 60)}m remaining`
    : timer.state === 'paused' ? 'Paused' : 'Idle'
  const nextReminder = reminders
    .filter((r) => !r.triggered)
    .sort((a, b) => a.trigger_time.localeCompare(b.trigger_time))[0]
  const nextReminderText = nextReminder
    ? new Date(nextReminder.trigger_time).toLocaleString()
    : 'None set'

  const face = timer.state === 'running' ? 'FOCUS' : 'IDLE'
  const statusLine = timer.state === 'running'
    ? `Focusing... ${Math.floor(timer.seconds_remaining / 60)}:${String(timer.seconds_remaining % 60).padStart(2, '0')} left`
    : activeTasks > 0
      ? `${activeTasks} task${activeTasks === 1 ? '' : 's'} to go`
      : 'All clear. Ready when you are.'

  return (
    <div className="enter-up flex flex-col items-center">
      <div className="mt-8">
        <WebbPreview face={face as any} large />
      </div>

      <div className="mt-4 text-sm" style={{ color: 'var(--text-muted)' }}>
        {statusLine}
      </div>

      <div className="mt-8 grid w-full max-w-lg grid-cols-3 gap-3">
        <div className="card p-4 text-center">
          <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{activeTasks}</div>
          <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Active tasks</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-sm font-semibold" style={{ color: timer.state === 'running' ? 'var(--accent-color)' : 'var(--text-primary)' }}>
            {timerText}
          </div>
          <div className="mt-1 text-xs" style={{ color: 'var(--text-muted)' }}>Timer</div>
        </div>
        <div className="card p-4 text-center">
          <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            {nextReminder ? 'Upcoming' : '—'}
          </div>
          <div className="mt-1 text-xs truncate" style={{ color: 'var(--text-muted)' }}>{nextReminderText}</div>
        </div>
      </div>

      <div className="mt-8 flex gap-3">
        <button onClick={() => navigate('/tasks')} className="btn-cube px-5 py-2.5 text-sm">
          Add task
        </button>
        <button onClick={() => navigate('/timer')} className="btn-ghost px-5 py-2.5 text-sm">
          Start timer
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Wire DashboardPage and FaceContext into App.tsx**

Replace the entire content of `frontend/src/App.tsx` with:

```tsx
import { Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { DashboardPage } from './pages/DashboardPage'
import { RemindersPage } from './pages/RemindersPage'
import { SettingsPage } from './pages/SettingsPage'
import { TasksPage } from './pages/TasksPage'
import { TimerPage } from './pages/TimerPage'
import { VoiceIndicator } from './components/VoiceIndicator'
import { NotificationCenter } from './components/NotificationCenter'
import { DesktopTopBar } from './components/DesktopTopBar'
import { WebbFaceProvider } from './context/WebbFaceContext'

export default function App() {
  return (
    <WebbFaceProvider>
      <div className="relative min-h-screen" style={{ background: 'var(--bg-base)', color: 'var(--text-primary)' }}>
        <div className="relative flex min-h-screen w-full flex-col">
          <DesktopTopBar />
          <div className="flex min-h-0 flex-1 flex-col md:flex-row">
            <Sidebar />
            <main className="flex-1 px-4 py-4 md:px-6 md:py-6">
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/tasks" element={<TasksPage />} />
                <Route path="/timer" element={<TimerPage />} />
                <Route path="/reminders" element={<RemindersPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </main>
          </div>
        </div>
        <VoiceIndicator />
        <NotificationCenter />
      </div>
    </WebbFaceProvider>
  )
}
```

- [ ] **Step 4: Add Home nav item to Sidebar**

In `frontend/src/components/Sidebar.tsx`, add a Home entry at the beginning of the `navItems` array:

```tsx
  {
    to: '/',
    label: 'Home',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        <polyline points="9 22 9 12 15 12 15 22" />
      </svg>
    ),
  },
```

Also change the Home NavLink to use `end` prop so it only activates on exact `/` match. Update the `NavLink` component for the Home item:

In the `navItems.map` callback, add `end` to the NavLink when `item.to === '/'`:

```tsx
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
```

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd F:/Webb1/frontend && npx tsc --noEmit`

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/context/WebbFaceContext.tsx frontend/src/pages/DashboardPage.tsx frontend/src/App.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat: add Dashboard page, WebbFaceContext, Home nav item"
```

---

## Task 13: Final Verification

- [ ] **Step 1: Run TypeScript check**

Run: `cd F:/Webb1/frontend && npx tsc --noEmit`

Expected: Clean — no errors.

- [ ] **Step 2: Run Vite dev build**

Run: `cd F:/Webb1/frontend && npx vite build 2>&1 | tail -10`

Expected: Build succeeds.

- [ ] **Step 3: Verify backend starts**

Run: `cd F:/Webb1 && timeout 5 python -m uvicorn backend.main:app --port 8099 2>&1 || true`

Expected: Server starts without import errors.

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: resolve any build/type issues from redesign"
```

Only run this step if previous steps required fixes.
