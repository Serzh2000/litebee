import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import type { Project, ProjectActions } from '../App'
import { baseName } from '../lib/files'
import { LangSwitch } from './LangSwitch'
import { ThemeSwitch } from './ThemeSwitch'
import './ProjectMenu.css'
import { tr } from '@core/i18n'

/** The project in the top bar: its name and file, and the menu to create, open and save projects. */
export function ProjectMenu({ project, actions }: { project: Project; actions: ProjectActions }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', away)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', away)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  const run = (f: () => void) => () => {
    setOpen(false)
    f()
  }

  return (
    <div className="project" ref={box}>
      <button type="button" className="project-button" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((o) => !o)}>
        <span className="project-text">
          <span className="project-name">{tr(project.data.name)}</span>
          <span className="project-file">{project.path
              ? baseName(project.path) + (project.saved ? '' : ' · ' + tr('изменён'))
              : project.saved
                ? tr('пример, не сохранён в файл')
                : tr('не сохранён')}</span>
        </span>
        <ChevronDown size={16} strokeWidth={1.9} aria-hidden="true" />
      </button>

      {open && (
        <div className="menu" role="menu" aria-label={tr('Проект')}>
          <button type="button" role="menuitem" onClick={run(actions.onWizard)}>
            {tr('Новый проект…')}
          </button>
          <button type="button" role="menuitem" onClick={run(actions.onHome)}>
            {tr('Начальный экран')}
          </button>
          <button type="button" role="menuitem" onClick={run(actions.onOpen)}>
            {tr('Открыть…')}<kbd>Ctrl O</kbd>
          </button>
          <button type="button" role="menuitem" onClick={run(() => actions.onSave(false))}>
            {tr('Сохранить')}<kbd>Ctrl S</kbd>
          </button>
          <button type="button" role="menuitem" onClick={run(() => actions.onSave(true))}>
            {tr('Сохранить как…')}<kbd>Ctrl Shift S</kbd>
          </button>
          <div className="menu-lang">
            <span>{tr('Язык')}</span>
            <LangSwitch />
          </div>
          <div className="menu-lang">
            <span>{tr('Тема')}</span>
            <ThemeSwitch />
          </div>
        </div>
      )}

    </div>
  )
}
