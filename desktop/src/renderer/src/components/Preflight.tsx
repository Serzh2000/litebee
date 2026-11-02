import type { ReactNode } from 'react'
import { Check, Play, ShieldCheck, TriangleAlert, Upload } from 'lucide-react'
import type { PreflightStep } from '../state/preflight'
import './Preflight.css'
import { tr } from '@core/i18n'

/** The four steps before a flight, as a chain. Done: a check; current: filled; next: outlined; blocked: dim. */
/** What a step does when it is pressed, shown in place of its number once it can be pressed. */
const ACTION_ICON: Record<number, ReactNode> = {
  1: <Upload size={12} strokeWidth={2.4} />,
  2: <ShieldCheck size={12} strokeWidth={2.4} />,
  3: <Play size={12} strokeWidth={2.4} />,
}

export function Preflight({ steps, onStep }: { steps: PreflightStep[]; onStep: (i: number) => void }) {
  return (
    <ol className="preflight" aria-label={tr('Порядок подготовки к полёту')}>
      {steps.map((s, i) => {
        const interactive = i === 0 || (i === 1 && s.state === 'current' && s.word === 'можно') || (i === 2 && (s.state === 'current' || s.word === 'взведён')) || (i === 3 && s.state === 'current')
        const reason = s.why ?? (s.state === 'blocked' ? tr('Сначала предыдущие шаги') : undefined)
        return (
          <li key={s.label} className="pf-item">
            <button
              type="button"
              className="pf-step"
              data-state={s.state}
              data-error={s.error ? 'true' : undefined}
              disabled={!interactive}
              aria-disabled={!interactive}
              onClick={interactive ? () => onStep(i) : undefined}
              title={interactive ? tr('Нажмите: {step}', { step: tr(s.label) }) + (s.why ? `. ${tr(s.why)}` : '') : tr(reason ?? s.word)}
            >
              <span className="pf-mark" aria-hidden="true">
                {s.state === 'done' ? (
                  <Check size={13} strokeWidth={2.4} />
                ) : s.error ? (
                  <TriangleAlert size={13} strokeWidth={2.2} />
                ) : interactive && i > 0 ? (
                  ACTION_ICON[i]
                ) : (
                  i + 1
                )}
              </span>
              <span className="pf-label">{tr(s.label)}</span>
              <span className="sr-only">: {tr(s.word)}</span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}
