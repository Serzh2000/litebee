import { useMemo, useRef, useState } from 'react'
import type { MouseEvent } from 'react'
import { cellXY, colorAt, positionAt, segmentIndexAt, stepAt, type Rgb, type Show, type Vec3 } from '@core/show'
import { cellInArea, type Area } from '@core/area'
import { TAG36H11 } from '@core/apriltag'
import { css, isLit, readable } from '../lib/color'
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
/** Room for the numerals around the grid, in screen pixels: text and marks keep their size, the grid takes what is left. */
const MARGIN = { left: 30, top: 6, right: 8, bottom: 30 }
const MIN_DRONE_PX = 44
/** A cell narrower than this (px) shows only every second (and below the second one, every third) cell number. */
const CELL_NUM_PX = 40
const CELL_NUM_PX_2 = 28
const CLOSE_CM = 60

/**
 * Tags are the real ones of the mat: tag36h11, the id of a tag is the number of its cell (see core/apriltag.ts): a dark
 * square with a one-module dark border and a 6 x 6 field of light and dark modules.
 */
export const TAG_CM = 14
const TAG_MODULE = TAG_CM / 8
export const TAGS: string[] = TAG36H11.map((bits) => {
  let d = ''
  for (let row = 0; row < 6; row++) {
    for (let col = 0; col < 6; col++) {
      if (bits[row * 6 + col] === '1') {
        const x = (col + 1) * TAG_MODULE
        const y = (row + 1) * TAG_MODULE
        d += `M${x} ${y}h${TAG_MODULE}v${TAG_MODULE}h${-TAG_MODULE}Z`
      }
    }
  }
  return d
})

/** How the grid of an area fits a box: pixels per user unit and the grid's size on screen (the map is as large as the box allows). */
export function fitMap(area: Area, width: number, height: number) {
  const gw = 40 * area.cols
  const gh = 40 * area.rows
  const scale = Math.max(Math.min((width - MARGIN.left - MARGIN.right) / gw, (height - MARGIN.top - MARGIN.bottom) / gh), 0)
  return { scale, gridW: gw * scale, gridH: gh * scale }
}

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
  showTags?: boolean
  showRoutes?: boolean
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

export function MatChart({ show, t, selected, onSelect, hoverCell, onHoverCell, size, area, live = [], onPick, onMove, showTags = false, showRoutes = true }: Props) {
  // The shown part of the sheet in user units (y runs down), and the window onto it with room for the numerals.
  const x0 = 40 * area.col0
  const x1 = 40 * (area.col0 + area.cols)
  const y0 = SHEET - 40 * (area.row0 + area.rows)
  const y1 = SHEET - 40 * area.row0
  const { scale } = fitMap(area, size.width, size.height) // pixels per user unit
  const px = (v: number) => (scale > 0 ? v / scale : v)
  const svgW = (x1 - x0) * scale + MARGIN.left + MARGIN.right
  const svgH = (y1 - y0) * scale + MARGIN.top + MARGIN.bottom
  const VIEW = { x: x0 - px(MARGIN.left), y: y0 - px(MARGIN.top), w: px(svgW), h: px(svgH) }
  const cellPx = 40 * scale
  const numStep = cellPx >= CELL_NUM_PX ? 1 : cellPx >= CELL_NUM_PX_2 ? 2 : 3

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

  // The bullet of a drone: a circle in the LED colour, its number in white (in ink on a light colour, with a ring on white).
  const bullet = (n: number, rgb: Rgb | null, strong: boolean) => {
    const lit = rgb !== null && isLit(rgb)
    const ring = lit ? css(readable(rgb)) : 'var(--control)'
    return (
      <>
        <circle r={px(10)} fill={strong ? 'var(--active)' : 'var(--surface)'} stroke={ring} strokeWidth={px(strong ? 2 : 1.2)} />
        <text y={px(3.8)} textAnchor="middle" fontSize={px(11)} fontWeight={500} fill="var(--text)" className="mat-num">
          {n}
        </text>
      </>
    )
  }

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
      <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="var(--raised)" />

      {targetCell !== null && <rect {...cellRect(targetCell)} fill="var(--accent-tint)" opacity={0.8} />}
      {drag?.moved && drag.cell !== null && <rect {...cellRect(drag.cell)} fill="var(--accent-tint)" stroke="var(--accent)" strokeWidth={px(2)} />}
      {hoverCell !== null && <rect {...cellRect(hoverCell)} fill="var(--accent-tint)" opacity={0.55} />}

      {/* hairlines: every cell boundary */}
      <g strokeWidth={px(1)} fill="none" stroke="var(--rule)">
        {colLines.map((k) => (
          <line key={`c${k}`} x1={40 * k} y1={y0} x2={40 * k} y2={y1} />
        ))}
        {rowLines.map((k) => (
          <line key={`r${k}`} x1={x0} y1={SHEET - 40 * k} x2={x1} y2={SHEET - 40 * k} />
        ))}
      </g>

      {/* an AprilTag at every cell centre, where the drone looks down to find its place: dark ink on the cell, the real pattern */}
      <g stroke="none" display={showTags ? undefined : 'none'} opacity={.65}>
        {cells.map((c) => {
          const cx = 40 * (c % 12) + 20
          const cy = SHEET - 40 * (Math.floor(c / 12) + 1) + 20
          return (
            <g key={c} transform={`translate(${cx - TAG_CM / 2} ${cy - TAG_CM / 2})`}>
              <rect width={TAG_CM} height={TAG_CM} fill="var(--text)" opacity={0.64} />
              <path d={TAGS[c]} fill="var(--raised)" />
            </g>
          )
        })}
      </g>

      {/* axis numerals, 13 px */}
      <g fontSize={px(13)} fontWeight={500} fill="var(--muted)" className="mat-num">
        {Array.from({ length: area.cols }, (_, k) => area.col0 + k).map((i) => (
          <text key={`c${i}`} x={40 * i + 20} y={y1 + px(20)} textAnchor="middle">
            {i}
          </text>
        ))}
        {Array.from({ length: area.rows }, (_, k) => area.row0 + k).map((i) => (
          <text key={`r${i}`} x={x0 - px(10)} y={SHEET - 40 * i - 20 + px(4.5)} textAnchor="end">
            {i}
          </text>
        ))}
      </g>

      {/* cell numbers, 12 px, quiet; the ones that matter now (under a drone, a target, the pointer) turn to ink */}
      <g fontSize={px(11)} className="mat-num">
        {cells.map((c) => {
          const r = cellRect(c)
          const held = heldCells.has(c)
          if (!held && (c % 12) % numStep !== 0) return null
          return (
            <text key={c} x={r.x + px(4)} y={r.y + px(14)} fill={held ? 'var(--text)' : 'var(--faint)'} fontWeight={held ? 600 : 400}>
              {c}
            </text>
          )
        })}
      </g>

      {/* routes: 3 px in the drone's colour, the selected one 4 px and whole, the others a step back; walked part solid, the rest dashed */}
      <g fill="none" strokeLinejoin="round" strokeLinecap="round" display={showRoutes ? undefined : 'none'}>
        {[...state]
          .sort((p, q) => (p.drone.number === selected ? 1 : 0) - (q.drone.number === selected ? 1 : 0))
          .map(({ drone, track, pos, idx }) => {
            const strong = selected === drone.number
            const here = `${X(pos[0])},${Y(pos[1])}`
            const poly = (pts: Vec3[]) => pts.map((p) => `${X(p[0])},${Y(p[1])}`).join(' ')
            const dash = `${px(7)} ${px(5)}`
            const w = px(strong ? 2.5 : 1.4)
            const base = 'var(--muted)'
            return (
              <g key={drone.number} opacity={strong ? .95 : selected === null ? .28 : .14}>
                {track.runs.map((run, k) => {
                  const color = strong ? run.color : base
                  const done = idx > run.s1 // every segment of the run is behind the drone
                  const todo = idx < run.s0
                  if (done) return <polyline key={k} points={poly(run.points)} stroke={color} strokeWidth={w} />
                  if (todo) return <polyline key={k} points={poly(run.points)} stroke={color} strokeWidth={w} strokeDasharray={dash} />
                  const cut = idx - run.s0 // the drone is inside this run
                  return (
                    <g key={k} stroke={color} strokeWidth={w}>
                      <polyline points={`${poly(run.points.slice(0, cut + 1))} ${here}`} />
                      <polyline points={`${here} ${poly(run.points.slice(cut + 1))}`} strokeDasharray={dash} />
                    </g>
                  )
                })}
              </g>
            )
          })}
      </g>

      {/* stations of the selected drone: a small white circle where each cell move ends, the order beside it */}
      {selected !== null && showRoutes && (
        <g fontSize={px(12)} fill="var(--text)" stroke="none" className="mat-num">
          {show.drones
            .find((d) => d.number === selected)
            ?.path.filter((s) => s.kind === 'code' || s.kind === 'code_z')
            .map((s, i, all) => (
              <g key={i}>
                <circle cx={X(s.p1[0])} cy={Y(s.p1[1])} r={px(5)} fill="#ffffff" stroke="var(--text)" strokeWidth={px(1.5)} />
                {all.length <= 24 && (
                  <text x={X(s.p1[0]) + px(9)} y={Y(s.p1[1]) - px(7)} stroke="var(--surface)" strokeWidth={px(3)} paintOrder="stroke" fontWeight={600}>
                    {i + 1}
                  </text>
                )}
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
          r={d / 2 + (DRONE_WIDTH_CM / 2) * droneK + 4}
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
            opacity={faded ? 0.5 : 1}
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
            {strong && <circle r={14 * droneK} fill="none" stroke="var(--accent)" strokeWidth={px(2)} strokeDasharray={`${px(5)} ${px(4)}`} />}
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
          <g transform={`translate(0 ${-14 * droneK})`}>{bullet(drag.n, null, true)}</g>
        </g>
      )}

      {/* line bullets, drawn after all drones so none is hidden: 22 px, the LED colour, 100 % for the selected one and 70 % for the rest */}
      {state.map(({ drone, pos, track, led }) => {
        const strong = selected === drone.number
        const rgb = led ?? track.color
        const o = (DRONE_WIDTH_CM / 2) * droneK * 0.78
        return (
          <g key={drone.number} transform={`translate(${X(pos[0]) + o} ${Y(pos[1]) + o})`} pointerEvents="none">
            {bullet(drone.number, rgb, strong)}
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
              <circle r={r} fill="var(--surface)" fillOpacity={0.85} stroke="var(--accent)" strokeWidth={px(2)} />
              <circle r={px(4)} fill="var(--accent)" />
              <text
                y={r + px(14)}
                textAnchor="middle"
                fontSize={px(12)}
                fontWeight={600}
                fill="var(--text)"
                stroke="var(--surface)"
                strokeWidth={px(3)}
                paintOrder="stroke"
                className="mat-num"
              >
                …{d.ip.split('.').pop()}
                {level !== 'ok' ? ' ▲' : ''}
              </text>
            </g>
          )
        })}

      {/* the edge of the mat */}
      <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} fill="none" stroke="var(--control)" strokeWidth={px(1)} />
    </svg>
  )
}

export { cellXY }
