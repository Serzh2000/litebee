import { Monitor, Moon, Sun } from 'lucide-react'
import { tr } from '@core/i18n'
import { setThemePref, useTheme, type ThemePref } from '../state/useTheme'
import './LangSwitch.css'

const CHOICES: [ThemePref, typeof Sun, string][] = [
  ['auto', Monitor, 'Как в системе'],
  ['light', Sun, 'Светлая'],
  ['dark', Moon, 'Тёмная'],
]

/** Light, dark, or as the system has it. */
export function ThemeSwitch() {
  const { pref } = useTheme()
  return (
    <div className="lang" role="group" aria-label={tr('Тема')}>
      {CHOICES.map(([id, Icon, name]) => (
        <button key={id} type="button" aria-pressed={pref === id} title={tr(name)} aria-label={tr(name)} onClick={() => setThemePref(id)}>
          <Icon size={14} strokeWidth={1.9} aria-hidden="true" />
        </button>
      ))}
    </div>
  )
}
