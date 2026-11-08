import { useState } from 'react'
import { ChevronDown, CircleX, Info, TriangleAlert } from 'lucide-react'
import type { Finding } from '@core/checks'
import type { Group } from '@core/groups'
import { seconds } from '../lib/color'
import './SidePanel.css'
import { tr } from '@core/i18n'

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
