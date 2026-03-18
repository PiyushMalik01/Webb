import { NavLink } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import { apiGet } from '../lib/api'
import type { WebbStatus } from '../lib/types'
import { WebbPreview } from './WebbPreview'

function classNames(...xs: Array<string | false | undefined | null>) {
  return xs.filter(Boolean).join(' ')
}

export function Sidebar() {
  const [status, setStatus] = useState<WebbStatus | null>(null)
  const [backendOk, setBackendOk] = useState<boolean>(false)

  useEffect(() => {
    let cancelled = false

    async function refresh() {
      try {
        await apiGet<{ status: string }>('/health')
        if (!cancelled) setBackendOk(true)
      } catch {
        if (!cancelled) setBackendOk(false)
      }

      try {
        const s = await apiGet<WebbStatus>('/api/webb/status')
        if (!cancelled) setStatus(s)
      } catch {
        if (!cancelled) setStatus(null)
      }
    }

    refresh()
    const t = window.setInterval(refresh, 2500)
    return () => {
      cancelled = true
      window.clearInterval(t)
    }
  }, [])

  const nav = useMemo(
    () => [
      { to: '/tasks', label: 'Tasks' },
      { to: '/timer', label: 'Timer' },
      { to: '/reminders', label: 'Reminders' },
      { to: '/settings', label: 'Settings' },
    ],
    [],
  )

  const dot = backendOk ? (status?.connected ? 'bg-emerald-500' : 'bg-rose-500') : 'bg-gray-300'
  const face = (status?.last_face as any) ?? 'IDLE'

  return (
    <aside className="w-64 shrink-0 border-r border-gray-200 bg-gray-50 px-4 py-6">
      <WebbPreview face={face} />

      <nav className="mt-6 space-y-1">
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              classNames(
                'block rounded-lg px-3 py-2 text-sm font-medium transition',
                isActive ? 'bg-white text-gray-900' : 'text-gray-600 hover:bg-white hover:text-gray-900',
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-8 rounded-lg border border-gray-200 bg-white p-3">
        <div className="flex items-center gap-2">
          <span className={classNames('h-2.5 w-2.5 rounded-full', dot)} />
          <div className="text-xs font-medium text-gray-900">Connection</div>
        </div>
        <div className="mt-2 space-y-1 text-xs text-gray-600">
          <div>
            Backend: <span className="font-medium text-gray-900">{backendOk ? 'OK' : 'Down'}</span>
          </div>
          <div>
            Serial:{' '}
            <span className="font-medium text-gray-900">
              {backendOk ? (status?.connected ? 'Connected' : 'Disconnected') : '—'}
            </span>
          </div>
          <div className="truncate">Port: {status?.port ?? '—'}</div>
        </div>
      </div>
    </aside>
  )
}

