type Face =
  | 'IDLE'
  | 'HAPPY'
  | 'FOCUS'
  | 'SLEEPY'
  | 'REMINDER'
  | 'LISTENING'
  | 'SURPRISED'

function Eyes({ mood }: { mood: Face }) {
  const common = 'stroke-gray-900'
  if (mood === 'FOCUS') {
    return (
      <>
        <path d="M14 18 L26 16" className={common} strokeWidth="2" strokeLinecap="round" />
        <path d="M38 16 L50 18" className={common} strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'SLEEPY') {
    return (
      <>
        <path d="M14 18 Q20 16 26 18" className={common} strokeWidth="2" strokeLinecap="round" />
        <path d="M38 18 Q44 16 50 18" className={common} strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'HAPPY') {
    return (
      <>
        <path d="M14 16 Q20 22 26 16" className={common} strokeWidth="2" strokeLinecap="round" />
        <path d="M38 16 Q44 22 50 16" className={common} strokeWidth="2" strokeLinecap="round" />
      </>
    )
  }
  if (mood === 'SURPRISED' || mood === 'LISTENING') {
    return (
      <>
        <circle cx="20" cy="18" r="3.2" className={common} strokeWidth="2" fill="none" />
        <circle cx="44" cy="18" r="3.2" className={common} strokeWidth="2" fill="none" />
      </>
    )
  }
  return (
    <>
      <circle cx="20" cy="18" r="2.5" className={common} strokeWidth="2" fill="none" />
      <circle cx="44" cy="18" r="2.5" className={common} strokeWidth="2" fill="none" />
    </>
  )
}

function Mouth({ mood }: { mood: Face }) {
  const common = 'stroke-gray-900'
  if (mood === 'HAPPY') {
    return (
      <path d="M24 34 Q32 40 40 34" className={common} strokeWidth="2" strokeLinecap="round" />
    )
  }
  if (mood === 'SURPRISED') {
    return <circle cx="32" cy="35" r="3.6" className={common} strokeWidth="2" fill="none" />
  }
  if (mood === 'SLEEPY') {
    return (
      <path d="M26 36 Q32 34 38 36" className={common} strokeWidth="2" strokeLinecap="round" />
    )
  }
  if (mood === 'REMINDER') {
    return (
      <path d="M24 36 Q32 32 40 36" className={common} strokeWidth="2" strokeLinecap="round" />
    )
  }
  return <path d="M26 36 L38 36" className={common} strokeWidth="2" strokeLinecap="round" />
}

export function WebbPreview({ face = 'IDLE' }: { face?: Face }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-gray-900">Webb</div>
        <div className="text-xs text-gray-500">{face}</div>
      </div>
      <div className="mt-3 flex justify-center">
        <svg width="80" height="64" viewBox="0 0 64 52" aria-hidden="true">
          <rect x="1" y="1" width="62" height="50" rx="12" className="stroke-gray-200" fill="white" />
          <g>
            <Eyes mood={face} />
            <Mouth mood={face} />
            {face === 'LISTENING' ? (
              <path
                d="M8 30 C6 33 6 37 8 40"
                className="stroke-indigo-500"
                strokeWidth="2"
                strokeLinecap="round"
                fill="none"
              />
            ) : null}
          </g>
        </svg>
      </div>
    </div>
  )
}

