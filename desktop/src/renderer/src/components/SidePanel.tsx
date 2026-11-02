import { useState } from 'react'
import { ChevronDown, CircleX, Info, TriangleAlert, WifiOff } from 'lucide-react'
import { colorAt, type Show } from '@core/show'
import type { Finding } from '@core/checks'
import type { Group } from '@core/groups'
import { css, isLit, readable, seconds } from '../lib/color'
import './SidePanel.css'
import { tr } from '@core/i18n'

interface FleetProps {
  show: Show
  t: number
  selected: number | null
  onSelect: (n: number | null) => void
}

/** One row per drone of the show. Live drones (battery, cell, state) join these rows when the link is ported. */
export function Fleet({ show, t, selected, onSelect }: FleetProps) {
  return (
    <section className="panel" aria-labelledby="fleet-title">
      <header className="panel-head">
        <h2 id="fleet-title">{tr('Дроны')}</h2>
        <span className="panel-note">{tr('в шоу {n}, на связи 0', { n: show.drones.length })}</span>
      </header>
      <ul className="rows">
        {show.drones.map((d) => {
          const [, led] = colorAt(d.steps, t)
          const lit = d.steps.find((s) => s.kind === 'rgb' && isLit(s.args.rgb))
          const identity = lit ? readable(lit.args.rgb) : null
          const on = selected === d.number
          return (
            <li key={d.number}>
              <button type="button" className="row fleet-row" data-selected={on} aria-pressed={on} onClick={() => onSelect(on ? null : d.number)}>
                <span className="badge" style={{ borderColor: identity ? css(identity) : 'var(--ink-3)' }}>
                  {d.number}
                  {isLit(led) && <i style={{ background: css(led) }} />}
                </span>
                <span className="row-main">
                  <span className="row-title">{tr('Дрон {n}', { n: d.number })}</span>
                  <span className="row-sub">
                    {tr('{n} шагов, {s} с', { n: d.steps.length, s: seconds(d.duration) })}
                  </span>
                </span>
                <span className="row-state">
                  <WifiOff size={13} strokeWidth={1.75} aria-hidden="true" />
                  {tr('Нет связи')}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

const ICON = { error: CircleX, warn: TriangleAlert, info: Info } as const
const LABEL = { error: 'Ошибка', warn: 'Замечание', info: 'Сведение' } as const // shown through tr()

interface ChecksProps {
  groups: Group[] | null
  stale: boolean
  onJump: (f: Finding) => void
}

const where = (f: Finding): string =>
  [f.drone !== null && tr('дрон {n}', { n: f.drone }), f.t !== null && `${seconds(f.t)} ${tr('с')}`, f.line && tr('строка {n}', { n: f.line })].filter(Boolean).join(', ')

/** The findings of the check, one row per thing said: a row that covers several findings opens to list them. */
export function Checks({ groups, stale, onJump }: ChecksProps) {
  const [open, setOpen] = useState<number | null>(null)
  const count = (level: Finding['level']) => groups?.filter((g) => g.level === level).length ?? 0
  return (
    <section className="panel panel-checks" aria-labelledby="checks-title">
      <header className="panel-head">
        <h2 id="checks-title">{tr('Проверки')}</h2>
        {groups && (
          <span className="panel-note">
            {stale && tr('устарели') + ': '}
            {tr('ошибок {a}, замечаний {b}, сведений {c}', { a: count('error'), b: count('warn'), c: count('info') })}
          </span>
        )}
      </header>
      {!groups ? (
        <p className="empty">{tr('Нажмите «Проверить»: приложение прогонит шоу в симуляции и покажет ошибки, слишком быстрые переходы и сближения дронов.')}</p>
      ) : groups.length === 0 ? (
        <p className="empty">{tr('Замечаний нет.')}</p>
      ) : (
        <ul className="rows" data-stale={stale}>
          {groups.map((g, i) => {
            const Icon = ICON[g.level]
            const many = g.items.length > 1
            const shown = open === i
            return (
              <li key={i}>
                <button
                  type="button"
                  className="row finding"
                  data-level={g.level}
                  aria-expanded={many ? shown : undefined}
                  onClick={() => (many ? setOpen(shown ? null : i) : onJump(g.items[0]))}
                >
                  <Icon size={16} strokeWidth={1.9} aria-label={tr(LABEL[g.level])} />
                  <span className="row-main">
                    <span className="finding-text">{g.title}</span>
                    {g.detail && <span className="row-sub">{g.detail}</span>}
                  </span>
                  {many && (
                    <span className="finding-count">
                      {g.items.length}
                      <ChevronDown size={14} strokeWidth={2} aria-hidden="true" data-open={shown} />
                    </span>
                  )}
                </button>
                {many && shown && (
                  <ul className="finding-items">
                    {g.items.map((f, k) => (
                      <li key={k}>
                        <button type="button" onClick={() => onJump(f)}>
                          {where(f)}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
