import { useMemo, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { cellXY, colorAt, positionAt, segmentIndexAt, stepAt, type Rgb, type Show, type Vec3 } from '@core/show'
import { cellInArea, type Area } from '@core/area'
import { css, isLit, readable, sheet } from '../lib/color'
import { batteryLevel, isAlive } from '../state/useLink'
import { DRONE_WIDTH_CM, DroneArt } from './DroneArt'
import './MatChart.css'
import { tr } from '@core/i18n'

/**
 * The mat as the sheet of a formation chart: 12 x 12 cells of 40 cm, cell 0 at the bottom left, cells numbered to
 * the right and up. Drones are numbered dots; the path of every drone is a thin line (walked part solid, the rest
 * dashed); the selected drone keeps its colour and the others step back.
 *
 * World coordinates are centimetres, x along the columns and y along the rows. Cells are centred on multiples of
 * 40 cm, so the sheet spans -20..460 cm; SVG user units 0..480 map to it with y flipped.
 */
const SHEET = 480
const MARGIN = { left: 34, top: 8, right: 6, bottom: 32 }
const MIN_DRONE_PX = 44
const CLOSE_CM = 60

/**
 * Tags are drawn as the tag family looks: a dark square, a one-module dark border and a 6 x 6 field of light and dark
 * modules. The pattern of each cell is a stand-in (the same every time), not the real code of the tag on the mat.
 */
const TAG_CM = 14
const TAG_MODULE = TAG_CM / 8
const TAGS: string[] = Array.from({ length: 144 }, (_, c) => {
  let seed = (c + 1) * 2654435761
  let d = ''
  for (let row = 0; row < 6; row++) {
    for (let col = 0; col < 6; col++) {
      seed = (Math.imul(seed, 1103515245) + 12345) >>> 0
      if ((seed >>> 16) & 1) {
        const x = (col + 1) * TAG_MODULE
        const y = (row + 1) * TAG_MODULE
        d += `M${x} ${y}h${TAG_MODULE}v${TAG_MODULE}h${-TAG_MODULE}Z`
      }
    }
  }
  return d
})

const X = (x: number) => x + 20
const Y = (y: number) => 460 - y

interface Props {
  show: Show
  t: number
  selected: number | null
  onSelect: (n: number | null) => void
  hoverCell: number | null
  onHoverCell: (cell: number | null) => void
  size: { width: number; height: number }
  /** the part of the mat that is shown, magnified to fill the space */
  area: Area
  /** a cell is being chosen for a drone: a click on a cell is the answer */
  onPick?: (cell: number) => void
  /** a drone was dragged to a cell: it now starts there */
  onMove?: (drone: number, cell: number) => void
  /** drones that are on the link: shown where they really stand */
  live?: LiveDrone[]
}

/** A stretch of a path lit by one LED colour: segments s0..s1 and the points between them (one more than segments). */
interface Run {
  color: string
  s0: number
  s1: number
  t0: number
  t1: number
  points: Vec3[]
}

interface Track {
  number: number
  color: Rgb | null
  runs: Run[]
}

/** Cut a path into runs of one LED colour, so the chart shows the light design along the route. */
function buildRuns(d: Show['drones'][number]): Run[] {
  const runs: Run[] = []
  d.path.forEach((seg, i) => {
    const [, rgb] = colorAt(d.steps, (seg.t0 + seg.t1) / 2)
    const color = isLit(rgb) ? css(readable(rgb)) : 'var(--ink-3)'
    const last = runs[runs.length - 1]
    if (last && last.color === color) {
      last.s1 = i
      last.t1 = seg.t1
      last.points.push(seg.p1)
    } else {
      runs.push({ color, s0: i, s1: i, t0: seg.t0, t1: seg.t1, points: [seg.p0, seg.p1] })
    }
  })
  return runs
}

export function MatChart({ show, t, selected, onSelect, hoverCell, onHoverCell, size, area, live = [], onPick, onMove }: Props) {
  // The shown part of the sheet in user units (y runs down), and the window onto it with room for the numerals.
  const x0 = 40 * area.col0
  const x1 = 40 * (area.col0 + area.cols)
  const y0 = SHEET - 40 * (area.row0 + area.rows)
  const y1 = SHEET - 40 * area.row0
  const VIEW = { x: x0 - MARGIN.left, y: y0 - MARGIN.top, w: x1 - x0 + MARGIN.left + MARGIN.right, h: y1 - y0 + MARGIN.top + MARGIN.bottom }
  const scale = Math.max(Math.min(size.width / VIEW.w, size.height / VIEW.h), 0) // pixels per user unit
  const svgW = VIEW.w * scale
  const svgH = VIEW.h * scale
  const px = (v: number) => (scale > 0 ? v / scale : v)

  const tracks = useMemo<Track[]>(
    () =>
      show.drones.map((d) => {
        const lit = d.steps.find((s) => s.kind === 'rgb' && isLit(s.args.rgb))
        return { number: d.number, color: lit ? readable(lit.args.rgb as Rgb) : null, runs: buildRuns(d) }
      }),
    [show],
  )

  const state = show.drones.map((d, i) => {
    const pos = positionAt(d.path, t)
    const idx = Math.min(segmentIndexAt(d.path, t), d.path.length)
    const [, ledRgb] = colorAt(d.steps, t)
    const step = stepAt(d.steps, d.path, t)
    return { drone: d, track: tracks[i], pos, idx, led: isLit(ledRgb) ? ledRgb : null, step }
  })

  const close: { a: Vec3; b: Vec3; d: number; key: string }[] = []
  for (let i = 0; i < state.length; i++) {
    for (let j = i + 1; j < state.length; j++) {
      const a = state[i].pos
      const b = state[j].pos
      const d = Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])
      if (d < CLOSE_CM) close.push({ a, b, d, key: `${i}-${j}` })
    }
  }

  const targets = new Map<number, number>() // drone number -> cell it is flying to now
  const heldCells = new Set<number>() // cells whose number is shown in ink
  for (const s of state) {
    if (s.step && (s.step.kind === 'code' || s.step.kind === 'code_z')) targets.set(s.drone.number, s.step.args.cell)
    const [x, y] = s.pos
    const col = Math.round(x / 40)
    const row = Math.round(y / 40)
    if (cellInArea(area, col + 12 * row) && col >= 0 && col < 12 && (selected === null || selected === s.drone.number)) {
      heldCells.add(col + 12 * row)
    }
  }
  if (hoverCell !== null) heldCells.add(hoverCell)
  const targetCell = selected !== null ? targets.get(selected) ?? null : null
  if (targetCell !== null) heldCells.add(targetCell)

  const droneK = Math.max(1, px(MIN_DRONE_PX) / DRONE_WIDTH_CM)

  // a drone dragged by the pointer; `moved` turns on after a few pixels, so a plain click still selects
  const [drag, setDrag] = useState<{ n: number; x: number; y: number; cell: number | null; moved: boolean } | null>(null)
  const justDragged = useRef(false)

  const cellAt = (e: MouseEvent<SVGSVGElement>): number | null => {
    const r = e.currentTarget.getBoundingClientRect()
    const ux = (e.clientX - r.left) / scale + VIEW.x
    const uy = (e.clientY - r.top) / scale + VIEW.y
    if (ux < x0 || ux >= x1 || uy < y0 || uy >= y1) return null
    return Math.floor(ux / 40) + 12 * Math.floor((SHEET - uy) / 40)
  }

  const cellRect = (cell: number) => {
    const col = cell % 12
    const row = Math.floor(cell / 12)
    return { x: 40 * col, y: SHEET - 40 * (row + 1), w: 40, h: 40 }
  }

  const colLines = Array.from({ length: area.cols + 1 }, (_, k) => area.col0 + k)
  const rowLines = Array.from({ length: area.rows + 1 }, (_, k) => area.row0 + k)
  const cells = Array.from({ length: 144 }, (_, c) => c).filter((c) => cellInArea(area, c))

  return (
    <svg
      className="mat"
      width={svgW}
      height={svgH}
      viewBox={`${VIEW.x} ${VIEW.y} ${VIEW.w} ${VIEW.h}`}
      role="img"
      aria-label={tr('Коврик 12 на 12 клеток сверху: дроны, их пути и цели')}
      onMouseMove={(e) => {
        const c = cellAt(e)
        onHoverCell(c)
        const { clientX, clientY } = e
        setDrag((d) => (d ? { ...d, cell: c, moved: d.moved || Math.hypot(clientX - d.x, clientY - d.y) > 5 } : d))
      }}
      onMouseLeave={() => {
        onHoverCell(null)
        setDrag(null)
      }}
      onMouseUp={() => {
        if (drag?.moved && drag.cell !== null && onMove) {
          justDragged.current = true
          onMove(drag.n, drag.cell)
        } else if (drag?.moved) justDragged.current = true
        setDrag(null)
      }}
      data-picking={onPick ? 'true' : undefined}
      data-dragging={drag?.moved ? 'true' : undefined}
      onClick={(e) => {
        if (justDragged.current) {
          justDragged.current = false
          return
        }
        const c = onPick ? cellAt(e) : null
        if (onPick && c !== null) onPick(c)
        else onSelect(null)
      }}
    >
      <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="var(--paper)" />

      {targetCell !== null && (
        <rect {...cellRect(targetCell)} fill="var(--accent-tint)" opacity={0.8} />
      )}
      {drag?.moved && drag.cell !== null && <rect {...cellRect(drag.cell)} fill="var(--accent-tint)" stroke="var(--accent)" strokeWidth={px(2)} />}
      {hoverCell !== null && <rect {...cellRect(hoverCell)} fill="var(--accent-tint)" opacity={0.55} />}

      {/* field lines: every cell boundary, the third ones stronger like the yard lines of a chart */}
      <g strokeWidth={px(1)} fill="none">
        {colLines.map((k) => (
          <line key={`c${k}`} x1={40 * k} y1={y0} x2={40 * k} y2={y1} stroke={k % 3 === 0 ? 'var(--rule-strong)' : 'var(--rule)'} />
        ))}
        {rowLines.map((k) => (
          <line key={`r${k}`} x1={x0} y1={SHEET - 40 * k} x2={x1} y2={SHEET - 40 * k} stroke={k % 3 === 0 ? 'var(--rule-strong)' : 'var(--rule)'} />
        ))}
      </g>

      {/* hash marks on the bottom and left edges */}
      <g stroke="var(--rule-strong)" strokeWidth={px(1)}>
        {colLines.map((k) => (
          <line key={`c${k}`} x1={40 * k} y1={y1} x2={40 * k} y2={y1 + (k % 3 === 0 ? 9 : 5)} />
        ))}
        {rowLines.map((k) => (
          <line key={`r${k}`} x1={x0 - (k % 3 === 0 ? 9 : 5)} y1={SHEET - 40 * k} x2={x0} y2={SHEET - 40 * k} />
        ))}
      </g>

      {/* an AprilTag at every cell centre, where the drone looks down to find its place */}
      <g stroke="none">
        {cells.map((c) => {
          const cx = 40 * (c % 12) + 20
          const cy = SHEET - 40 * (Math.floor(c / 12) + 1) + 20
          return (
            <g key={c} transform={`translate(${cx - TAG_CM / 2} ${cy - TAG_CM / 2})`}>
              <rect width={TAG_CM} height={TAG_CM} fill="var(--ink-2)" opacity={0.3} />
              <path d={TAGS[c]} fill="var(--paper)" />
            </g>
          )
        })}
      </g>

      {/* axis numerals */}
      <g fontSize={px(13)} fontWeight={600} fill="var(--ink-2)">
        {Array.from({ length: area.cols }, (_, k) => area.col0 + k).map((i) => (
          <text key={`c${i}`} x={40 * i + 20} y={y1 + px(24)} textAnchor="middle">{i}</text>
        ))}
        {Array.from({ length: area.rows }, (_, k) => area.row0 + k).map((i) => (
          <text key={`r${i}`} x={x0 - px(12)} y={SHEET - 40 * i - 20 + px(4.5)} textAnchor="end">{i}</text>
        ))}
      </g>

      {/* cell numbers, quiet; the ones that matter now (under a drone, a target, the pointer) turn to ink */}
      <g fontSize={px(10.5)}>
        {cells.map((c) => {
          const r = cellRect(c)
          const held = heldCells.has(c)
          return (
            <text key={c} x={r.x + 4} y={r.y + px(12)} fill={held ? 'var(--ink)' : 'var(--ink-3)'} fontWeight={held ? 700 : 400}>
              {c}
            </text>
          )
        })}
      </g>

      {/* paths */}
      <g fill="none" strokeLinejoin="round" strokeLinecap="round">
        {[...state]
          .sort((p, q) => (p.drone.number === selected ? 1 : 0) - (q.drone.number === selected ? 1 : 0))
          .map(({ drone, track, pos, idx }) => {
            const strong = selected === drone.number
            const here = `${X(pos[0])},${Y(pos[1])}`
            const poly = (pts: Vec3[]) => pts.map((p) => `${X(p[0])},${Y(p[1])}`).join(' ')
            const dash = `${px(5)} ${px(4)}`
            if (!strong) {
              // Only the selected drone shows its whole route; the others show the leg they are flying now.
              const leg = drone.path[idx]
              if (!leg) return null
              return (
                <polyline
                  key={drone.number}
                  points={`${here} ${X(leg.p1[0])},${Y(leg.p1[1])}`}
                  stroke="var(--ink-2)"
                  strokeWidth={px(1.4)}
                  strokeDasharray={dash}
                  opacity={selected === null ? 0.75 : 0.3}
                />
              )
            }
            return (
              <g key={drone.number}>
                {track.runs.map((run, k) => {
                  const done = idx > run.s1 // every segment of the run is behind the drone
                  const todo = idx < run.s0
                  const walkedW = px(3)
                  const aheadW = px(2)
                  if (done) return <polyline key={k} points={poly(run.points)} stroke={run.color} strokeWidth={walkedW} />
                  if (todo)
                    return <polyline key={k} points={poly(run.points)} stroke={run.color} strokeWidth={aheadW} strokeDasharray={dash} />
                  const cut = idx - run.s0 // the drone is inside this run
                  return (
                    <g key={k} stroke={run.color}>
                      <polyline points={`${poly(run.points.slice(0, cut + 1))} ${here}`} strokeWidth={walkedW} />
                      <polyline points={`${here} ${poly(run.points.slice(cut + 1))}`} strokeWidth={aheadW} strokeDasharray={dash} />
                    </g>
                  )
                })}
              </g>
            )
          })}
      </g>

      {/* sets of the selected drone: where each cell move ends, in order */}
      {selected !== null && (
        <g fontSize={px(10.5)} fill="var(--ink)" stroke="none">
          {show.drones
            .find((d) => d.number === selected)
            ?.path.filter((s) => s.kind === 'code' || s.kind === 'code_z')
            .map((s, i, all) => (
              <g key={i}>
                <rect
                  x={X(s.p1[0]) - 4}
                  y={Y(s.p1[1]) - 4}
                  width={8}
                  height={8}
                  fill="var(--sheet)"
                  stroke="var(--ink)"
                  strokeWidth={px(1.2)}
                />
                {all.length <= 24 && <text x={X(s.p1[0]) + 6} y={Y(s.p1[1]) - 6}>{i + 1}</text>}
              </g>
            ))}
        </g>
      )}

      {/* too close */}
      {close.map(({ a, b, d, key }) => (
        <circle
          key={key}
          cx={X((a[0] + b[0]) / 2)}
          cy={Y((a[1] + b[1]) / 2)}
          r={d / 2 + DRONE_WIDTH_CM / 2 * droneK + 4}
          fill="none"
          stroke="var(--danger)"
          strokeWidth={px(2)}
        />
      ))}

      {/* drones */}
      {state.map(({ drone, pos, led }) => {
        const strong = selected === drone.number
        const faded = selected !== null && !strong
        return (
          <g
            key={drone.number}
            className="mat-drone"
            transform={`translate(${X(pos[0])} ${Y(pos[1])})`}
            opacity={faded ? 0.45 : 1}
            data-draggable={onMove ? 'true' : undefined}
            onMouseDown={(e) => {
              if (e.button !== 0 || !onMove || onPick) return
              setDrag({ n: drone.number, x: e.clientX, y: e.clientY, cell: null, moved: false })
            }}
            onClick={(e) => {
              e.stopPropagation()
              if (justDragged.current) {
                justDragged.current = false
                return
              }
              onSelect(strong ? null : drone.number)
            }}
          >
            {strong && (
              <circle r={14 * droneK} fill="none" stroke="var(--accent)" strokeWidth={px(1.6)} strokeDasharray={`${px(5)} ${px(4)}`} />
            )}
            <g transform={`scale(${droneK})`}>
              <DroneArt led={led} />
            </g>
          </g>
        )
      })}

      {/* the drone under the pointer while it is dragged: it will stand in the middle of the cell */}
      {drag?.moved && drag.cell !== null && (
        <g transform={`translate(${40 * (drag.cell % 12) + 20} ${SHEET - 40 * (Math.floor(drag.cell / 12) + 1) + 20})`} opacity={0.8} pointerEvents="none">
          <g transform={`scale(${droneK})`}>
            <DroneArt led={null} />
          </g>
          <text y={-14 * droneK} textAnchor="middle" fontSize={px(12.5)} fontWeight={700} fill="var(--ink)" stroke="var(--sheet)" strokeWidth={px(3)} paintOrder="stroke">
            {drag.n}
          </text>
        </g>
      )}

      {/* number plates, drawn after all drones so none is hidden */}
      {state.map(({ drone, pos, track, led }) => {
        const strong = selected === drone.number
        const faded = selected !== null && !strong
        const color = led ? readable(led, sheet()) : track.color
        const w = px(drone.number >= 10 ? 26 : 22)
        const h = px(18)
        const cx = X(pos[0]) + (DRONE_WIDTH_CM / 2) * droneK * 0.78
        const cy = Y(pos[1]) + (DRONE_WIDTH_CM / 2) * droneK * 0.78
        return (
          <g key={drone.number} opacity={faded ? 0.5 : 1} pointerEvents="none">
            <rect
              x={cx - w / 2}
              y={cy - h / 2}
              width={w}
              height={h}
              rx={px(4)}
              fill="var(--sheet)"
              stroke={strong ? 'var(--accent)' : color ? css(color) : 'var(--ink-3)'}
              strokeWidth={px(strong ? 2 : 1.6)}
            />
            <text x={cx} y={cy + px(4.5)} textAnchor="middle" fontSize={px(12.5)} fontWeight={700} fill="var(--ink)">
              {drone.number}
            </text>
          </g>
        )
      })}

      {/* real drones on the link: a ring in the accent at the position they report, the IP tail and the battery colour */}
      {live
        .filter((d) => d.fix && isAlive(d))
        .map((d) => {
          const level = batteryLevel(d.batteryV)
          const r = px(15)
          return (
            <g key={d.ip} transform={`translate(${X(d.x)} ${Y(d.y)})`} pointerEvents="none">
              <circle r={r} fill="var(--sheet)" fillOpacity={0.85} stroke="var(--accent)" strokeWidth={px(2.2)} />
              <circle r={px(4)} fill="var(--accent)" />
              <text y={r + px(13)} textAnchor="middle" fontSize={px(11.5)} fontWeight={700} fill="var(--ink)" stroke="var(--sheet)" strokeWidth={px(3)} paintOrder="stroke">
                …{d.ip.split('.').pop()}
                {level !== 'ok' ? ' ▲' : ''}
              </text>
            </g>
          )
        })}

      {/* sheet frame on top */}
      <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="none" stroke="var(--rule-strong)" strokeWidth={px(1.5)} />
    </svg>
  )
}

export { cellXY }
