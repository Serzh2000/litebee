import { css, isLit } from '../lib/color'
import type { Rgb } from '@core/show'

/**
 * The LiteBee Wing seen from above, drawn from the photograph of the user's drone: white body with a dark lens at
 * the nose, a white lid over the grey battery block, four grey building-block arms with holes, silver motors with
 * translucent two-blade propellers, grey feet. No guard rings (the real drone has none).
 *
 * Local frame in centimetres, centre at (0, 0), nose towards -y (up on the screen). True width 20.9 cm.
 */
export const DRONE_WIDTH_CM = 20.9

const MOTORS: [number, number][] = [
  [-5.9, -4.5],
  [5.9, -4.5],
  [5.9, 4.5],
  [-5.9, 4.5],
]
const BLADE_ANGLES = [28, -28, 28, -28]
const BLADE =
  'M0 0.25 C0.825 0.95 2.475 0.85 3.3 0.15 C2.64 -0.35 1.155 -0.5 0 -0.25 Z'

export function DroneArt({ led, live = false }: { led: Rgb | null; live?: boolean }) {
  const ring = led && isLit(led) ? css(led) : 'var(--drone-dark)'
  return (
    <g>
      {MOTORS.map(([mx, my], i) => {
        const foot = [mx + Math.sign(mx) * 4.3, my + Math.sign(my) * 0.5]
        return (
          <g key={i}>
            <line x1={0} y1={0} x2={mx} y2={my} stroke="var(--drone-dark)" strokeWidth={2.1} />
            <line x1={0} y1={0} x2={mx} y2={my} stroke="var(--drone-grey)" strokeWidth={1.6} />
            {[0.45, 0.62, 0.79].map((k) => (
              <circle key={k} cx={mx * k} cy={my * k} r={0.26} fill="var(--drone-dark)" />
            ))}
            <line x1={mx} y1={my} x2={foot[0]} y2={foot[1]} stroke="var(--drone-dark)" strokeWidth={1.9} />
            <line x1={mx} y1={my} x2={foot[0]} y2={foot[1]} stroke="var(--drone-grey)" strokeWidth={1.4} />
            <circle cx={mx} cy={my} r={1.35} fill="var(--drone-grey)" />
            <circle cx={mx} cy={my} r={0.95} fill="var(--drone-silver)" />
            <g transform={`translate(${mx} ${my}) rotate(${BLADE_ANGLES[i]})`}>
              {[0, 180].map((rot) => (
                <path
                  key={rot}
                  d={BLADE}
                  transform={`rotate(${rot})`}
                  fill="var(--drone-body)"
                  fillOpacity={0.6}
                  stroke="var(--drone-silver)"
                  strokeWidth={0.12}
                  strokeOpacity={0.7}
                />
              ))}
            </g>
            <circle cx={mx} cy={my} r={0.42} fill="var(--drone-body)" />
          </g>
        )
      })}
      <rect x={-2.9} y={-4.4} width={5.8} height={8.6} rx={1.7} fill="var(--drone-body)" stroke="var(--drone-grey)" strokeWidth={0.35} />
      <rect x={-2.3} y={0.6} width={4.6} height={3.3} rx={0.5} fill="var(--drone-grey)" stroke="var(--drone-dark)" strokeWidth={0.3} />
      <rect x={-2.45} y={-1.9} width={4.9} height={4.2} rx={0.9} fill="var(--drone-body)" stroke="var(--drone-dark)" strokeWidth={0.3} />
      <rect
        x={-2.65}
        y={-2.2}
        width={5.3}
        height={6.2}
        rx={1.4}
        fill="none"
        stroke={ring}
        strokeWidth={led && isLit(led) ? 0.7 : 0.35}
      />
      <circle cx={0} cy={-3.5} r={0.95} fill="var(--drone-dark)" stroke="var(--drone-grey)" strokeWidth={0.3} />
      <circle cx={-0.3} cy={-3.8} r={0.25} fill="var(--drone-silver)" />
      <path d="M0 -11.8 L-1.3 -9.8 L1.3 -9.8 Z" fill={live ? 'var(--accent)' : 'var(--ink-2)'} />
    </g>
  )
}
