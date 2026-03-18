import { useEffect, useState } from 'react'
import { apiGet, apiSend } from '../lib/api'
import type { WebbStatus } from '../lib/types'

const faces = ['IDLE', 'HAPPY', 'FOCUS', 'SLEEPY', 'REMINDER', 'LISTENING', 'SURPRISED'] as const

export function SettingsPage() {
  const [status, setStatus] = useState<WebbStatus | null>(null)
  const [face, setFace] = useState<(typeof faces)[number]>('IDLE')
  const [err, setErr] = useState<string | null>(null)
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
    return () => {
      cancelled = true
      window.clearInterval(t)
    }
  }, [])

  async function testFace() {
    setErr(null)
    await apiSend<{ ok: string; face: string }>('/api/webb/face', { method: 'POST', body: { face } })
    const s = await apiGet<WebbStatus>('/api/webb/status')
    setStatus(s)
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Settings</h1>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="text-sm font-semibold text-gray-900">Serial status</div>
          <div className="mt-3 space-y-1 text-sm text-gray-700">
            <div>
              Connected: <span className="font-medium">{status?.connected ? 'Yes' : 'No'}</span>
            </div>
            <div>
              Port: <span className="font-medium">{status?.port ?? '—'}</span>
            </div>
            <div>
              Baud: <span className="font-medium">{status?.baud ?? '—'}</span>
            </div>
            <div>
              Last face: <span className="font-medium">{status?.last_face ?? '—'}</span>
            </div>
            {status?.last_error ? <div className="text-rose-700">Error: {status.last_error}</div> : null}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="text-sm font-semibold text-gray-900">Test face</div>
          <div className="mt-3 flex items-center gap-2">
            <select
              value={face}
              onChange={(e) => setFace(e.target.value as any)}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm"
            >
              {faces.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
            <button
              onClick={() => testFace().catch((e) => setErr(String(e)))}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Send
            </button>
          </div>
          <div className="mt-4 space-y-3">
            <div className="text-sm font-semibold text-gray-900">Developer toggles</div>
            <label className="flex items-center justify-between gap-3 text-sm text-gray-700">
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
            <label className="flex items-center justify-between gap-3 text-sm text-gray-700">
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
            <div className="text-xs text-gray-500">
              For now these toggles are stored locally. Set env vars `IDLE_DISABLED=1` and/or `VOICE_DISABLED=1` on the
              backend to fully apply.
            </div>
          </div>
        </div>
      </div>

      {err ? <div className="mt-4 text-sm text-rose-700">{err}</div> : null}
    </div>
  )
}

