import { Plus } from 'lucide-react'
import { MAX_DRONES } from '@core/project'
import { colorAt, type Show } from '@core/show'
import { css, isLit, readable } from '../lib/color'
import './FleetRail.css'
import { tr } from '@core/i18n'

interface Props {
  show: Show
  t: number
  selected: number | null
  onSelect: (n: number | null) => void
  onAdd: () => void
}

/** One chip per drone down the left edge: its number, the colour it is lit now, selection. Live battery joins the chip with the link. */
export function FleetRail({ show, t, selected, onSelect, onAdd }: Props) {
  return (
    <nav className="rail" aria-label={tr('Дроны шоу')}>
      {show.drones.map((d) => {
        const [, led] = colorAt(d.steps, t)
        const lit = d.steps.find((s) => s.kind === 'rgb' && isLit(s.args.rgb))
        const identity = lit ? readable(lit.args.rgb) : null
        const on = selected === d.number
        return (
          <button
            key={d.number}
            type="button"
            className="chip"
            data-selected={on}
            aria-pressed={on}
            title={tr('Дрон {n}: нет связи', { n: d.number })}
            onClick={() => onSelect(on ? null : d.number)}
          >
            <span className="chip-num" style={{ borderColor: identity ? css(identity) : 'var(--ink-3)' }}>
              {d.number}
            </span>
            <span className="chip-led" style={{ background: isLit(led) ? css(led) : 'transparent' }} />
          </button>
        )
      })}
      {show.drones.length < MAX_DRONES && (
        <button type="button" className="chip chip-add" onClick={onAdd} title={tr('Добавить дрона: он встанет на свободную клетку')} aria-label={tr('Добавить дрона')}>
          <Plus size={18} strokeWidth={2} aria-hidden="true" />
        </button>
      )}
    </nav>
  )
}
