import { useMemo, useRef } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'
import { Plus } from 'lucide-react'
import { stepText } from '@core/labels'
import { colorAt, stepAt, type Rgb, type Show } from '@core/show'
import { css, isLit, readable, seconds } from '../lib/color'
import { useSize } from '../state/useSize'
import './Timetable.css'
import { tr } from '@core/i18n'

/**
 * The score ("Партитура"): one row per drone, time runs left to right. A row says who (the line bullet) and, on its own
 * strip, the LED colour over time with a station at take-off, at every target and at landing. A single accent cursor runs
 * through all rows. Click or drag on a strip to move the time; click a name to pick the drone.
 */

/** A run wider than this (px) gets the one-letter name of its colour on the selected row, so colour is not the only carrier. */
const LABEL_MIN_W = 40
/** The strips of rows that are not selected are drawn at this strength of their colour. */
const DIM = 0.55

/** The one-letter name of an LED colour, '' for a colour without one. */
function colorLetter(name: string): string {
  switch (name) {
    case 'red':
      return tr('К')
    case 'green':
      return tr('З')
    case 'blue':
      return tr('С')
    case 'yellow':
      return tr('Ж')
    case 'cyan':
      return tr('Г')
    case 'purple':
    case 'magenta':
    case 'pink':
      return tr('Р')
    case 'white':
      return tr('Б')
    default:
      return ''
  }
}

interface Lane {
  number: number
  leds: { from: number; to: number; rgb: Rgb; name: string }[]
  /** the moments of the stations: take-off when it starts, a target when it is reached, landing when the drone is down */
  stations: number[]
  end: number
}

function buildLane(show: Show, index: number): Lane {
  const d = show.drones[index]
  const leds: Lane['leds'] = []
  const stations: number[] = []
  let now = 0
  let rgb: Rgb = [0, 0, 0]
  let from = 0
  let name = 'black'
  for (const s of d.steps) {
    if (s.kind === 'rgb') {
      if (now > from && isLit(rgb)) leds.push({ from, to: now, rgb, name })
      rgb = s.args.rgb
      name = s.args.color
      from = now
    } else if (s.kind === 'takeoff') stations.push(now)
    else if (s.kind === 'code' || s.kind === 'code_z' || s.kind === 'land') stations.push(now + s.seconds)
    now += s.seconds
  }
  if (isLit(rgb)) leds.push({ from, to: Math.max(now, show.duration), rgb, name })
  return { number: d.number, leds, stations, end: now }
}

interface Props {
  show: Show
  t: number
  selected: number | null
  onSelect: (n: number | null) => void
  onSeek: (t: number) => void
  onHover: (text: string | null) => void
  /** one more drone (null: the limit is reached) */
  onAdd: (() => void) | null
}

export function Timetable(p: Props) {
  const { show, t, selected, onSelect, onSeek, onHover } = p
  const [rulerRef, ruler] = useSize<HTMLDivElement>()
  const lanes = useMemo(() => show.drones.map((_, i) => buildLane(show, i)), [show])
  const dragging = useRef(false)

  const width = ruler.width
  const duration = show.duration
  const pct = (time: number) => (duration > 0 ? (Math.min(Math.max(time, 0), duration) / duration) * 100 : 0)
  const timeAt = (clientX: number, el: Element) => {
    const r = el.getBoundingClientRect()
    return Math.min(Math.max(((clientX - r.left) / Math.max(r.width, 1)) * duration, 0), duration)
  }

  const hover = (e: PointerEvent<HTMLElement>, index: number) => {
    const d = show.drones[index]
    const time = timeAt(e.clientX, e.currentTarget)
    const step = stepAt(d.steps, d.path, time)
    const [name] = colorAt(d.steps, time)
    onHover(
      `${tr('Дрон {n}', { n: d.number })}, ${seconds(time)} ${tr('с')}: ${step ? tr(stepText(step.kind, step.args)) : tr('нет шагов')}${
        step?.line ? ', ' + tr('строка {n}', { n: step.line }) : ''
      }${name !== 'black' ? ', ' + tr('светодиод {name}', { name }) : ''}`,
    )
  }

  const onKey = (e: KeyboardEvent<HTMLElement>) => {
    const tag = (e.target as HTMLElement).tagName
    if (tag === 'SELECT' || tag === 'INPUT') return
    const big = e.shiftKey ? 10 : 1
    if (e.key === 'ArrowLeft') onSeek(t - big)
    else if (e.key === 'ArrowRight') onSeek(t + big)
    else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      const numbers = show.drones.map((d) => d.number)
      if (numbers.length === 0) return
      const at = selected === null ? -1 : numbers.indexOf(selected)
      const next = e.key === 'ArrowUp' ? Math.max(at - 1, 0) : Math.min(at + 1, numbers.length - 1)
      onSelect(numbers[next])
    } else return
    e.preventDefault()
  }

  // a numeral every 5 s, thinned to 10, 30 or 60 s when the strip is narrow
  const every = [5, 10, 30, 60, 120].find((e) => (duration > 0 ? (e / duration) * width : 99) >= 34) ?? 120
  const ticks: number[] = []
  for (let s = 0; s <= duration + 0.001; s += 5) ticks.push(s)

  const cursor = (
    <div className="tt-cursor-layer" aria-hidden="true">
      <i className="tt-cursor" style={{ left: `${pct(t)}%` }} />
    </div>
  )

  return (
    <section className="tt tt-flat" aria-label={tr('Расписание')} onKeyDown={onKey}>
      <div className="tt-cols" role="row">
        <span className="tt-h tt-h-name" role="columnheader">
          {tr('Борт')}
        </span>
        <div
          className="tt-ruler"
          ref={rulerRef}
          role="columnheader"
          aria-label={tr('Время шоу, секунды')}
          onPointerDown={(e) => {
            dragging.current = true
            e.currentTarget.setPointerCapture(e.pointerId)
            onSeek(timeAt(e.clientX, e.currentTarget))
          }}
          onPointerMove={(e) => dragging.current && onSeek(timeAt(e.clientX, e.currentTarget))}
          onPointerUp={() => (dragging.current = false)}
        >
          {ticks.map((s) => (
            <span key={s} className="tt-tick" data-num={s % every === 0} style={{ left: `${pct(s)}%` }}>
              {s % every === 0 && <b className="num">{s}</b>}
            </span>
          ))}
        </div>
        {cursor}
      </div>

      <div className="tt-scroll" tabIndex={0} role="group" aria-label={tr('Строки расписания: по одной на борт')} aria-describedby="tt-keys">
        <p id="tt-keys" className="sr-only">
          {tr('Тяните по линии или ← → (Shift: по 10 с), ↑ ↓ выбирают борт')}
        </p>
        <div className="tt-rows" role="table" aria-label={tr('Расписание')}>
          {lanes.map((lane, i) => {
            const d = show.drones[i]
            const mine = selected === lane.number
            const [, led] = colorAt(d.steps, t)
            const lit = d.steps.find((s) => s.kind === 'rgb' && isLit(s.args.rgb))
            const ring = isLit(led) ? css(readable(led)) : lit ? css(readable(lit.args.rgb)) : 'var(--faint)'
            return (
              <div key={lane.number} className="tt-row" role="row" data-selected={mine}>
                <button
                  type="button"
                  className="tt-name"
                  role="rowheader"
                  aria-pressed={mine}
                  onClick={() => onSelect(mine ? null : lane.number)}
                  title={tr('Дрон {n}', { n: lane.number })}
                >
                  <span className="tt-bullet num" style={{ borderColor: ring }}>
                    {lane.number}
                  </span>
                  <span>{tr('Дрон {n}', { n: lane.number })}</span>
                </button>

                <div
                  className="tt-strip"
                  role="cell"
                  aria-label={tr('Линия борта {n}', { n: lane.number })}
                  onPointerDown={(e) => {
                    dragging.current = true
                    e.currentTarget.setPointerCapture(e.pointerId)
                    onSeek(timeAt(e.clientX, e.currentTarget))
                  }}
                  onPointerMove={(e) => {
                    hover(e, i)
                    if (dragging.current) onSeek(timeAt(e.clientX, e.currentTarget))
                  }}
                  onPointerUp={() => (dragging.current = false)}
                  onPointerLeave={() => onHover(null)}
                >
                  <i className="tt-track" style={{ width: `${pct(lane.end)}%` }} />
                  {lane.leds.map((seg, k) => {
                    const hot = t >= seg.from && t < seg.to
                    const letter = mine ? colorLetter(seg.name) : ''
                    const wide = ((seg.to - seg.from) / Math.max(duration, 1)) * width > LABEL_MIN_W
                    return (
                      <span key={k}>
                        <i
                          className="tt-seg"
                          style={{
                            left: `${pct(seg.from)}%`,
                            width: `${Math.max(pct(seg.to) - pct(seg.from), 0.3)}%`,
                            background: css(seg.rgb),
                            opacity: mine || hot ? 1 : DIM,
                          }}
                        />
                        {letter && wide && (
                          <b className="tt-letter" style={{ left: `${pct(seg.from)}%` }}>
                            {letter}
                          </b>
                        )}
                      </span>
                    )
                  })}
                  {lane.stations.map((s, k) => (
                    <i key={k} className="tt-station" style={{ left: `${pct(s)}%`, opacity: mine ? 1 : 0.8 }} />
                  ))}
                </div>
              </div>
            )
          })}
          {lanes.length === 0 && <p className="tt-empty">{tr('В шоу нет бортов')}</p>}
          <button
            type="button"
            className="tt-add"
            disabled={!p.onAdd}
            onClick={p.onAdd ?? undefined}
            title={p.onAdd ? tr('Добавить дрона: он встанет на свободную клетку') : tr('Больше бортов добавить нельзя')}
          >
            <Plus size={16} strokeWidth={1.75} aria-hidden="true" />
            {tr('Добавить борт')}
          </button>
          {cursor}
        </div>
      </div>
    </section>
  )
}
