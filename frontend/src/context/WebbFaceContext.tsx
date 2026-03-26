import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

type Face = 'IDLE' | 'HAPPY' | 'FOCUS' | 'SLEEPY' | 'REMINDER' | 'LISTENING' | 'SURPRISED'

type FaceContextValue = {
  face: Face
  setFace: (face: Face, durationMs?: number) => void
}

const Ctx = createContext<FaceContextValue>({ face: 'IDLE', setFace: () => {} })

export function WebbFaceProvider({ children }: { children: ReactNode }) {
  const [face, setFaceState] = useState<Face>('IDLE')
  const timeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const setFace = useCallback((next: Face, durationMs?: number) => {
    if (timeout.current) clearTimeout(timeout.current)
    setFaceState(next)
    if (durationMs) {
      timeout.current = setTimeout(() => setFaceState('IDLE'), durationMs)
    }
  }, [])

  useEffect(() => {
    return () => { if (timeout.current) clearTimeout(timeout.current) }
  }, [])

  return <Ctx.Provider value={{ face, setFace }}>{children}</Ctx.Provider>
}

export function useWebbFace() {
  return useContext(Ctx)
}
