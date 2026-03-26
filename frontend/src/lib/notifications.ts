import { apiWsUrl } from './api'

export type NotificationEvent =
  | { type: 'idle_nudge'; text: string; created_at: string }
  | { type: 'reminder_triggered'; text: string; reminder_id: number; created_at: string }
  | { type: 'timer_complete'; text: string; created_at: string }
  | { type: string; [k: string]: any }

export function connectNotifications(onEvent: (ev: NotificationEvent) => void) {
  let ws: WebSocket | null = null
  let stopped = false
  let backoffMs = 500
  let reconnectTimer: number | null = null

  const url = apiWsUrl('/api/notifications/ws')

  function start() {
    if (stopped) return
    ws = new WebSocket(url)

    ws.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data))
      } catch {
        // ignore
      }
    }

    ws.onclose = () => {
      if (stopped) return
      reconnectTimer = window.setTimeout(() => {
        backoffMs = Math.min(backoffMs * 1.6, 8000)
        start()
      }, backoffMs)
    }
  }

  start()

  return () => {
    stopped = true
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    try { ws?.close() } catch { /* ignore */ }
  }
}
