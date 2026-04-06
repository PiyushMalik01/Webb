import { useEffect, useRef, useCallback } from 'react'

// ── Mood type ──────────────────────────────────────────────────────────
type Mood = 'NEUTRAL' | 'HAPPY' | 'ANGRY' | 'SLEEPY' | 'SURPRISED' | 'SAD' | 'LOVE' | 'SUS'

const FACE_TO_MOOD: Record<string, Mood> = {
  IDLE: 'NEUTRAL',
  HAPPY: 'HAPPY',
  FOCUS: 'ANGRY',
  SLEEPY: 'SLEEPY',
  LISTENING: 'SURPRISED',
  SURPRISED: 'SURPRISED',
  THINKING: 'SUS',
  SPEAKING: 'HAPPY',
  REMINDER: 'SURPRISED',
  SAD: 'SAD',
  LOVE: 'LOVE',
  SUS: 'SUS',
  ANGRY: 'ANGRY',
  NEUTRAL: 'NEUTRAL',
}

// ── Mood parameters ────────────────────────────────────────────────────
interface MoodParams {
  leW: number; leH: number; leR: number
  reW: number; reH: number; reR: number
  skewL: number; skewR: number
  eyeYOff: number
  eyeGap: number
  mouthW: number; mouthCurve: number; mouthThick: number; mouthY: number
  browW: number; browAngle: number; browY: number
  eyeColor: string; browColor: string
  blush: boolean; sparkles: boolean; vein: boolean; tears: boolean; zzz: boolean
  oMouth: boolean; happyEyes: boolean; heartEyes: boolean
  mSpd: number
}

function mp(p: Partial<MoodParams> & { eyeW?: number; eyeH?: number; eyeR?: number; skew?: number }): MoodParams {
  const base: MoodParams = {
    leW: 52, leH: 48, leR: 16, reW: 52, reH: 48, reR: 16,
    skewL: 0, skewR: 0, eyeYOff: 0, eyeGap: 50,
    mouthW: 22, mouthCurve: 2.5, mouthThick: 2.5, mouthY: 40,
    browW: 28, browAngle: 0, browY: -10,
    eyeColor: '#ffffff', browColor: '#b4b4b4',
    blush: false, sparkles: false, vein: false, tears: false, zzz: false,
    oMouth: false, happyEyes: false, heartEyes: false,
    mSpd: 0.12,
  }
  const r = { ...base, ...p }
  if (p.eyeW !== undefined) { r.leW = p.eyeW; r.reW = p.eyeW }
  if (p.eyeH !== undefined) { r.leH = p.eyeH; r.reH = p.eyeH }
  if (p.eyeR !== undefined) { r.leR = p.eyeR; r.reR = p.eyeR }
  if (p.skew !== undefined) { r.skewL = p.skew; r.skewR = p.skew }
  return r
}

const MOODS: Record<Mood, MoodParams> = {
  NEUTRAL: mp({}),
  HAPPY: mp({
    eyeW: 56, eyeH: 40, eyeR: 20,
    mouthW: 32, mouthCurve: 7, mouthThick: 3, mouthY: 36,
    browW: 32, browAngle: -4, browY: -14,
    blush: true, sparkles: true,
    eyeColor: '#fff0c8', browColor: '#ffdc8c',
    happyEyes: true, mSpd: 0.15,
  }),
  ANGRY: mp({
    eyeW: 54, eyeH: 30, eyeR: 8, skew: 14,
    eyeGap: 36,
    mouthW: 18, mouthCurve: -4, mouthThick: 3, mouthY: 34,
    browW: 42, browAngle: 14, browY: -12,
    vein: true,
    eyeColor: '#ffb4b4', browColor: '#ff503c',
    mSpd: 0.2,
  }),
  SLEEPY: mp({
    eyeW: 54, eyeH: 10, eyeR: 5, eyeYOff: 5,
    mouthW: 16, mouthCurve: 0, mouthThick: 2, mouthY: 30,
    browW: 30, browAngle: -3, browY: -6,
    zzz: true,
    eyeColor: '#c8d2ff', browColor: '#8c96c8',
    mSpd: 0.05,
  }),
  SURPRISED: mp({
    eyeW: 56, eyeH: 58, eyeR: 26, eyeYOff: -4,
    eyeGap: 56,
    mouthW: 18, mouthCurve: 0, mouthThick: 3, mouthY: 42,
    browW: 38, browAngle: -8, browY: -18,
    oMouth: true,
    eyeColor: '#dcffff', browColor: '#b4ffff',
    mSpd: 0.35,
  }),
  SAD: mp({
    eyeW: 48, eyeH: 38, eyeR: 14, skew: -10, eyeYOff: 5,
    mouthW: 20, mouthCurve: -5, mouthThick: 2.5, mouthY: 36,
    browW: 34, browAngle: -12, browY: -10,
    tears: true,
    eyeColor: '#b4c8ff', browColor: '#648cff',
    mSpd: 0.08,
  }),
  LOVE: mp({
    eyeW: 50, eyeH: 48, eyeR: 22,
    mouthW: 28, mouthCurve: 6, mouthThick: 2.5, mouthY: 38,
    browW: 30, browAngle: -5, browY: -14,
    blush: true, sparkles: true,
    eyeColor: '#ffc8dc', browColor: '#ff96b4',
    heartEyes: true, mSpd: 0.12,
  }),
  SUS: mp({
    leW: 48, leH: 20, leR: 8, reW: 54, reH: 50, reR: 18,
    skewL: 8, skewR: -4,
    mouthW: 14, mouthCurve: -1, mouthThick: 2, mouthY: 36,
    browW: 34, browAngle: 8, browY: -10,
    eyeColor: '#ffffc8', browColor: '#ffc83c',
    mSpd: 0.1,
  }),
}

// ── Lerp helpers ───────────────────────────────────────────────────────
function lerp(a: number, b: number, t: number): number { return a + (b - a) * t }
function lerpColor(a: string, b: string, t: number): string {
  const pa = parseColor(a), pb = parseColor(b)
  const r = Math.round(lerp(pa[0], pb[0], t))
  const g = Math.round(lerp(pa[1], pb[1], t))
  const bl = Math.round(lerp(pa[2], pb[2], t))
  return `rgb(${r},${g},${bl})`
}
function parseColor(c: string): [number, number, number] {
  if (c.startsWith('#')) {
    const hex = c.slice(1)
    return [parseInt(hex.slice(0, 2), 16), parseInt(hex.slice(2, 4), 16), parseInt(hex.slice(4, 6), 16)]
  }
  const m = c.match(/\d+/g)
  if (m) return [+m[0], +m[1], +m[2]]
  return [255, 255, 255]
}

// ── Canvas drawing helpers ─────────────────────────────────────────────
function fillRoundedRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  r = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
  ctx.fill()
}

function drawHeart(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number, color: string) {
  const r = size * 0.3
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(cx - r * 0.9, cy - r * 0.4, r, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(cx + r * 0.9, cy - r * 0.4, r, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.moveTo(cx - r * 1.8, cy)
  ctx.lineTo(cx, cy + size * 0.65)
  ctx.lineTo(cx + r * 1.8, cy)
  ctx.closePath()
  ctx.fill()
}

function drawStar(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number, angle: number) {
  ctx.strokeStyle = '#ffff64'
  ctx.lineWidth = 1.5
  for (let i = 0; i < 4; i++) {
    const a = angle + (i * Math.PI) / 4
    const dx = Math.cos(a) * size
    const dy = Math.sin(a) * size
    ctx.beginPath()
    ctx.moveTo(cx - dx, cy - dy)
    ctx.lineTo(cx + dx, cy + dy)
    ctx.stroke()
  }
}

function drawTeardrop(ctx: CanvasRenderingContext2D, x: number, y: number, size: number) {
  ctx.fillStyle = '#64b4ff'
  ctx.beginPath()
  ctx.arc(x, y + size * 0.4, size * 0.4, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.moveTo(x, y - size * 0.3)
  ctx.lineTo(x - size * 0.35, y + size * 0.3)
  ctx.lineTo(x + size * 0.35, y + size * 0.3)
  ctx.closePath()
  ctx.fill()
}

// ── Animated state ─────────────────────────────────────────────────────
interface AnimState {
  // Current lerped params (numeric)
  leW: number; leH: number; leR: number
  reW: number; reH: number; reR: number
  skewL: number; skewR: number
  eyeYOff: number; eyeGap: number
  mouthW: number; mouthCurve: number; mouthThick: number; mouthY: number
  browW: number; browAngle: number; browY: number
  // Colors
  eyeColor: string; browColor: string
  // Blink
  blinkTimer: number; blinkNext: number; blinkPhase: number
  // Look
  lookX: number; lookY: number; lookTargetX: number; lookTargetY: number; lookTimer: number; lookNext: number
  // Tears
  tearY: number
  // Zzz
  zY: number
  // Sparkle angle
  sparkleAngle: number
  // Mood speed
  mSpd: number
}

function createAnimState(): AnimState {
  const n = MOODS.NEUTRAL
  return {
    leW: n.leW, leH: n.leH, leR: n.leR,
    reW: n.reW, reH: n.reH, reR: n.reR,
    skewL: n.skewL, skewR: n.skewR,
    eyeYOff: n.eyeYOff, eyeGap: n.eyeGap,
    mouthW: n.mouthW, mouthCurve: n.mouthCurve, mouthThick: n.mouthThick, mouthY: n.mouthY,
    browW: n.browW, browAngle: n.browAngle, browY: n.browY,
    eyeColor: n.eyeColor, browColor: n.browColor,
    blinkTimer: 0, blinkNext: 3 + Math.random() * 3, blinkPhase: 0,
    lookX: 0, lookY: 0, lookTargetX: 0, lookTargetY: 0, lookTimer: 0, lookNext: 0.6 + Math.random() * 1.6,
    tearY: 0, zY: 0, sparkleAngle: 0, mSpd: n.mSpd,
  }
}

const LERP_FIELDS: (keyof AnimState & keyof MoodParams)[] = [
  'leW', 'leH', 'leR', 'reW', 'reH', 'reR',
  'skewL', 'skewR', 'eyeYOff', 'eyeGap',
  'mouthW', 'mouthCurve', 'mouthThick', 'mouthY',
  'browW', 'browAngle', 'browY', 'mSpd',
]

// ── Component ──────────────────────────────────────────────────────────
export function WebbPreview({ face = 'IDLE', large = false }: { face?: string; large?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const stateRef = useRef<AnimState>(createAnimState())
  const moodRef = useRef<Mood>('NEUTRAL')
  const rafRef = useRef<number>(0)
  const lastTimeRef = useRef<number>(0)

  const resolvedMood = FACE_TO_MOOD[face] ?? 'NEUTRAL'
  moodRef.current = resolvedMood

  const W = 320
  const H = 120
  const scale = large ? 2 : 1

  const render = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const now = performance.now() / 1000
    const dt = Math.min(now - (lastTimeRef.current || now), 0.1)
    lastTimeRef.current = now

    const s = stateRef.current
    const target = MOODS[moodRef.current]
    const spd = s.mSpd

    // Lerp numeric fields
    for (const f of LERP_FIELDS) {
      ;(s as any)[f] = lerp((s as any)[f], (target as any)[f], 1 - Math.pow(1 - spd, dt * 60))
    }
    // Lerp colors
    const colorT = 1 - Math.pow(1 - spd, dt * 60)
    s.eyeColor = lerpColor(s.eyeColor, target.eyeColor, colorT)
    s.browColor = lerpColor(s.browColor, target.browColor, colorT)

    // Blink logic
    s.blinkTimer += dt
    if (s.blinkPhase === 0 && s.blinkTimer >= s.blinkNext) {
      s.blinkPhase = 1
      s.blinkTimer = 0
    }
    if (s.blinkPhase === 1 && s.blinkTimer >= 0.15) {
      s.blinkPhase = 0
      s.blinkTimer = 0
      s.blinkNext = 3 + Math.random() * 3
    }

    // Look logic
    s.lookTimer += dt
    if (s.lookTimer >= s.lookNext) {
      s.lookTargetX = (Math.random() - 0.5) * 12
      s.lookTargetY = (Math.random() - 0.5) * 6
      s.lookTimer = 0
      s.lookNext = 0.6 + Math.random() * 1.6
    }
    s.lookX = lerp(s.lookX, s.lookTargetX, 1 - Math.pow(0.85, dt * 60))
    s.lookY = lerp(s.lookY, s.lookTargetY, 1 - Math.pow(0.85, dt * 60))

    // Animated effects
    if (target.tears) s.tearY = (s.tearY + dt * 30) % 25
    if (target.zzz) s.zY = (s.zY + dt * 12) % 20
    s.sparkleAngle += dt * 2

    // ── Draw ───────────────────────────────────────────────────────
    ctx.clearRect(0, 0, W, H)
    ctx.fillStyle = '#000000'
    ctx.fillRect(0, 0, W, H)

    const cx = 160
    const cy = 42 + s.eyeYOff
    const gap = s.eyeGap
    const lCx = cx - gap / 2 - s.leW / 2 + s.lookX
    const rCx = cx + gap / 2 + s.reW / 2 + s.lookX
    const yCom = cy + s.lookY

    const blinking = s.blinkPhase === 1

    // ── Eyes ───────────────────────────────────────────────────────
    if (blinking) {
      // Thin lines for blink
      ctx.fillStyle = s.eyeColor
      fillRoundedRect(ctx, lCx - s.leW / 2, yCom - 1.5, s.leW, 3, 1.5)
      fillRoundedRect(ctx, rCx - s.reW / 2, yCom - 1.5, s.reW, 3, 1.5)
    } else if (target.happyEyes) {
      // ^_^ arcs: draw circle, then mask the top half with black
      const drawHappyEye = (ecx: number, eW: number, eH: number) => {
        const r = Math.min(eW, eH) / 2
        ctx.fillStyle = s.eyeColor
        ctx.beginPath()
        ctx.arc(ecx, yCom, r, 0, Math.PI * 2)
        ctx.fill()
        // Mask top half
        ctx.fillStyle = '#000000'
        ctx.fillRect(ecx - r - 2, yCom - r - 2, r * 2 + 4, r + 2)
      }
      drawHappyEye(lCx, s.leW, s.leH)
      drawHappyEye(rCx, s.reW, s.reH)
    } else if (target.heartEyes) {
      drawHeart(ctx, lCx, yCom, Math.min(s.leW, s.leH) * 0.8, s.eyeColor)
      drawHeart(ctx, rCx, yCom, Math.min(s.reW, s.reH) * 0.8, s.eyeColor)
    } else {
      // Normal rounded-rect eyes with skew
      const drawEye = (ecx: number, eW: number, eH: number, eR: number, skew: number) => {
        const ex = ecx - eW / 2
        const ey = yCom - eH / 2
        ctx.fillStyle = s.eyeColor
        fillRoundedRect(ctx, ex, ey, eW, eH, eR)
        // Skew: clip top-right (positive skew) or top-left (negative skew) corner with triangle
        if (Math.abs(skew) > 0.5) {
          ctx.fillStyle = '#000000'
          if (skew > 0) {
            // Clip top-right corner
            ctx.beginPath()
            ctx.moveTo(ecx + eW / 2 - skew * 2, ey)
            ctx.lineTo(ecx + eW / 2 + 1, ey)
            ctx.lineTo(ecx + eW / 2 + 1, ey + Math.abs(skew) * 1.2)
            ctx.closePath()
            ctx.fill()
          } else {
            // Clip top-left corner
            ctx.beginPath()
            ctx.moveTo(ecx - eW / 2 + Math.abs(skew) * 2, ey)
            ctx.lineTo(ecx - eW / 2 - 1, ey)
            ctx.lineTo(ecx - eW / 2 - 1, ey + Math.abs(skew) * 1.2)
            ctx.closePath()
            ctx.fill()
          }
        }
      }
      drawEye(lCx, s.leW, s.leH, s.leR, s.skewL)
      drawEye(rCx, s.reW, s.reH, s.reR, s.skewR)
    }

    // ── Brows ──────────────────────────────────────────────────────
    const drawBrow = (ecx: number, browAngle: number) => {
      ctx.save()
      ctx.translate(ecx, yCom + s.browY)
      ctx.rotate((browAngle * Math.PI) / 180)
      ctx.strokeStyle = s.browColor
      ctx.lineWidth = 2.5
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.moveTo(-s.browW / 2, 0)
      ctx.lineTo(s.browW / 2, 0)
      ctx.stroke()
      ctx.restore()
    }
    drawBrow(lCx, s.browAngle)
    drawBrow(rCx, -s.browAngle)

    // ── Mouth ──────────────────────────────────────────────────────
    const mCx = cx + s.lookX
    const mCy = yCom + s.mouthY
    if (target.oMouth) {
      // O-mouth circle
      ctx.strokeStyle = s.eyeColor
      ctx.lineWidth = s.mouthThick
      ctx.beginPath()
      ctx.arc(mCx, mCy, 10, 0, Math.PI * 2)
      ctx.stroke()
    } else {
      // Arc mouth
      ctx.strokeStyle = s.eyeColor
      ctx.lineWidth = s.mouthThick
      ctx.lineCap = 'round'
      ctx.beginPath()
      if (Math.abs(s.mouthCurve) < 0.5) {
        // Flat line
        ctx.moveTo(mCx - s.mouthW / 2, mCy)
        ctx.lineTo(mCx + s.mouthW / 2, mCy)
      } else {
        ctx.moveTo(mCx - s.mouthW / 2, mCy)
        ctx.quadraticCurveTo(mCx, mCy + s.mouthCurve * 2, mCx + s.mouthW / 2, mCy)
      }
      ctx.stroke()
    }

    // ── Blush ──────────────────────────────────────────────────────
    if (target.blush) {
      ctx.fillStyle = 'rgba(255,100,120,0.35)'
      ctx.beginPath()
      ctx.ellipse(lCx - 4, yCom + s.leH / 2 + 4, 12, 6, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.ellipse(rCx + 4, yCom + s.reH / 2 + 4, 12, 6, 0, 0, Math.PI * 2)
      ctx.fill()
    }

    // ── Vein ───────────────────────────────────────────────────────
    if (target.vein) {
      const vx = rCx + s.reW / 2 + 8
      const vy = yCom - s.reH / 2 - 8
      ctx.strokeStyle = '#ff3c28'
      ctx.lineWidth = 2
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.moveTo(vx - 5, vy - 5)
      ctx.lineTo(vx + 5, vy + 5)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(vx + 5, vy - 5)
      ctx.lineTo(vx - 5, vy + 5)
      ctx.stroke()
    }

    // ── Sparkles ───────────────────────────────────────────────────
    if (target.sparkles) {
      const sa = s.sparkleAngle
      drawStar(ctx, lCx - s.leW / 2 - 14, yCom - s.leH / 2 - 6, 4, sa)
      drawStar(ctx, rCx + s.reW / 2 + 14, yCom - s.reH / 2 - 6, 4, sa + 0.5)
      drawStar(ctx, lCx + s.leW / 2 + 10, yCom - s.leH / 2 + 2, 3, sa + 1.0)
      drawStar(ctx, rCx - s.reW / 2 - 10, yCom - s.reH / 2 + 2, 3, sa + 1.5)
    }

    // ── Tears ──────────────────────────────────────────────────────
    if (target.tears) {
      const tAlpha = Math.min(1, (25 - s.tearY) / 8)
      ctx.globalAlpha = tAlpha
      drawTeardrop(ctx, lCx + s.leW / 2 - 4, yCom + s.leH / 2 + s.tearY, 6)
      drawTeardrop(ctx, rCx - s.reW / 2 + 4, yCom + s.reH / 2 + s.tearY, 6)
      ctx.globalAlpha = 1
    }

    // ── Zzz ────────────────────────────────────────────────────────
    if (target.zzz) {
      ctx.fillStyle = '#96b4ff'
      ctx.font = 'bold 14px monospace'
      ctx.textAlign = 'center'
      const baseX = rCx + s.reW / 2 + 18
      const baseY = yCom - 12
      const offY = s.zY
      ctx.globalAlpha = Math.max(0, 1 - offY / 20)
      ctx.fillText('Z', baseX, baseY - offY)
      ctx.font = 'bold 11px monospace'
      ctx.fillText('z', baseX + 10, baseY - offY * 0.6 + 4)
      ctx.font = 'bold 8px monospace'
      ctx.fillText('z', baseX + 16, baseY - offY * 0.3 + 8)
      ctx.globalAlpha = 1
    }

    rafRef.current = requestAnimationFrame(render)
  }, [])

  useEffect(() => {
    lastTimeRef.current = performance.now() / 1000
    rafRef.current = requestAnimationFrame(render)
    return () => { cancelAnimationFrame(rafRef.current) }
  }, [render])

  return (
    <div
      className="rounded-xl p-4 flex flex-col items-center"
      style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)' }}
    >
      <canvas
        ref={canvasRef}
        width={W}
        height={H}
        style={{
          width: W * scale,
          height: H * scale,
          imageRendering: 'pixelated',
          borderRadius: 8,
        }}
        aria-hidden="true"
      />
      <div className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>{face}</div>
    </div>
  )
}
