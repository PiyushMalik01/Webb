import { NavLink } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import { apiGet } from '../lib/api'
import type { WebbStatus } from '../lib/types'
import { WebbPreview } from './WebbPreview'

function cn(...xs: Array<string | false | undefined | null>) {
  return xs.filter(Boolean).join(' ')
}

const navItems = [
  {
    to: '/',
    label: 'Home',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        <polyline points="9 22 9 12 15 12 15 22" />
      </svg>
    ),
  },
  {
    to: '/tasks',
    label: 'Tasks',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
    ),
  },
  {
    to: '/timer',
    label: 'Timer',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
  },
  {
    to: '/reminders',
    label: 'Reminders',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
    ),
  },
  {
    to: '/settings',
    label: 'Settings',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    ),
  },
]

export function Sidebar() {
  const [status, setStatus] = useState<WebbStatus | null>(null)
  const [backendOk, setBackendOk] = useState(false)

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
    return () => { cancelled = true; window.clearInterval(t) }
  }, [])

  const face = (status?.last_face as any) ?? 'IDLE'
  const dotColor = backendOk ? (status?.connected ? 'var(--success)' : 'var(--danger)') : 'var(--text-muted)'
  const connectionLabel = backendOk
    ? status?.connected ? 'Bot connected' : 'Bot offline'
    : 'Backend down'

  return (
    <aside
      className="enter-up w-full shrink-0 flex flex-col md:w-60"
      style={{ background: 'var(--bg-surface)', borderRight: '1px solid var(--border)' }}
    >
      <div className="p-4">
        <WebbPreview face={face} />
      </div>

      <nav className="flex-1 px-2 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
              )
            }
            style={({ isActive }) => ({
              background: isActive ? 'var(--bg-elevated)' : 'transparent',
              color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
              borderLeft: isActive ? '3px solid var(--accent-color)' : '3px solid transparent',
            })}
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-3" style={{ borderTop: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: dotColor }}
          />
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {connectionLabel}
          </span>
        </div>
      </div>
    </aside>
  )
}
