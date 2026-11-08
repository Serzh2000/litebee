import './Emergency.css'
import { tr } from '@core/i18n'

/** Always on screen, top right, whatever else is open. Esc does the same. */
export function Emergency({ onPress }: { onPress: () => void }) {
  return (
    <button type="button" className="emergency" onClick={onPress} aria-keyshortcuts="Escape">
      <span>{tr('Аварийная посадка')}</span>
      <kbd>Esc</kbd>
    </button>
  )
}
