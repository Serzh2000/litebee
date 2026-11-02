import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import data from '../data/reference.json'
import './Reference.css'
import { tr } from '@core/i18n'

interface Entry {
  owner: string
  name: string
  signature: string
  summary: string
  topic: string
  status: string
  icon: string
  params: { name: string; unit: string; text: string }[]
  example: string
  context: string
  notes: string[]
}

const ENTRIES = data.entries as Entry[]
const HINT = data.statusHint as Record<string, string>
const norm = (s: string) => s.toLowerCase().replace(/ё/g, 'е')

/** The command reference of the Python DSL (exported from litebee/reference.py): search, details, insert an example. */
export function Reference({ onInsert }: { onInsert: (code: string) => void }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState<string | null>('Drone.takeoff')

  const shown = useMemo(() => {
    const q = norm(query.trim())
    return q ? ENTRIES.filter((e) => norm(`${e.name} ${e.signature} ${e.summary}`).includes(q)) : ENTRIES
  }, [query])

  return (
    <section className="ref" aria-label={tr('Справочник команд')}>
      <details className="ref-time">
        <summary>{tr('Как течёт время в шоу')}</summary>
        <ul>
          <li>{tr('У каждого дрона своё время с 0 секунд. Его шаги идут по порядку сверху вниз, один за другим.')}</li>
          <li>
            {tr('Число в команде — сколько длится шаг.')} <code>d.code(25, 4)</code>: {tr('4 секунды лететь к клетке 25 с постоянной скоростью. Скорость получается из расстояния и секунд.')}
          </li>
          <li>
            {tr('Подождать можно командой на месте:')} <code>d.set_z(100, 3)</code> {tr('на той же высоте — дрон висит 3 секунды.')}
          </li>
          <li>
            <code>rgb</code> {tr('занимает 0 секунд: цвет меняется в тот момент, когда до него дошла очередь. Посадка в симуляции — 3 секунды.')}
          </li>
          <li>
            {tr('Общих часов у дронов нет: после «Старт» каждый идёт по своему списку. Чтобы два дрона встретились в одно время, суммы секунд у них до этого места должны совпасть.')}
          </li>
          <li>{tr('Длина шоу — время самого долгого дрона. Время на карте и в партитуре одно: тяните по партитуре, и код подсветит строки.')}</li>
        </ul>
      </details>
      <label className="ref-search">
        <Search size={15} strokeWidth={1.9} aria-hidden="true" />
        <input type="search" placeholder={tr('Найти команду: взлёт, круг, цвет…')} value={query} onChange={(e) => setQuery(e.target.value)} />
      </label>
      <div className="ref-list">
        {data.topics.map((topic) => {
          const items = shown.filter((e) => e.topic === topic.id)
          if (!items.length) return null
          return (
            <div key={topic.id}>
              <h3 className="ref-topic">{tr(topic.title)}</h3>
              <ul>
                {items.map((e) => {
                  const key = `${e.owner}.${e.name}`
                  const on = open === key
                  return (
                    <li key={key}>
                      <button type="button" className="ref-row" aria-expanded={on} onClick={() => setOpen(on ? null : key)}>
                        <code>{e.signature}</code>
                        <span className="ref-sum">{tr(e.summary)}</span>
                        <span className="ref-status" title={tr(HINT[e.status])} data-sim={e.status !== 'проверено на дроне' && e.owner === 'Drone'}>
                          {e.icon} {tr(e.status)}
                        </span>
                      </button>
                      {on && (
                        <div className="ref-body">
                          {e.params.length > 0 && (
                            <dl>
                              {e.params.map((p) => (
                                <div key={p.name}>
                                  <dt>
                                    {p.name} <span>{tr(p.unit)}</span>
                                  </dt>
                                  <dd>{tr(p.text)}</dd>
                                </div>
                              ))}
                            </dl>
                          )}
                          {e.notes.map((n) => (
                            <p key={n} className="ref-note">
                              {tr(n)}
                            </p>
                          ))}
                          {e.example && (
                            <>
                              <pre>{tr(e.example)}</pre>
                              {e.context !== 'full' && (
                                <button type="button" className="ref-insert" onClick={() => onInsert(tr(e.example))}>
                                  {tr('Вставить в код')}
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
            </div>
          )
        })}
        {shown.length === 0 && <p className="ref-empty">{tr('Ничего не нашлось. Попробуйте «круг», «цвет» или «высота».')}</p>}
      </div>
    </section>
  )
}
