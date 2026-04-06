import { useEffect, useState } from 'react'
import { apiGet, apiSend } from '../lib/api'
import type { VoiceResult } from '../lib/types'

type Phase = 'idle' | 'listening' | 'processing' | 'speaking' | 'executing'

export function VoiceIndicator() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [toast, setToast] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Poll voice state
  useEffect(() => {
    const poll = setInterval(() => {
      apiGet<{ state: string }>('/api/voice/status')
        .then(d => setPhase(d.state as Phase))
        .catch(() => {})
    }, 500)
    return () => clearInterval(poll)
  }, [])

  useEffect(() => {
    if (!toast && !error) return
    const t = window.setTimeout(() => { setToast(null); setError(null) }, 5000)
    return () => window.clearTimeout(t)
  }, [toast, error])

  async function runOnce() {
    if (phase !== 'idle') {
      // Interrupt if already active
      await apiSend('/api/voice/interrupt', { method: 'POST' })
      return
    }
    setError(null)
    setToast(null)
    try {
      const result = await apiSend<VoiceResult>('/api/voice/once', { method: 'POST' })

      if (result.stt_error) {
        setError(`Mic error: ${result.stt_error}`)
        return
      }

      const heard = result.text ? `"${result.text}"` : ''
      const response = result.speak || ''
      const parts = [heard, response].filter(Boolean)
      setToast(parts.join('\n') || 'Done')
    } catch (e) {
      setError(String(e))
    }
  }

  const ringColor =
    phase === 'listening' ? 'var(--accent-color)' :
    phase === 'processing' ? '#c4a882' :
    phase === 'speaking' ? 'var(--success)' :
    phase === 'executing' ? 'var(--accent-color)' :
    'rgba(255,255,255,0.1)'

  const isActive = phase !== 'idle'

  return (
    <>
      <button
        onClick={() => runOnce()}
        className="fixed bottom-5 right-5 z-50 flex h-14 w-14 items-center justify-center rounded-full transition"
        style={{
          background: isActive ? ringColor : 'var(--bg-elevated)',
          border: `2px solid ${ringColor}`,
          color: isActive ? 'white' : 'var(--text-secondary)',
          animation: isActive ? 'pulse 1.5s ease-in-out infinite' : 'none',
        }}
        aria-label={isActive ? 'Interrupt Webb' : 'Voice command'}
      >
        {isActive ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" />
            <path d="M19 11a7 7 0 0 1-14 0" />
            <path d="M12 18v3" />
          </svg>
        )}
      </button>

      {isActive && phase !== 'idle' ? (
        <div className="fixed bottom-20 right-5 z-50 text-xs font-medium" style={{ color: 'var(--accent-color)' }}>
          {phase === 'listening' ? 'Listening...' :
           phase === 'processing' ? 'Thinking...' :
           phase === 'speaking' ? 'Speaking...' :
           phase === 'executing' ? 'Executing...' : ''}
        </div>
      ) : null}

      {toast || error ? (
        <div className="card fixed bottom-24 right-5 z-50 w-[340px] whitespace-pre-line p-3 text-sm">
          <div className="flex items-start justify-between gap-3">
            <div style={{ color: error ? 'var(--danger)' : 'var(--text-primary)' }}>{error ?? toast}</div>
            <button
              onClick={() => { setToast(null); setError(null) }}
              style={{ color: 'var(--text-muted)', background: 'transparent', border: 'none' }}
              aria-label="Dismiss"
            >
              x
            </button>
          </div>
        </div>
      ) : null}
    </>
  )
}
