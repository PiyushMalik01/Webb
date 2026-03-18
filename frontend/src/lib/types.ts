export type Task = {
  id: number
  title: string
  priority: 'low' | 'medium' | 'high'
  due_date: string | null
  completed: boolean
  created_at: string
}

export type Reminder = {
  id: number
  message: string
  trigger_time: string
  repeat: 'none' | 'daily' | 'weekly'
  triggered: boolean
  created_at: string
}

export type WebbStatus = {
  connected: boolean
  port: string | null
  baud: number
  last_face: string | null
  last_error: string | null
}

export type TimerStatus = {
  state: 'idle' | 'running' | 'paused'
  seconds_remaining: number
  duration_seconds: number
}

