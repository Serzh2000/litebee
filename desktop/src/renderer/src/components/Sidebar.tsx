import { useEffect, useRef, useState } from 'react'
import { BookOpen, FolderOpen, Map as MapIcon, Settings2 } from 'lucide-react'
import type { Mode, Project, ProjectActions } from '../App'
import type { Link } from '../state/useLink'
import { LangSwitch } from './LangSwitch'
import { LinkChip } from './LinkChip'
import { Mark } from './Mark'
import { ThemeSwitch } from './ThemeSwitch'
import './Sidebar.css'
import { tr } from '@core/i18n'

interface Props {
  project: Project
  actions: ProjectActions
  mode: Mode
  onMode: (m: Mode) => void
  /** the reference tab of the inspector is open */
  reference: boolean
  onReference: () => void
  link: Link
}

/**
 * The left half of the frame: the product, the project, where to go, and at the bottom the link to the drones with the
 * language and the theme. It folds to icons below 1100 px; every item keeps its name for screen readers and a title.
 */
export function Sidebar({ actions, mode, onMode, reference, onReference, link }: Props) {
  const [settings, setSettings] = useState(false)
  const settingsBox = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!settings) return
    const away = (event: PointerEvent) => {
      if (!settingsBox.current?.contains(event.target as Node)) setSettings(false)
    }
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSettings(false)
    }
    document.addEventListener('pointerdown', away)
    document.addEventListener('keydown', key)
    return () => {
      document.removeEventListener('pointerdown', away)
      document.removeEventListener('keydown', key)
    }
  }, [settings])
  const items = [
    { id: 'map', label: tr('Карта'), icon: MapIcon, current: mode === 'map', run: () => onMode('map') },
    { id: 'ref', label: tr('Справочник'), short: tr('Справка'), icon: BookOpen, current: false, pressed: reference, run: onReference },
    { id: 'home', label: tr('Проекты'), icon: FolderOpen, current: false, run: actions.onHome },
  ]
  return (
    <aside className="sidebar">
      <div className="brand">
        <Mark size={27} />
        <span className="brand-name">Litebee</span>
      </div>
      <nav className="nav" aria-label={tr('Разделы')}>
        {items.map((it) => (
          <button
            key={it.id}
            type="button"
            className="nav-item"
            aria-current={it.current ? 'page' : undefined}
            aria-pressed={it.pressed}
            title={it.label}
            aria-label={it.label}
            onClick={it.run}
          >
            <it.icon size={20} strokeWidth={1.65} aria-hidden="true" />
            <span className="nav-label">{'short' in it ? it.short : it.label}</span>
          </button>
        ))}
      </nav>
      <div className="side-foot">
        <LinkChip link={link} />
        <div className="rail-settings" ref={settingsBox}>
          <button type="button" className="nav-item" aria-label={tr('Настройки')} title={tr('Настройки')} aria-expanded={settings} aria-controls="appearance-settings" onClick={() => setSettings(!settings)}>
            <Settings2 size={20} strokeWidth={1.65} aria-hidden="true" />
            <span className="nav-label">{tr('Вид')}</span>
          </button>
          {settings && <div className="rail-settings-panel" id="appearance-settings">
            <h2>{tr('Тема')}</h2>
            <ThemeSwitch />
            <h2>{tr('Language / Язык')}</h2>
            <LangSwitch />
          </div>}
        </div>
      </div>
    </aside>
  )
}
