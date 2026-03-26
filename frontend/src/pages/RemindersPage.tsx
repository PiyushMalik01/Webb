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
