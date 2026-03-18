import { useEffect, useMemo, useState } from 'react'
import { apiGet, apiSend } from '../lib/api'
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

  const progress = useMemo(() => {
    if (status.duration_seconds <= 0) return 0
    return 1 - status.seconds_remaining / status.duration_seconds
  }, [status.duration_seconds, status.seconds_remaining])

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

    const ws = new WebSocket('ws://127.0.0.1:8000/api/timer/ws')
    ws.onmessage = (ev) => {
      try {
        const next = JSON.parse(ev.data) as TimerStatus
        if (!cancelled) setStatus(next)
      } catch {
        // ignore
      }
    }
    ws.onerror = () => {
      // fallback polling
    }

    const poll = window.setInterval(() => {
      apiGet<TimerStatus>('/api/timer/status')
        .then((s) => {
          if (!cancelled) setStatus(s)
        })
        .catch(() => {})
    }, 3000)

    return () => {
      cancelled = true
      window.clearInterval(poll)
      try {
        ws.close()
      } catch {
        // ignore
      }
    }
  }, [])

  async function start() {
    setErr(null)
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
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Timer</h1>
        <div className="flex items-center gap-2">
          {[25, 50].map((m) => (
            <button
              key={m}
              onClick={() => setMinutes(m)}
              className={[
                'rounded-lg px-3 py-1.5 text-sm font-medium transition',
                minutes === m ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ].join(' ')}
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
            className="w-20 rounded-lg border border-gray-200 px-3 py-1.5 text-sm"
          />
        </div>
      </div>

      <div className="mt-8 flex items-center justify-center">
        <div className="relative">
          <svg width="240" height="240" viewBox="0 0 240 240">
            <circle cx="120" cy="120" r={radius} className="stroke-gray-100" strokeWidth="14" fill="none" />
            <circle
              cx="120"
              cy="120"
              r={radius}
              className="stroke-indigo-600"
              strokeWidth="14"
              fill="none"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dash}
              transform="rotate(-90 120 120)"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="text-5xl font-semibold tracking-tight">{formatSeconds(status.seconds_remaining)}</div>
            <div className="mt-2 text-sm text-gray-500">{status.state.toUpperCase()}</div>
          </div>
        </div>
      </div>

      <div className="mt-8 flex justify-center gap-3">
        <button
          onClick={() => start().catch((e) => setErr(String(e)))}
          className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Start
        </button>
        <button
          onClick={() => pause().catch((e) => setErr(String(e)))}
          className="rounded-lg bg-gray-100 px-5 py-2.5 text-sm font-medium text-gray-900 hover:bg-gray-200"
        >
          Pause
        </button>
        <button
          onClick={() => stop().catch((e) => setErr(String(e)))}
          className="rounded-lg bg-gray-100 px-5 py-2.5 text-sm font-medium text-gray-900 hover:bg-gray-200"
        >
          Stop
        </button>
      </div>

      {err ? <div className="mt-4 text-center text-sm text-rose-700">{err}</div> : null}
    </div>
  )
}

