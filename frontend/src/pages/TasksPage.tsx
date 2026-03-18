import { useEffect, useMemo, useState } from 'react'
import confetti from 'canvas-confetti'
import { apiGet, apiSend } from '../lib/api'
import type { Task } from '../lib/types'

type Priority = 'all' | 'high' | 'medium' | 'low'

function badge(priority: Task['priority']) {
  const base = 'rounded-full px-2 py-0.5 text-xs font-medium'
  if (priority === 'high') return `${base} bg-rose-50 text-rose-700`
  if (priority === 'low') return `${base} bg-gray-100 text-gray-700`
  return `${base} bg-indigo-50 text-indigo-700`
}

export function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<Task['priority']>('medium')
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    await apiSend<Task>('/api/tasks/', { method: 'POST', body: { title: t, priority } })
    await refresh()
  }

  async function completeTask(id: number) {
    await apiSend<Task>(`/api/tasks/${id}/complete`, { method: 'POST' })
    confetti({ particleCount: 80, spread: 65, origin: { y: 0.75 } })
    await refresh()
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Tasks</h1>
        <div className="flex items-center gap-2">
          {(['all', 'high', 'medium', 'low'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setFilter(p)}
              className={[
                'rounded-lg px-3 py-1.5 text-sm font-medium transition',
                filter === p ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
              ].join(' ')}
            >
              {p === 'all' ? 'All' : p[0].toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 rounded-xl border border-gray-200 bg-white p-4">
        <div className="flex gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Add a task…"
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-indigo-500"
            onKeyDown={(e) => {
              if (e.key === 'Enter') addTask().catch((x) => setErr(String(x)))
            }}
          />
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as Task['priority'])}
            className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm"
          >
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <button
            onClick={() => addTask().catch((x) => setErr(String(x)))}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Add
          </button>
        </div>
        {err ? <div className="mt-3 text-sm text-rose-700">{err}</div> : null}
      </div>

      <div className="mt-6 space-y-6">
        <section>
          <div className="text-sm font-semibold text-gray-900">Active</div>
          <div className="mt-3 space-y-2">
            {grouped.active.length === 0 ? (
              <div className="text-sm text-gray-500">No tasks yet.</div>
            ) : (
              grouped.active.map((t) => (
                <div
                  key={t.id}
                  className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => completeTask(t.id).catch((x) => setErr(String(x)))}
                      className="h-5 w-5 rounded border border-gray-300 hover:border-gray-900"
                      aria-label="Complete task"
                    />
                    <div>
                      <div className="text-sm font-medium text-gray-900">{t.title}</div>
                      <div className="mt-1 flex items-center gap-2">
                        <span className={badge(t.priority)}>{t.priority}</span>
                        {t.due_date ? <span className="text-xs text-gray-500">{t.due_date}</span> : null}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section>
          <div className="text-sm font-semibold text-gray-900">Completed</div>
          <div className="mt-3 space-y-2">
            {grouped.completed.length === 0 ? (
              <div className="text-sm text-gray-500">Nothing completed yet.</div>
            ) : (
              grouped.completed.map((t) => (
                <div
                  key={t.id}
                  className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3 opacity-70"
                >
                  <div className="flex items-center gap-3">
                    <div className="h-5 w-5 rounded bg-gray-900" aria-hidden="true" />
                    <div className="text-sm text-gray-700 line-through">{t.title}</div>
                  </div>
                  <span className={badge(t.priority)}>{t.priority}</span>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  )
}

