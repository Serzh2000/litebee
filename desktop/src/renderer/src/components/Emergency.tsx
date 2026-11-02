import { PlaneLanding } from 'lucide-react'
import './Emergency.css'
import { tr } from '@core/i18n'

/** Always on screen, top right, whatever else is open. Esc does the same. */
export function Emergency({ onPress, compact = false }: { onPress: () => void; compact?: boolean }) {
  return (
    <button type="button" className="emergency" data-compact={compact} onClick={onPress}>
      <PlaneLanding size={compact ? 16 : 20} strokeWidth={2} aria-hidden="true" />
      {tr('Аварийная посадка')}
      <kbd>Esc</kbd>
    </button>
  )
}
