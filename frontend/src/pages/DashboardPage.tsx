import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiGet } from '../lib/api'
import type { Task, TimerStatus, Reminder, VoiceStatus } from '../lib/types'
import { WebbPreview } from '../components/WebbPreview'

export function DashboardPage() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [timer, setTimer] = useState<TimerStatus>({ state: 'idle', seconds_remaining: 0, duration_seconds: 0 })
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [voiceState, setVoiceState] = useState<string>('idle')

  useEffect(() => {
    apiGet<Task[]>('/api/tasks/').then(setTasks).catch(() => {})
    apiGet<TimerStatus>('/api/timer/status').then(setTimer).catch(() => {})
    apiGet<Reminder[]>('/api/reminders/').then(setReminders).catch(() => {})
  }, [])

  useEffect(() => {
    const poll = setInterval(() => {
      apiGet<VoiceStatus>('/api/voice/status').then(s => setVoiceState(s.state)).catch(() => {})
    }, 1000)
    return () => clearInterval(poll)
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

      <div className="mt-2 text-xs font-medium" style={{
        color: voiceState !== 'idle' ? 'var(--accent-color)' : 'var(--text-muted)'
      }}>
        {voiceState === 'idle' ? 'Say "Hey Webb" or tap mic' :
         voiceState === 'listening' ? 'Listening...' :
         voiceState === 'processing' ? 'Thinking...' :
         voiceState === 'speaking' ? 'Speaking...' :
         voiceState === 'executing' ? 'On it...' : voiceState}
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
