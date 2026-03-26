import { useEffect, useState } from 'react'
import { apiSend } from '../lib/api'

type VoiceSummary = { text: string; intent: any; result_summary: string; stt_error: string }
type Phase = 'idle' | 'listening' | 'processing'

export function VoiceIndicator() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [toast, setToast] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!toast && !error) return
    const t = window.setTimeout(() => { setToast(null); setError(null) }, 4500)
    return () => window.clearTimeout(t)
  }, [toast, error])

  async function runOnce() {
    setError(null)
    setToast(null)
    setPhase('listening')
    try {
      const summary = await apiSend<VoiceSummary>('/api/voice/once', { method: 'POST' })
      setPhase('processing')

      if (summary.stt_error) {
        setError(`Mic/STT error: ${summary.stt_error}`)
        setPhase('idle')
        return
      }

      const heard = summary.text ? `Heard: "${summary.text}"` : 'Heard nothing.'
      const did = summary.result_summary ? `\n${summary.result_summary}` : ''
      setToast(`${heard}${did}`)
      setPhase('idle')
    } catch (e) {
      setError(String(e))
      setPhase('idle')
    }
  }

  const ringColor =
    phase === 'listening' ? 'var(--accent-color)' : phase === 'processing' ? '#c4a882' : 'rgba(255,255,255,0.1)'

  return (
    <>
      <button
        onClick={() => runOnce()}
        className="fixed bottom-5 right-5 z-50 flex h-14 w-14 items-center justify-center rounded-full transition"
        style={{
          background: 'var(--bg-elevated)',
          border: `2px solid ${ringColor}`,
          color: 'var(--text-secondary)',
          animation: phase !== 'idle' ? 'pulse 1.5s ease-in-out infinite' : 'none',
        }}
        aria-label="Voice command"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z" />
          <path d="M19 11a7 7 0 0 1-14 0" />
          <path d="M12 18v3" />
        </svg>
      </button>

      {toast || error ? (
        <div className="card fixed bottom-24 right-5 z-50 w-[340px] whitespace-pre-line p-3 text-sm">
          <div className="flex items-start justify-between gap-3">
            <div style={{ color: error ? 'var(--danger)' : 'var(--text-primary)' }}>{error ?? toast}</div>
            <button
              onClick={() => { setToast(null); setError(null) }}
              style={{ color: 'var(--text-muted)', background: 'transparent', border: 'none' }}
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
          <div className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>
            {phase === 'listening' ? 'Listening...' : phase === 'processing' ? 'Processing...' : 'Tap mic to talk'}
          </div>
        </div>
      ) : null}
    </>
  )
}
