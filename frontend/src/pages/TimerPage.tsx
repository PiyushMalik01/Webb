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
