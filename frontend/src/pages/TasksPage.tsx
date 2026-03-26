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
