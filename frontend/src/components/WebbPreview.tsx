import { useEffect, useState } from 'react'

type Face = 'IDLE' | 'HAPPY' | 'FOCUS' | 'SLEEPY' | 'REMINDER' | 'LISTENING' | 'SURPRISED' | 'THINKING' | 'SPEAKING'

function Eyes({ mood, blinking }: { mood: Face; blinking: boolean }) {
  if (blinking) {
    return (
      <>
        <path d="M14 18 L26 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M38 18 L50 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'FOCUS') {
    return (
      <>
        <path d="M14 18 L26 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M38 16 L50 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'SLEEPY') {
    return (
      <>
        <path d="M14 18 Q20 16 26 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M38 18 Q44 16 50 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'HAPPY') {
    return (
      <>
        <path d="M14 16 Q20 22 26 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M38 16 Q44 22 50 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'SURPRISED' || mood === 'LISTENING') {
    return (
      <>
        <circle cx="20" cy="18" r="3.2" stroke="currentColor" strokeWidth="2" fill="none" />
        <circle cx="44" cy="18" r="3.2" stroke="currentColor" strokeWidth="2" fill="none" />
      </>
    )
  }
  if (mood === 'THINKING') {
    return (
      <>
        <circle cx="22" cy="16" r="2.5" stroke="currentColor" strokeWidth="2" fill="none" />
        <circle cx="42" cy="16" r="2.5" stroke="currentColor" strokeWidth="2" fill="none" />
      </>
    )
  }
  return (
    <>
      <circle cx="20" cy="18" r="2.5" stroke="currentColor" strokeWidth="2" fill="none" />
      <circle cx="44" cy="18" r="2.5" stroke="currentColor" strokeWidth="2" fill="none" />
    </>
  )
}

function Mouth({ mood }: { mood: Face }) {
  if (mood === 'HAPPY') {
    return <path d="M24 34 Q32 40 40 34" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
  }
  if (mood === 'SURPRISED') {
    return <circle cx="32" cy="35" r="3.6" stroke="currentColor" strokeWidth="2" fill="none" />
  }
  if (mood === 'SLEEPY') {
    return <path d="M26 36 Q32 34 38 36" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
  }
  if (mood === 'REMINDER') {
    return <path d="M24 36 Q32 32 40 36" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
  }
  if (mood === 'SPEAKING') {
    return <ellipse cx="32" cy="36" rx="5" ry="3" stroke="currentColor" strokeWidth="2" fill="none" />
  }
  return <path d="M26 36 L38 36" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
}

export function WebbPreview({ face = 'IDLE', large = false }: { face?: Face; large?: boolean }) {
  const [blinking, setBlinking] = useState(false)

  useEffect(() => {
    if (face !== 'IDLE') return
    const interval = setInterval(() => {
      setBlinking(true)
      setTimeout(() => setBlinking(false), 200)
    }, 4000 + Math.random() * 2000)
    return () => clearInterval(interval)
  }, [face])

  const width = large ? 160 : 100
  const height = large ? 120 : 80

  return (
    <div
      className="rounded-xl p-4 flex flex-col items-center"
      style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}
    >
      <svg
        width={width}
        height={height}
        viewBox="0 0 64 52"
        aria-hidden="true"
        style={{ color: 'var(--text-secondary)', transition: 'color 300ms ease' }}
      >
        <rect x="1" y="1" width="62" height="50" rx="12" stroke="currentColor" strokeOpacity="0.3" fill="rgba(0,0,0,0.2)" />
        <g style={{ transition: 'opacity 200ms ease' }}>
          <Eyes mood={face} blinking={blinking} />
          <Mouth mood={face} />
          {face === 'LISTENING' ? (
            <path
              d="M8 30 C6 33 6 37 8 40"
              stroke="var(--accent-color)"
              strokeWidth="2"
              strokeLinecap="round"
              fill="none"
            />
          ) : null}
        </g>
      </svg>
      <div className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>{face}</div>
    </div>
  )
}
