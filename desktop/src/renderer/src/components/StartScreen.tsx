import { FilePlus2, FolderOpen } from 'lucide-react'
import { useRef } from 'react'
import { useModalFocus } from '../state/useModalFocus'
import { getLang, tr } from '@core/i18n'
import { baseName } from '../lib/files'
import { recents } from '../lib/recent'
import { useLink } from '../state/useLink'
import { LangSwitch } from './LangSwitch'
import { ThemeSwitch } from './ThemeSwitch'
import { Mark } from './Mark'
import { ShowThumb } from './ShowThumb'
import './StartScreen.css'

interface Props {
  inactive: boolean
  /** the wizard of a new project, opened on its blank tab or on the examples */
  onWizard: (tab: 'example' | 'blank') => void
  onOpen: () => void
  onOpenRecent: (path: string) => void
  onExample: (id: string) => void
  /** back to the project that is open now */
  onContinue: () => void
  projectName: string
}

/** The show the example card pictures: eight drones in a ring, the most readable thumbnail of the kit. */
const PICTURED = 'quarter_eight_carousel'

/** The first thing the person sees: three ways to begin, and below them the projects opened lately. */
export function StartScreen({ onWizard, onOpen, onOpenRecent, onContinue, projectName, inactive }: Props) {
  const dialog = useRef<HTMLDivElement>(null)
  useModalFocus(dialog, !inactive)
  const link = useLink()
  const recent = recents()
  const day = (at: number) => new Date(at).toLocaleDateString(getLang() === 'ru' ? 'ru-RU' : 'en-GB', { day: 'numeric', month: 'long' })
  const alive = link.drones.filter((d) => !d.lost && d.silentMs < 3000).length

  return (
    <div className="start" ref={dialog} role="dialog" aria-modal="true" inert={inactive} aria-label={tr('Начало работы')}>
      <div className="start-page">
        <header className="start-brand">
          <Mark size={34} />
          <div>
            <h1>Litebee IDE</h1>
            <p>{tr('Шоу для дронов LiteBee Wing: пишите на Python, смотрите на карте, запускайте.')}</p>
          </div>
        </header>

        <section aria-label={tr('С чего начать')}>
          <h2>{tr('С чего начать')}</h2>
          <div className="start-cards">
            <button type="button" className="start-card" onClick={() => onWizard('blank')} autoFocus>
              <span className="start-art">
                <FilePlus2 size={36} strokeWidth={1.4} aria-hidden="true" />
              </span>
              <b>{tr('Создать проект с нуля')}</b>
              <small>{tr('Пустое шоу: вы выбираете число дронов, а шаги пишете сами.')}</small>
            </button>
            <button type="button" className="start-card" onClick={() => onWizard('example')}>
              <span className="start-art">
                <ShowThumb id={PICTURED} size={6} />
              </span>
              <b>{tr('Взять встроенный пример')}</b>
              <small>{tr('Готовые шоу на 2–10 дронов: выберите по числу дронов, теме и длине.')}</small>
            </button>
            <button type="button" className="start-card" onClick={onOpen}>
              <span className="start-art">
                <FolderOpen size={36} strokeWidth={1.4} aria-hidden="true" />
              </span>
              <b>{tr('Загрузить файл с компьютера')}</b>
              <small>
                {tr('Шоу на Python, файл .py.')} <kbd>Ctrl O</kbd>
              </small>
            </button>
          </div>
        </section>

        <section aria-label={tr('Недавние')}>
          <h2>{tr('Недавние')}</h2>
          {recent.length > 0 || projectName ? (
            <ul className="start-recent">
              {projectName && (
                <li>
                  <button type="button" className="start-card start-small" onClick={onContinue}>
                    <b>{tr(projectName)}</b>
                    <small>{tr('Открыт сейчас')}</small>
                    <span className="start-go">{tr('Продолжить')}</span>
                  </button>
                </li>
              )}
              {recent.map((r) => (
                <li key={r.path}>
                  <button type="button" className="start-card start-small" onClick={() => onOpenRecent(r.path)} title={r.path}>
                    <b>{r.name || baseName(r.path)}</b>
                    <small>{day(r.at)}</small>
                    <span className="start-go">{tr('Открыть')}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="start-empty">{tr('Здесь появятся проекты, которые вы откроете или сохраните.')}</p>
          )}
        </section>
      </div>

      <footer className="start-foot">
        <span className="start-link" data-on={alive > 0}>
          <i aria-hidden="true" />
          {alive > 0
            ? tr('Дронов на связи: {n}', { n: alive })
            : link.available
              ? tr('Дроны не подключены: включите их, и они найдут компьютер')
              : tr('Связь с дронами работает в приложении для компьютера')}
        </span>
        <span className="start-switches">
          <ThemeSwitch />
          <LangSwitch />
        </span>
      </footer>
    </div>
  )
}
