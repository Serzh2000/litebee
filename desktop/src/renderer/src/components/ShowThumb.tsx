import { useMemo } from 'react'
import type { Rgb } from '@core/show'
import { css, readable } from '../lib/color'
import previews from '../data/previews.json'
import './ShowThumb.css'

type Routes = [string, number[]][]
const ROUTES = previews as unknown as Record<string, Routes>

const hexRgb = (hex: string): Rgb => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)]

/**
 * The routes of a show on its part of the mat, drawn small: a hairline grid of cells and one line in the colour of each
 * drone. Coordinates in the data are tenths of a cell (cell 0 has its middle at 0, 0).
 */
export function ShowThumb({ id, size }: { id: string; size: 6 | 12 }) {
  const routes = ROUTES[id]
  const view = useMemo(() => {
    if (!routes) return null
    const xs = routes.flatMap(([, p]) => p.filter((_, i) => i % 2 === 0))
    const ys = routes.flatMap(([, p]) => p.filter((_, i) => i % 2 === 1))
    if (!xs.length) return null
    // the square part of the mat (a quarter or the whole mat) that holds the show
    const pick = (lo: number, hi: number) => {
      const mid = (lo + hi) / 20
      return size === 12 ? -0.5 : Math.min(Math.max(Math.floor((mid + 0.5) / 6) * 6, 0), 6) - 0.5
    }
    return { x0: pick(Math.min(...xs), Math.max(...xs)), y0: pick(Math.min(...ys), Math.max(...ys)) }
  }, [routes, size])
  if (!routes || !view) return <div className="thumb" aria-hidden="true" />
  const { x0, y0 } = view
  const cells = Array.from({ length: size + 1 }, (_, k) => k)
  return (
    <svg className="thumb" viewBox={`0 0 ${size} ${size}`} preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <g stroke="var(--rule)" strokeWidth={0.04}>
        {cells.map((k) => (
          <g key={k}>
            <line x1={k} y1={0} x2={k} y2={size} />
            <line x1={0} y1={k} x2={size} y2={k} />
          </g>
        ))}
      </g>
      <g fill="none" strokeLinecap="round" strokeLinejoin="round" strokeWidth={size === 6 ? 0.14 : 0.2} opacity={0.9}>
        {routes.map(([hex, p], i) => {
          // y runs up on the mat and down on the screen
          const pts = p.map((v, k) => (k % 2 === 0 ? v / 10 - x0 : size - (v / 10 - y0))).reduce<string[]>((a, v, k) => {
            if (k % 2 === 0) a.push(String(v))
            else a[a.length - 1] += ',' + v
            return a
          }, [])
          return <polyline key={i} points={pts.join(' ')} stroke={css(readable(hexRgb(hex)))} />
        })}
      </g>
      {/* where each drone stands: the only mark of a show that only plays with light */}
      <g stroke="var(--text, #131416)" strokeWidth={0.05}>
        {routes.map(([hex, p], i) =>
          p.length >= 2 ? (
            <circle key={i} cx={p[0] / 10 - x0} cy={size - (p[1] / 10 - y0)} r={size === 6 ? 0.2 : 0.28} fill={css(readable(hexRgb(hex)))} />
          ) : null,
        )}
      </g>
    </svg>
  )
}
