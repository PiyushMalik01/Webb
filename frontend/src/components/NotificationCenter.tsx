import { useEffect, useState } from 'react'
import { connectNotifications, type NotificationEvent } from '../lib/notifications'

type Toast = NotificationEvent & { id: string }

function prettyTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString()
  } catch {
    return ''
  }
}

export function NotificationCenter() {
  const [toasts, setToasts] = useState<Toast[]>([])

  useEffect(() => {
    const disconnect = connectNotifications((ev) => {
      const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
      const toast: Toast = { ...(ev as any), id }
      setToasts((xs) => [toast, ...xs].slice(0, 5))

      window.setTimeout(() => {
        setToasts((xs) => xs.filter((t) => t.id !== id))
      }, 7000)
    })
    return () => disconnect()
  }, [])

  if (toasts.length === 0) return null

  return (
    <div className="fixed right-5 top-5 z-50 flex w-[360px] flex-col gap-2">
      {toasts.map((t) => (
        <div key={t.id} className="rounded-xl border border-gray-200 bg-white p-3 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div className="text-sm font-semibold text-gray-900">
              {t.type === 'idle_nudge' ? 'Idle nudge' : t.type}
            </div>
            <button
              onClick={() => setToasts((xs) => xs.filter((x) => x.id !== t.id))}
              className="text-gray-400 hover:text-gray-700"
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
          {'text' in t && t.text ? <div className="mt-1 text-sm text-gray-700">{String(t.text)}</div> : null}
          {'created_at' in t && t.created_at ? (
            <div className="mt-2 text-xs text-gray-500">{prettyTime(String(t.created_at))}</div>
          ) : null}
        </div>
      ))}
    </div>
  )
}

