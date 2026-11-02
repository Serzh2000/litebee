import { useMemo } from 'react'
import { X } from 'lucide-react'
import { splitDrones } from '@core/sections'
import { colorAt, stepAt, type Show } from '@core/show'
import { css, isLit, readable } from '../lib/color'
import './DroneWindows.css'
import { tr } from '@core/i18n'

interface Props {
  show: Show
  /** the time on the count sheet, in seconds */
  t: number
  source: string
  selected: number | null
  onPick: (n: number) => void
  /** drones whose window the person closed */
  hidden: Set<number>
  onHide: (n: number) => void
}

/** Lines of context above and below the line that runs. */
const AROUND = 1

interface Excerpt {
  /** 1-based number of the first line, in the whole file */
  from: number
  lines: string[]
  /** the index in `lines` of the line that runs; -1 when none does */
  now: number
  state: 'runs' | 'waits' | 'done'
}

/**
 * Windows with the code of each drone, laid on both sides of the mat while the count sheet is scrubbed: the line that
 * runs at that time, with a few lines around it, so the code of every drone can be read at the same moment.
 */
export function DroneWindows({ show, t, source, selected, onPick, hidden, onHide }: Props) {
  const file = useMemo(() => source.split('\n'), [source])
  const split = useMemo(() => splitDrones(source), [source])

  const windows = show.drones
    .filter((d) => !hidden.has(d.number))
    .map((d) => {
      const section = split?.sections.find((s) => s.number === d.number)
      const first = section ? section.line : 1
      const last = section ? section.line + section.lines - 1 : file.length
      const step = stepAt(d.steps, d.path, t)
      const state: Excerpt['state'] = step ? 'runs' : t >= d.duration ? 'done' : 'waits'
      let from = first
      let now = -1
      if (step?.line) {
        from = Math.max(first, step.line - AROUND)
        const to = Math.min(last, step.line + AROUND)
        now = step.line - from
        return { d, ex: { from, lines: file.slice(from - 1, to), now, state } satisfies Excerpt }
      }
      if (state === 'done') from = Math.max(first, last - 2 * AROUND)
      const to = Math.min(last, from + 2 * AROUND)
      return { d, ex: { from, lines: file.slice(from - 1, to), now, state } satisfies Excerpt }
    })

  const half = Math.ceil(windows.length / 2)
  const column = (items: typeof windows, side: 'left' | 'right') => (
    <div className="dwins-col" data-side={side}>
      {items.map(({ d, ex }) => {
        const [, led] = colorAt(d.steps, t)
        const lit = isLit(led)
        const tail = ex.state === 'waits' ? tr('ждёт начала') : ex.state === 'done' ? tr('закончил') : null
        return (
          <section key={d.number} className="dwin" data-selected={selected === d.number} aria-label={tr('Код дрона {n}', { n: d.number })}>
            <header onClick={() => onPick(d.number)}>
              <span className="dwin-num" style={{ borderColor: lit ? css(readable(led)) : 'var(--ink-3)' }}>
                {d.number}
              </span>
              <span className="dwin-state">{tail ?? tr('строка {n}', { n: ex.from + ex.now })}</span>
              <span className="dwin-led" style={{ background: lit ? css(led) : 'transparent' }} aria-hidden="true" />
              <button
                type="button"
                className="dwin-close"
                aria-label={tr('Закрыть окно дрона {n}', { n: d.number })}
                onClick={(e) => {
                  e.stopPropagation()
                  onHide(d.number)
                }}
              >
                <X size={12} strokeWidth={2.2} />
              </button>
            </header>
            <div className="dwin-code">
              {ex.lines.map((text, i) => (
                <div key={ex.from + i} className="dwin-line" data-now={i === ex.now}>
                  <span className="dwin-n">{ex.from + i}</span>
                  <code>{text || ' '}</code>
                </div>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )

  if (windows.length === 0) return null
  return (
    <div className="dwins">
      {column(windows.slice(0, half), 'left')}
      {column(windows.slice(half), 'right')}
    </div>
  )
}
