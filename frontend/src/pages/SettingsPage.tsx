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
