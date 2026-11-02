import { stepText } from '@core/labels'
import { colorAt, positionAt, stepAt, type Show } from '@core/show'
import './Readout.css'
import { tr } from '@core/i18n'

interface Props {
  show: Show
  t: number
  selected: number | null
  hoverCell: number | null
  /** beside the code: only what the pointer or the selection says, without the standing hints */
  compact?: boolean
  /** the cell the selected drone starts on, and the way to move it by a click on the map */
  start: number | null
  placing: boolean
  onPlace: () => void
}

/** Plain text beside the chart: what the pointer is on, or what the selected drone is doing right now. */
export function Readout({ show, t, selected, hoverCell, compact = false, start, placing, onPlace }: Props) {
  const drone = selected === null ? null : show.drones.find((d) => d.number === selected) ?? null
  const lines: string[] = []

  if (drone) {
    const step = stepAt(drone.steps, drone.path, t)
    const [name, rgb] = colorAt(drone.steps, t)
    const z = positionAt(drone.path, t)[2]
    const now = step ? drone.steps.indexOf(step) : -1
    const moves = drone.steps.map((s, i) => (s.kind === 'code' || s.kind === 'code_z' ? i : -1)).filter((i) => i >= 0)
    const reached = moves.filter((i) => i <= now).length // moves started so far, the one under way included
    lines.push(step ? tr(stepText(step.kind, step.args)) : tr('нет шагов'))
    lines.push(tr('высота {z} см', { z: Math.round(z) }))
    if (rgb[0] + rgb[1] + rgb[2] > 0) lines.push(tr('светодиод {name}', { name }))
    if (moves.length) lines.push(tr('переход {a} из {b}', { a: reached, b: moves.length }))
  }

  const row = hoverCell === null ? null : Math.floor(hoverCell / 12)
  const col = hoverCell === null ? null : hoverCell % 12

  if (compact && !drone && hoverCell === null) return null

  return (
    <div className="readout" aria-live="polite">
      {drone ? (
        <>
          <h2>{tr('Дрон {n}', { n: drone.number })}</h2>
          {lines.map((l) => (
            <p key={l}>{l}</p>
          ))}
          <p className="start-cell">
            <span>{start === null ? tr('Стартовой клетки нет') : tr('Стоит на клетке {n}', { n: start })}</span>
            <button type="button" onClick={onPlace} aria-pressed={placing}>
              {placing ? tr('Нажмите клетку на карте') : tr('Поставить на другую клетку')}
            </button>
          </p>
        </>
      ) : (
        <h2>{tr('Все дроны')}</h2>
      )}
      {hoverCell !== null && (
        <p className="cell">
          <strong>{tr('Клетка {n}', { n: hoverCell })}</strong>
          <span>
            {tr('строка {row}, столбец {col}', { row: row ?? 0, col: col ?? 0 })}
          </span>
          <span>
            {tr('y {y} см, x {x} см', { y: (row ?? 0) * 40, x: (col ?? 0) * 40 })}
          </span>
        </p>
      )}
      {!drone && hoverCell === null && <p className="muted">{tr('Щёлкните по дрону, чтобы выделить его.')}</p>}
    </div>
  )
}
