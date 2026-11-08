import { useEffect, useMemo, useRef, useState } from 'react'
import { useModalFocus } from '../state/useModalFocus'
import { Search, X } from 'lucide-react'
import {
  AREA_NAME,
  countFor,
  filterCatalog,
  isFiltered,
  LENGTH_NAME,
  NO_FILTERS,
  options,
  toggle,
  type Area,
  type Filters,
  type Length,
} from '@core/catalog'
import { MAX_DRONES } from '@core/project'
import { CATALOG } from '../data/shows'
import { ShowThumb } from './ShowThumb'
import './NewProjectWizard.css'
import { plural, tr } from '@core/i18n'

interface Props {
  onCancel: () => void
  onBlank: (name: string, drones: number) => void
  onExample: (id: string) => void
  /** the tab it opens on */
  initialTab?: 'example' | 'blank'
}

const droneWord = (n: number) => plural(n, ['дрон', 'дрона', 'дронов'], ['drone', 'drones'])
const FEATURE_HINT: Record<string, string> = {
  'Только свет': 'Дроны висят на месте, меняется только цвет',
  Перемещения: 'Дроны летают с клетки на клетку',
  'Разная высота': 'Высоты различаются на 50 см и больше',
  'Круги circle': 'Есть шаги circle: на дроне круг идёт дольше, чем в симуляции',
  'Проверенные шаги': 'Только шаги, которые уже летали на живом дроне',
}
const AREAS: Area[] = ['quarter', 'full']
const LENGTHS: Length[] = ['short', 'middle', 'long']

/** The new-project wizard: start from an example found with filters, or from an empty project. */
export function NewProjectWizard({ onCancel, onBlank, onExample, initialTab = 'example' }: Props) {
  const dialog = useRef<HTMLDivElement>(null)
  useModalFocus(dialog)
  const [tab, setTab] = useState<'example' | 'blank'>(initialTab)
  const [filters, setFilters] = useState<Filters>(NO_FILTERS)
  const [picked, setPicked] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [count, setCount] = useState('4')

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && (e.stopPropagation(), onCancel())
    window.addEventListener('keydown', esc, true)
    return () => window.removeEventListener('keydown', esc, true)
  }, [onCancel])

  const opts = useMemo(() => options(CATALOG), [])
  const shown = useMemo(() => filterCatalog(CATALOG, filters), [filters])
  // The pick goes away with the filters that hid it.
  const current = shown.find((s) => s.id === picked) ?? null

  const n = Number(count)
  const validCount = Number.isInteger(n) && n >= 1 && n <= MAX_DRONES

  const Chip = ({ group, value, label, hint }: { group: Exclude<keyof Filters, 'query'>; value: string | number; label: string; hint?: string }) => {
    const on = (filters[group] as unknown[]).includes(value)
    const total = countFor(CATALOG, filters, group, value)
    return (
      <button
        type="button"
        className="wz-chip"
        aria-pressed={on}
        disabled={!on && total === 0}
        title={hint}
        onClick={() => setFilters((f) => toggle(f, group, value as never))}
      >
        {label}
        <small>{on ? '' : total}</small>
      </button>
    )
  }

  return (
    <div className="scrim" onMouseDown={onCancel}>
      <div className="wizard" ref={dialog} data-tab={tab} role="dialog" aria-modal="true" aria-label={tr('Новый проект')} onMouseDown={(e) => e.stopPropagation()}>
        <header className="wz-head">
          <h2>{tr('Новый проект')}</h2>
          <div className="wz-tabs" role="tablist">
            <button type="button" role="tab" aria-selected={tab === 'example'} onClick={() => setTab('example')}>
              {tr('Из примера')}
            </button>
            <button type="button" role="tab" aria-selected={tab === 'blank'} onClick={() => setTab('blank')}>
              {tr('Пустой проект')}
            </button>
          </div>
          <button type="button" className="wz-close" aria-label={tr('Закрыть')} onClick={onCancel}>
            <X size={18} strokeWidth={2} />
          </button>
        </header>

        {tab === 'example' ? (
          <>
            <div className="wz-body">
              <aside className="wz-filters" aria-label={tr('Фильтры')}>
                <fieldset>
                  <legend>{tr('Карта')}</legend>
                  <div className="wz-chips">
                    {AREAS.map((a) => (
                      <Chip key={a} group="areas" value={a} label={AREA_NAME[a]} hint={tr(a === 'quarter' ? 'Одна четверть коврика, 6 × 6 клеток' : 'Весь коврик, 12 × 12 клеток')} />
                    ))}
                  </div>
                </fieldset>
                <fieldset>
                  <legend>{tr('Сколько дронов')}</legend>
                  <div className="wz-chips">
                    {opts.drones.map((d) => (
                      <Chip key={d} group="drones" value={d} label={String(d)} />
                    ))}
                  </div>
                </fieldset>
                <fieldset>
                  <legend>{tr('Тема')}</legend>
                  <div className="wz-chips">
                    {opts.themes.map((t) => (
                      <Chip key={t} group="themes" value={t} label={tr(t)} />
                    ))}
                  </div>
                </fieldset>
                <fieldset>
                  <legend>{tr('Длительность')}</legend>
                  <div className="wz-chips">
                    {LENGTHS.map((l) => (
                      <Chip key={l} group="lengths" value={l} label={tr(LENGTH_NAME[l])} />
                    ))}
                  </div>
                </fieldset>
                <fieldset>
                  <legend>{tr('Особенности')}</legend>
                  <div className="wz-chips">
                    {opts.features.map((t) => (
                      <Chip key={t} group="features" value={t} label={tr(t)} hint={tr(FEATURE_HINT[t])} />
                    ))}
                  </div>
                </fieldset>
              </aside>

              <section className="wz-results" aria-label={tr('Примеры')}>
                <div className="wz-bar">
                  <label className="wz-search">
                    <Search size={15} strokeWidth={1.9} aria-hidden="true" />
                    <input
                      type="search"
                      placeholder={tr('Найти по названию: круг, волна, свет…')}
                      value={filters.query}
                      onChange={(e) => setFilters((f) => ({ ...f, query: e.target.value }))}
                    />
                  </label>
                  <span className="wz-count" role="status">
                    {tr('Найдено {a} из {b}', { a: shown.length, b: CATALOG.length })}
                  </span>
                  {isFiltered(filters) && (
                    <button type="button" className="wz-reset" onClick={() => setFilters(NO_FILTERS)}>
                      {tr('Сбросить')}
                    </button>
                  )}
                </div>
                <ul className="wz-list">
                  {shown.map((s) => (
                    <li key={s.id}>
                      <button
                        type="button"
                        className="wz-row"
                        data-selected={current?.id === s.id}
                        aria-pressed={current?.id === s.id}
                        onClick={() => setPicked(s.id)}
                        onDoubleClick={() => onExample(s.id)}
                      >
                        <ShowThumb id={s.id} size={s.area === 'full' ? 12 : 6} />
                        <span className="wz-title">{tr(s.title)}</span>
                        <span className="wz-note">{tr(s.note)}</span>
                        <span className="wz-meta">
                          <b>{AREA_NAME[s.area]}</b>
                          <span>
                            {s.drones} {droneWord(s.drones)}
                          </span>
                          <span>{s.seconds} {tr('с')}</span>
                          {s.tags.includes('Круги circle') && <em title={tr(FEATURE_HINT['Круги circle'])}>circle</em>}
                          {s.tags.includes('Только свет') && <em>{tr('свет')}</em>}
                        </span>
                      </button>
                    </li>
                  ))}
                  {shown.length === 0 && (
                    <li className="wz-empty">
                      {tr('Ничего не подошло. Уберите один из фильтров')}
                      {isFiltered(filters) && (
                        <>
                          {' '}
                          {tr('или')}{' '}
                          <button type="button" onClick={() => setFilters(NO_FILTERS)}>
                            {tr('сбросьте все')}
                          </button>
                        </>
                      )}
                      .
                    </li>
                  )}
                </ul>
              </section>
            </div>
            <footer className="wz-foot">
              <span className="wz-pick">{current ? tr('Выбрано: {name}', { name: tr(current.title) }) : tr('Выберите пример слева или откройте вкладку «Пустой проект»')}</span>
              <button type="button" className="secondary" onClick={onCancel}>
                {tr('Отмена')}
              </button>
              <button type="button" className="primary" disabled={!current} onClick={() => current && onExample(current.id)}>
                {tr('Создать из примера')}
              </button>
            </footer>
          </>
        ) : (
          <form
            noValidate
            className="wz-blank"
            onSubmit={(e) => {
              e.preventDefault()
              if (validCount) onBlank(name, n)
            }}
          >
            <label htmlFor="np-name">{tr('Название')}</label>
            <input id="np-name" value={name} placeholder={tr('Новый проект')} autoFocus onChange={(e) => setName(e.target.value)} />

            <span className="wz-label" id="np-count-label">
              {tr('Сколько дронов')}
            </span>
            <div className="wz-count-chips" role="radiogroup" aria-labelledby="np-count-label">
              {Array.from({ length: MAX_DRONES }, (_, i) => i + 1).map((k) => (
                <button key={k} type="button" role="radio" aria-checked={n === k} onClick={() => setCount(String(k))}>
                  {k}
                </button>
              ))}
            </div>

            <p className="wz-note">{tr('Каждый дрон получит калибровку, взлёт на 100 см, цвет и посадку. Дальше шаги добавляются в редакторе.')}</p>
            <p className="wz-note">{tr('Каждый дрон стоит на своей клетке: её можно поменять на карте, выбрав дрона. Добавить ещё одного можно в любой момент кнопкой «+».')}</p>
            <div className="dialog-actions">
              <button type="button" className="secondary" onClick={onCancel}>
                {tr('Отмена')}
              </button>
              <button type="submit" className="primary">
                {tr('Создать проект')}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
