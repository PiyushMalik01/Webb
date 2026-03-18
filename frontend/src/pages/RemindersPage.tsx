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
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Reminders</h1>
      </div>

      <div className="mt-5 rounded-xl border border-gray-200 bg-white p-4">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Reminder message…"
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-indigo-500 md:col-span-2"
          />
          <input
            type="datetime-local"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
          />
          <select
            value={repeat}
            onChange={(e) => setRepeat(e.target.value as Reminder['repeat'])}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm"
          >
            <option value="none">No repeat</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </div>
        <div className="mt-3 flex justify-end">
          <button
            onClick={() => add().catch((e) => setErr(String(e)))}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Add reminder
          </button>
        </div>
        {err ? <div className="mt-3 text-sm text-rose-700">{err}</div> : null}
      </div>

      <div className="mt-6 space-y-2">
        {items.length === 0 ? (
          <div className="text-sm text-gray-500">No reminders yet.</div>
        ) : (
          items.map((r) => (
            <div
              key={r.id}
              className={[
                'flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3',
                r.triggered ? 'opacity-60' : '',
              ].join(' ')}
            >
              <div>
                <div className="text-sm font-medium text-gray-900">{r.message}</div>
                <div className="mt-1 text-xs text-gray-500">
                  {new Date(r.trigger_time).toLocaleString()} · {r.repeat}
                </div>
              </div>
              <button
                onClick={() => remove(r.id).catch((e) => setErr(String(e)))}
                className="rounded-lg bg-gray-100 px-3 py-2 text-sm font-medium text-gray-900 hover:bg-gray-200"
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

