import type { ReactNode } from 'react'
import { MapPin } from 'lucide-react'
import { cellFromXY, colorAt, positionAt, stepAt, type Show } from '@core/show'
import { css, isLit, readable } from '../lib/color'
import './Inspector.css'
import { tr } from '@core/i18n'

interface Props {
  show: Show
  t: number
  selected: number | null
  hoverCell: number | null
  /** the cell the selected drone starts on, and the way to move it by a click on the map */
  start: number | null
  placing: boolean
  onPlace: () => void
  notice: string
  /** the editor of the selected drone's program */
  editor: ReactNode
}

/**
 * The inspector, a 320 px card beside the map: the selected drone (its line bullet, the cell it stands on, the placement,
 * its facts at this second, the three lines of its code around the current one) over two tabs, the checks and the reference.
 */
export function Inspector({ show, t, selected, hoverCell, start, placing, onPlace, notice, editor }: Props) {
  const drone = selected === null ? null : (show.drones.find((d) => d.number === selected) ?? null)

  let body = null
  if (drone) {
    const step = stepAt(drone.steps, drone.path, t)
    const [name, rgb] = colorAt(drone.steps, t)
    const [x, y, z] = positionAt(drone.path, t)
    const here = cellFromXY(x, y)
    const index = step ? drone.steps.indexOf(step) : -1
    const moves = drone.steps.map((s, i) => (s.kind === 'code' || s.kind === 'code_z' ? i : -1)).filter((i) => i >= 0)
    const reached = moves.filter((i) => i <= index).length // moves started so far, the one under way included
    const target = step && (step.kind === 'code' || step.kind === 'code_z') ? (step.args.cell as number) : null
    const lit = drone.steps.find((s) => s.kind === 'rgb' && isLit(s.args.rgb))
    const ring = isLit(rgb) ? css(readable(rgb)) : lit ? css(readable(lit.args.rgb)) : 'var(--faint)'
    const facts: [string, string][] = [
      [tr('К клетке'), target === null ? '—' : String(target)],
      [tr('Высота'), `${Math.round(z)} ${tr('см')}`],
      [tr('Светодиод'), isLit(rgb) ? name : '—'],
      [tr('Переход'), moves.length ? tr('{a} из {b}', { a: reached, b: moves.length }) : '—'],
    ]
    body = (
      <section className="insp-drone" aria-live="polite">
        <header className="insp-head">
          <span className="tt-bullet num" style={{ borderColor: ring }}>
            {drone.number}
          </span>
          <h2>{tr('Дрон {n}', { n: drone.number })}</h2>
          <span className="insp-cell num">{here === null ? tr('вне коврика') : tr('клетка {n}', { n: here })}</span>
        </header>

        <div className="insp-place">
          <p>
            {start === null
              ? tr('У дрона {n} нет стартовой клетки. Нажмите клетку на карте.', { n: drone.number })
              : tr('Дрон {n} стоит на клетке {c}. Перетащите его на карте или нажмите клетку.', { n: drone.number, c: start })}
          </p>
          <button type="button" className="btn" onClick={onPlace} aria-pressed={placing}>
            <MapPin size={16} strokeWidth={1.75} aria-hidden="true" />
            {placing ? tr('Нажмите клетку на карте') : tr('Выбрать клетку')}
          </button>
        </div>

        <dl className="insp-facts">
          {facts.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd className="num">{v}</dd>
            </div>
          ))}
        </dl>

        <div className="insp-editor">{editor}</div>
      </section>
    )
  } else {
    const row = hoverCell === null ? null : Math.floor(hoverCell / 12)
    const col = hoverCell === null ? null : hoverCell % 12
    body = (
      <section className="insp-drone" aria-live="polite">
        <p className="insp-none">{tr('Выберите дрона на карте или в расписании: откроется его программа. Дрона можно перетащить на другую клетку.')}</p>
        {hoverCell !== null && (
          <p className="insp-hover">
            <strong>{tr('Клетка {n}', { n: hoverCell })}</strong>
            <span>{tr('строка {row}, столбец {col}', { row: row ?? 0, col: col ?? 0 })}</span>
            <span>{tr('y {y} см, x {x} см', { y: (row ?? 0) * 40, x: (col ?? 0) * 40 })}</span>
          </p>
        )}
      </section>
    )
  }

  return (
    <aside className="insp" aria-label={tr('Инспектор')}>
      <div className="insp-scroll">
        {body}
        {drone && hoverCell !== null && (
          <p className="insp-hover">
            <strong>{tr('Клетка {n}', { n: hoverCell })}</strong>
            <span>{tr('строка {row}, столбец {col}', { row: Math.floor(hoverCell / 12), col: hoverCell % 12 })}</span>
          </p>
        )}
      </div>
      <p className="notice" role="status" aria-live="assertive">
        {notice}
      </p>
    </aside>
  )
}
