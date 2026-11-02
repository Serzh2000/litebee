import { FilePlus2, FolderOpen } from 'lucide-react'
import { getLang, plural, tr } from '@core/i18n'
import { SHOWS } from '../data/shows'
import { baseName } from '../lib/files'
import { recents } from '../lib/recent'
import { useLink } from '../state/useLink'
import { LangSwitch } from './LangSwitch'
import { ThemeSwitch } from './ThemeSwitch'
import { Mark } from './Mark'
import './StartScreen.css'

interface Props {
  onWizard: () => void
  onOpen: () => void
  onOpenRecent: (path: string) => void
  onExample: (id: string) => void
  /** back to the project that is open now */
  onContinue: () => void
  projectName: string
}

/** A few shows that show what the app does, from one drone to ten. */
const FEATURED = ['quarter_traffic', 'quarter_pair_cross', 'quarter_square', 'quarter_five_cross', 'quarter_eight_carousel', 'my_dream']

const droneCount = (n: number) => `${n} ${plural(n, ['дрон', 'дрона', 'дронов'], ['drone', 'drones'])}`

/** The first thing the person sees: start a project, open one, pick up where they stopped, or look at an example. */
export function StartScreen({ onWizard, onOpen, onOpenRecent, onExample, onContinue, projectName }: Props) {
  const link = useLink()
  const recent = recents()
  const featured = FEATURED.map((id) => SHOWS.find((s) => s.id === id)).filter((s): s is NonNullable<typeof s> => Boolean(s))
  const day = (at: number) => new Date(at).toLocaleDateString(getLang() === 'ru' ? 'ru-RU' : 'en-GB', { day: 'numeric', month: 'short' })
  const alive = link.drones.filter((d) => !d.lost && d.silentMs < 3000).length

  return (
    <div className="start" role="dialog" aria-label={tr('Начало работы')}>
      <div className="start-grid">
        <section className="start-main">
          <div className="start-brand">
            <Mark size={34} />
            <div>
              <h1>Litebee IDE</h1>
              <p>{tr('Шоу для дронов LiteBee Wing: пишите на Python, смотрите на карте, запускайте.')}</p>
            </div>
          </div>

          <div className="start-actions">
            <button type="button" className="start-primary" onClick={onWizard} autoFocus>
              <FilePlus2 size={20} strokeWidth={1.8} aria-hidden="true" />
              <span>
                <b>{tr('Новый проект')}</b>
                <small>{tr('Из примера, с подбором по фильтрам, или с пустого шоу')}</small>
              </span>
            </button>
            <button type="button" className="start-secondary" onClick={onOpen}>
              <FolderOpen size={20} strokeWidth={1.8} aria-hidden="true" />
              <span>
                <b>{tr('Открыть файл…')}</b>
                <small>{tr('Шоу на Python, файл .py')}</small>
              </span>
              <kbd>Ctrl O</kbd>
            </button>
          </div>

          {projectName && (
            <button type="button" className="start-continue" onClick={onContinue}>
              {tr('Продолжить: {name}', { name: tr(projectName) })}
            </button>
          )}
        </section>

        <section className="start-side">
          <h2>{tr('Недавние')}</h2>
          {recent.length > 0 ? (
            <ul>
              {recent.map((r) => (
                <li key={r.path}>
                  <button type="button" onClick={() => onOpenRecent(r.path)} title={r.path}>
                    <span>{r.name || baseName(r.path)}</span>
                    <small>{day(r.at)}</small>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="start-empty">{tr('Здесь появятся проекты, которые вы откроете или сохраните.')}</p>
          )}

          <h2>{tr('Примеры для начала')}</h2>
          <ul>
            {featured.map((s) => (
              <li key={s.id}>
                <button type="button" onClick={() => onExample(s.id)}>
                  <span>{tr(s.title)}</span>
                  <small>
                    {droneCount(s.drones)}
                    {s.seconds ? ` · ${s.seconds} ${tr('с')}` : ''}
                  </small>
                </button>
              </li>
            ))}
          </ul>
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
