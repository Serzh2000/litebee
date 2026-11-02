import { useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'
import { stepText, STEP_NAME } from '@core/labels'
import { colorAt, stepAt, type Rgb, type Show, type StepKind } from '@core/show'
import { css, isLit, seconds } from '../lib/color'
import { useSize } from '../state/useSize'
import './CueSheet.css'
import { tr } from '@core/i18n'

/**
 * The count sheet under the chart: one lane per drone, time left to right. The LED colour over time is a solid
 * strip (a thin ink edge keeps white and yellow visible on the light lane); above it thin marks show the steps:
 * take-off, landing, a move between cells, a height change, a circle, a calibration.
 */
const LABEL_W = 132
const RULER_H = 18
const MIN_LANE = 13
const MAX_LANE = 20

/** The height the sheet takes for `drones` lanes when it may use `height` px: one lane per drone, as high as is useful. */
export function cueSheetHeight(drones: number, height: number): number {
  const lane = Math.max(MIN_LANE, Math.min(MAX_LANE, Math.floor((height - RULER_H) / Math.max(drones, 3))))
  return RULER_H + lane * drones
}

interface Props {
  show: Show
  t: number
  selected: number | null
  onSelect: (n: number | null) => void
  onSeek: (t: number) => void
  onHover: (text: string | null) => void
  height: number
}

interface Lane {
  number: number
  leds: { from: number; to: number; rgb: Rgb }[]
  marks: Record<StepKind, number[]>
  end: number
}

function buildLane(show: Show, index: number): Lane {
  const d = show.drones[index]
  const leds: Lane['leds'] = []
  const marks = {} as Lane['marks']
  let now = 0
  let rgb: Rgb = [0, 0, 0]
  let from = 0
  for (const s of d.steps) {
    if (s.kind === 'rgb') {
      if (now > from && isLit(rgb)) leds.push({ from, to: now, rgb })
      rgb = s.args.rgb
      from = now
    } else {
      ;(marks[s.kind] ??= []).push(now)
    }
    now += s.seconds
  }
  if (isLit(rgb)) leds.push({ from, to: Math.max(now, show.duration), rgb })
  return { number: d.number, leds, marks, end: now }
}

export function CueSheet({ show, t, selected, onSelect, onSeek, onHover, height }: Props) {
  const [stripRef, size] = useSize<HTMLDivElement>()
  const lanes = useMemo(() => show.drones.map((_, i) => buildLane(show, i)), [show])
  const dragging = useRef(false)
  const [focusIn, setFocusIn] = useState(false)

  const laneH = Math.max(MIN_LANE, Math.min(MAX_LANE, Math.floor((height - RULER_H) / Math.max(lanes.length, 3))))
  const width = size.width
  const x = (time: number) => (show.duration > 0 ? (time / show.duration) * width : 0)
  const timeAt = (clientX: number, el: Element) => {
    const r = el.getBoundingClientRect()
    return Math.min(Math.max(((clientX - r.left) / Math.max(r.width, 1)) * show.duration, 0), show.duration)
  }

  const hover = (e: PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const lane = Math.floor((e.clientY - r.top - RULER_H) / laneH)
    const time = timeAt(e.clientX, e.currentTarget)
    const d = show.drones[lane]
    if (!d) return onHover(null)
    const step = stepAt(d.steps, d.path, time)
    const [name] = colorAt(d.steps, time)
    onHover(`${tr('Дрон {n}', { n: d.number })}, ${seconds(time)} ${tr('с')}: ${step ? tr(stepText(step.kind, step.args)) : tr('нет шагов')}${
      step?.line ? ', ' + tr('строка {n}', { n: step.line }) : ''
    }${name !== 'black' ? ', ' + tr('светодиод {name}', { name }) : ''}`)
  }

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const big = e.shiftKey ? 10 : 1
    if (e.key === 'ArrowLeft') onSeek(t - big)
    else if (e.key === 'ArrowRight') onSeek(t + big)
    else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      const numbers = show.drones.map((d) => d.number)
      const at = selected === null ? -1 : numbers.indexOf(selected)
      const next = e.key === 'ArrowUp' ? Math.max(at - 1, 0) : Math.min(at + 1, numbers.length - 1)
      onSelect(numbers[next])
    } else return
    e.preventDefault()
  }

  const ticks = []
  for (let s = 0; s <= show.duration; s += 10) ticks.push(s)

  const glyph = (kind: StepKind, cx: number, y: number): string => {
    const h = Math.max(3, laneH * 0.28)
    switch (kind) {
      case 'takeoff':
        return `M${cx} ${y - h}L${cx - h} ${y + h}L${cx + h} ${y + h}Z`
      case 'land':
        return `M${cx - h} ${y - h}L${cx + h} ${y - h}L${cx} ${y + h}Z`
      case 'code':
      case 'code_z':
        return `M${cx} ${y - h}L${cx} ${y + h}`
      case 'set_z':
        return `M${cx - h} ${y}L${cx + h} ${y}`
      case 'circle':
      case 'circle_z':
        return `M${cx - h} ${y}a${h} ${h} 0 1 0 ${2 * h} 0a${h} ${h} 0 1 0 ${-2 * h} 0`
      case 'calibrate':
        return `M${cx - h * 0.7} ${y - h * 0.7}h${h * 1.4}v${h * 1.4}h${-h * 1.4}Z`
      default:
        return ''
    }
  }

  return (
    <div className="cue" style={{ height: RULER_H + laneH * lanes.length }}>
      <div className="cue-labels" style={{ width: LABEL_W, paddingTop: RULER_H }}>
        {show.drones.map((d) => {
          const [, led] = colorAt(d.steps, t)
          const on = selected === d.number
          return (
            <button
              key={d.number}
              className="cue-label"
              data-selected={on}
              style={{ height: laneH }}
              aria-pressed={on}
              onClick={() => onSelect(on ? null : d.number)}
            >
              <span className="cue-swatch" style={{ background: isLit(led) ? css(led) : 'transparent' }} />
              <span>{tr('Дрон {n}', { n: d.number })}</span>
            </button>
          )
        })}
      </div>

      <div
        className="cue-strip"
        ref={stripRef}
        tabIndex={0}
        role="slider"
        aria-label={tr('Время шоу')}
        aria-valuemin={0}
        aria-valuemax={Math.round(show.duration)}
        aria-valuenow={Math.round(t)}
        aria-valuetext={`${seconds(t)} ${tr('секунд')}`}
        onKeyDown={onKey}
        onFocus={() => setFocusIn(true)}
        onBlur={() => setFocusIn(false)}
        data-focus={focusIn}
      >
        {width > 0 && (
          <svg
            width={width}
            height={RULER_H + laneH * lanes.length}
            onPointerDown={(e) => {
              dragging.current = true
              e.currentTarget.setPointerCapture(e.pointerId)
              onSeek(timeAt(e.clientX, e.currentTarget))
            }}
            onPointerMove={(e) => {
              hover(e)
              if (dragging.current) onSeek(timeAt(e.clientX, e.currentTarget))
            }}
            onPointerUp={() => (dragging.current = false)}
            onPointerLeave={() => onHover(null)}
          >
            {/* ruler: a tick every 10 s, a number every 30 s */}
            <g fontSize={11} fill="var(--ink-3)">
              {ticks.map((s) => (
                <g key={s}>
                  <line x1={x(s) + 0.5} x2={x(s) + 0.5} y1={s % 30 === 0 ? 4 : 10} y2={RULER_H} stroke="var(--rule-strong)" />
                  {s % 30 === 0 && (
                    <text x={x(s) + 3} y={11}>
                      {s}
                    </text>
                  )}
                </g>
              ))}
            </g>

            {lanes.map((lane, i) => {
              const y = RULER_H + i * laneH
              const on = selected === null || selected === lane.number
              const markY = y + laneH * 0.3
              return (
                <g key={lane.number} opacity={on ? 1 : 0.35}>
                  <line x1={0} x2={width} y1={y + laneH - 0.5} y2={y + laneH - 0.5} stroke="var(--rule)" />
                  <rect x={0} y={y + laneH * 0.42} width={x(lane.end)} height={Math.max(2, laneH * 0.5)} fill="var(--rule)" opacity={0.5} />
                  {lane.leds.map((seg, k) => (
                    <rect
                      key={k}
                      x={x(seg.from)}
                      y={y + laneH * 0.42}
                      width={Math.max(x(seg.to) - x(seg.from), 1)}
                      height={Math.max(2, laneH * 0.5)}
                      fill={css(seg.rgb)}
                      stroke="var(--ink)"
                      strokeOpacity={0.3}
                      strokeWidth={0.75}
                    />
                  ))}
                  <g stroke="var(--ink-2)" strokeWidth={1} fill="none">
                    {(Object.keys(lane.marks) as StepKind[]).map((kind) => (
                      <path
                        key={kind}
                        d={lane.marks[kind].map((time) => glyph(kind, Math.round(x(time)) + 0.5, markY)).join('')}
                        fill={kind === 'takeoff' || kind === 'land' || kind === 'calibrate' ? 'var(--ink-2)' : 'none'}
                      />
                    ))}
                  </g>
                </g>
              )
            })}

            {/* the time cursor */}
            <g pointerEvents="none">
              <line x1={x(t)} x2={x(t)} y1={0} y2={RULER_H + laneH * lanes.length} stroke="var(--accent)" strokeWidth={2} />
              <path d={`M${x(t) - 5} 0h10l-5 6z`} fill="var(--accent)" />
            </g>
          </svg>
        )}
      </div>
    </div>
  )
}

export { STEP_NAME }
