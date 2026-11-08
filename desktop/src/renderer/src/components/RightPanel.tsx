import type { ReactNode } from 'react'
import './RightPanel.css'
import { tr } from '@core/i18n'

export type Tab = 'score' | 'code' | 'fleet' | 'checks' | 'ref'

const TABS: { id: Tab; label: string }[] = [
  { id: 'score', label: 'Партитура' },
  { id: 'code', label: 'Код' },
  { id: 'fleet', label: 'Борты' },
  { id: 'checks', label: 'Проверки' },
  { id: 'ref', label: 'Справочник' },
]

interface Props {
  tab: Tab
  onTab: (t: Tab) => void
  /** the show time: play, speed, the scrubber; it stays in view on every tab */
  transport: ReactNode
  score: ReactNode
  code: ReactNode
  fleet: ReactNode
  checks: ReactNode
  reference: ReactNode
  /** drones on the link, a number on the third tab */
  fleetCount: number
}

/**
 * The right three fifths of the work: one window with its tabs in one row, the score (the drones over time), the code of the
 * picked drone, the fleet (the real drones on the link), the checks and the reference. The show time above the tabs is shared.
 */
export function RightPanel({ tab, onTab, transport, score, code, fleet, checks, reference, fleetCount }: Props) {
  return (
    <section className="rp" aria-label={tr('Партитура, код, борты, проверки и справочник')}>
      <div className="rp-head">{transport}</div>
      <div className="rp-tabs" role="tablist">
        {TABS.map((x) => (
          <button key={x.id} type="button" role="tab" aria-selected={tab === x.id} onClick={() => onTab(x.id)}>
            {tr(x.label)}
            {x.id === 'fleet' && fleetCount > 0 && <span className="rp-count num">{fleetCount}</span>}
          </button>
        ))}
      </div>
      <div className="rp-body" role="tabpanel">
        {tab === 'score' ? score : tab === 'code' ? code : tab === 'fleet' ? fleet : tab === 'checks' ? checks : reference}
      </div>
    </section>
  )
}
