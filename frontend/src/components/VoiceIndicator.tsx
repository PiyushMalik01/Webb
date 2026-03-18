import { useEffect, useState } from 'react'
import { apiSend } from '../lib/api'

type VoiceSummary = {
  text: string
  intent: any
  result_summary: string
  stt_error: string
}

type Phase = 'idle' | 'listening' | 'processing'

export function VoiceIndicator() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [toast, setToast] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!toast && !error) return
    const t = window.setTimeout(() => {
      setToast(null)
      setError(null)
    }, 4500)
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

  const ring =
    phase === 'idle'
      ? 'ring-gray-200'
      : phase === 'listening'
        ? 'ring-indigo-400 animate-pulse'
        : 'ring-indigo-600 animate-pulse'

  return (
    <>
      <button
        onClick={() => runOnce()}
        className={[
          'fixed bottom-5 right-5 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-gray-900 text-white',
          'ring-4',
          ring,
          'hover:bg-gray-800 active:scale-[0.98] transition',
        ].join(' ')}
        aria-label="Voice command"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Z"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M19 11a7 7 0 0 1-14 0"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M12 18v3"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {toast || error ? (
        <div className="fixed bottom-20 right-5 z-50 w-[320px] whitespace-pre-line rounded-xl border border-gray-200 bg-white p-3 text-sm text-gray-900 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div className={error ? 'text-rose-700' : ''}>{error ?? toast}</div>
            <button
              onClick={() => {
                setToast(null)
                setError(null)
              }}
              className="text-gray-400 hover:text-gray-700"
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
          <div className="mt-2 text-xs text-gray-500">
            {phase === 'listening' ? 'Listening…' : phase === 'processing' ? 'Processing…' : 'Tap mic to talk'}
          </div>
        </div>
      ) : null}
    </>
  )
}

