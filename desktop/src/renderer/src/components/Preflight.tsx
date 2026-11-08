import { Check, TriangleAlert } from 'lucide-react'
import { canPress, type PreflightStep } from '../state/preflight'
import './Preflight.css'
import { tr } from '@core/i18n'

/**
 * The four steps before a flight as one flat segmented stepper: four real buttons in a 1px group. Done: a check; current:
 * ink text over a 2px accent underline; blocked: muted, with the reason in the title and in text for screen readers.
 */
export function Preflight({ steps, onStep }: { steps: PreflightStep[]; onStep: (i: number) => void }) {
  return (
    <ol className="preflight" aria-label={tr('Порядок подготовки к полёту')}>
      {steps.map((s, i) => {
        const interactive = canPress(steps, i)
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
              <span className="pf-mark num" aria-hidden="true">
                {s.state === 'done' ? <Check size={14} strokeWidth={2.4} /> : s.error ? <TriangleAlert size={14} strokeWidth={2.2} /> : i + 1}
              </span>
              <span className="pf-label">{tr(s.label)}</span>
              <span className="sr-only">: {tr(s.word)}</span>
              {!interactive && reason && <span className="sr-only">. {tr(reason)}</span>}
            </button>
          </li>
        )
      })}
    </ol>
  )
}
