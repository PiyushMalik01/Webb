export type NotificationEvent =
  | { type: 'idle_nudge'; text: string; created_at: string }
  | { type: string; [k: string]: any }

export function connectNotifications(onEvent: (ev: NotificationEvent) => void) {
  let ws: WebSocket | null = null
  let stopped = false
  let backoffMs = 500

  const url = 'ws://127.0.0.1:8000/api/notifications/ws'

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
      const t = window.setTimeout(() => {
        backoffMs = Math.min(backoffMs * 1.6, 8000)
        start()
      }, backoffMs)
      return () => window.clearTimeout(t)
    }
  }

  start()

  return () => {
    stopped = true
    try {
      ws?.close()
    } catch {
      // ignore
    }
  }
}

