import { useCallback, useEffect, useRef, useState } from 'react'

export const SPEEDS = [1, 4, 10] as const

/** Show time: play, pause, seek, speed. Time stops at the end of the show. */
export function usePlayback(duration: number, initial = 0) {
  const [t, setT] = useState(() => Math.min(Math.max(initial, 0), duration))
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<number>(1)
  const last = useRef(0)

  useEffect(() => {
    if (!playing) return
    last.current = performance.now()
    let raf = 0
    const tick = (now: number) => {
      const dt = ((now - last.current) / 1000) * speed
      last.current = now
      setT((prev) => {
        const next = prev + dt
        if (next >= duration) {
          setPlaying(false)
          return duration
        }
        return next
      })
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, speed, duration])

  const seek = useCallback((value: number) => setT(Math.min(Math.max(value, 0), duration)), [duration])
  const toggle = useCallback(() => {
    if (!playing && t >= duration) setT(0)
    setPlaying((p) => !p)
  }, [playing, t, duration])
  const stop = useCallback(() => setPlaying(false), [])

  return { t, playing, speed, setSpeed, seek, toggle, stop }
}
