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

export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking' | 'executing'

export type VoiceResult = {
  text?: string
  speak: string
  actions: Array<{ name: string; params: Record<string, any> }>
  face: string
  action_results: Array<{ name: string; result: string }>
  stt_error?: string
}

export type DisplayState = {
  mode: 'FACE' | 'DASHBOARD' | 'NOTIFY'
  face: string
  text: string[]
  animation: string | null
}

export type DisplayMode = 'FACE' | 'DASHBOARD' | 'NOTIFY'

export type VoiceStatus = {
  state: VoiceState
}

