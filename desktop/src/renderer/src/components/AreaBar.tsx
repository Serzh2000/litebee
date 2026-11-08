import { useEffect, useRef, useState } from 'react'
import { Box, Clapperboard, Route, ScanLine, Square } from 'lucide-react'
import { FULL, QUARTERS, sameArea, validArea, type Area } from '@core/area'
import { LimitField } from './LimitPopover'
import './AreaBar.css'
import { tr } from '@core/i18n'

interface Props {
  area: Area
  onArea: (a: Area) => void
  /** the quarter the show is written for now (null when it spans more than one), so it is not offered as a target */
  from: Area | null
  onMigrate: (to: Area) => void
  maxHeight: number
  onMaxHeight: (cm: number) => void
  /** the flat map or the model view */
  view: '2d' | '3d'
  onView: (v: '2d' | '3d') => void
  tags: boolean
  onTags: () => void
  routes: boolean
  onRoutes: () => void
}

const PRESETS = [{ id: 'full', title: 'Весь коврик, 12×12', area: FULL }, ...QUARTERS.map((q) => ({ id: q.id, title: q.title + ', 6×6', area: q.area }))]

/** Which part of the mat is shown and used for checks, and the move of a show into another quarter. */
export function AreaBar({ area, onArea, from, onMigrate, maxHeight, onMaxHeight, view, onView, tags, onTags, routes, onRoutes }: Props) {
  const preset = PRESETS.find((p) => sameArea(p.area, area))
  const [custom, setCustom] = useState(false)
  const [menu, setMenu] = useState(false)
  /** the quarter waiting for a confirmation */
  const [ask, setAsk] = useState<number | null>(null)
  const box = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!menu) {
      setAsk(null)
      return
    }
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setMenu(false)
    }
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setMenu(false)
    document.addEventListener('mousedown', away)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', away)
      document.removeEventListener('keydown', esc)
    }
  }, [menu])

  const set = (key: keyof Area, value: string) => {
    const next = { ...area, [key]: Number(value) }
    if (validArea(next)) onArea(next)
  }

  return (
    <div className="areabar">
      {view === '2d' && <div className="map-display" role="group" aria-label={tr('Отображение карты')}>
        <button type="button" aria-pressed={routes} aria-label={tr('Маршруты')} title={tr('Маршруты')} onClick={onRoutes}><Route size={15} aria-hidden="true" /></button>
        <button type="button" aria-pressed={tags} aria-label={tr('Метки коврика')} title={tr('Метки коврика')} onClick={onTags}><ScanLine size={15} aria-hidden="true" /></button>
      </div>}
      <label className="areabar-field">
        <span>{tr('Область')}</span>
        <select
          value={custom || !preset ? 'custom' : preset.id}
          onChange={(e) => {
            if (e.target.value === 'custom') return setCustom(true)
            setCustom(false)
            onArea(PRESETS.find((p) => p.id === e.target.value)!.area)
          }}
        >
          {PRESETS.map((p) => (
            <option key={p.id} value={p.id}>
              {tr(p.title)}
            </option>
          ))}
          <option value="custom">{tr('Свой кусок…')}</option>
        </select>
      </label>

      {(custom || !preset) && (
        <div className="areabar-custom" role="group" aria-label={tr('Свой кусок коврика')}>
          {(
            [
              ['col0', 'столбец с'],
              ['row0', 'строка с'],
              ['cols', 'столбцов'],
              ['rows', 'строк'],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              <span>{tr(label)}</span>
              <input type="number" min={key.endsWith('0') ? 0 : 1} max={12} value={area[key]} onChange={(e) => set(key, e.target.value)} />
            </label>
          ))}
        </div>
      )}

      <div className="areabar-right">
      <div className="areabar-view" role="group" aria-label={tr('Вид карты')}>
        <button type="button" aria-pressed={view === '2d'} onClick={() => onView('2d')} title={tr('Карта сверху')}>
          <Square size={14} strokeWidth={1.9} aria-hidden="true" />
          2D
        </button>
        <button type="button" aria-pressed={view === '3d'} onClick={() => onView('3d')} title={tr('Объёмная модель дронов, камеру можно вращать')}>
          <Box size={14} strokeWidth={1.9} aria-hidden="true" />
          3D
        </button>
      </div>
      <div className="areabar-move" ref={box}>
        <button type="button" className="areabar-button" aria-expanded={menu} aria-haspopup="menu" onClick={() => setMenu((m) => !m)}>
          <Clapperboard size={15} strokeWidth={1.9} aria-hidden="true" />
          {tr('Шоу…')}
        </button>
        {menu && (
          <div className="areabar-menu" role="menu" aria-label={tr('Шоу')}>
            <div className="areabar-section">
              <strong>{tr('Перенести шоу в четверть')}</strong>
              {ask === null ? (
                QUARTERS.map((q, i) => (
                  <button key={q.id} type="button" role="menuitem" disabled={from !== null && sameArea(from, q.area)} onClick={() => setAsk(i)}>
                    {tr(q.title)}
                  </button>
                ))
              ) : (
                <div className="areabar-confirm">
                  <p>{tr('Сдвинуть шоу в четверть {n}? Номера клеток в коде изменятся, отменить можно Ctrl+Z в редакторе.', { n: ask + 1 })}</p>
                  <div>
                    <button
                      type="button"
                      className="areabar-go"
                      onClick={() => {
                        const to = QUARTERS[ask].area
                        setMenu(false)
                        onMigrate(to)
                      }}
                    >
                      {tr('Сдвинуть')}
                    </button>
                    <button type="button" onClick={() => setAsk(null)}>
                      {tr('Отмена')}
                    </button>
                  </div>
                </div>
              )}
            </div>
            <div className="areabar-section areabar-limit">
              <strong>{tr('Высота')}</strong>
              <LimitField value={maxHeight} onChange={onMaxHeight} />
            </div>
          </div>
        )}
      </div>
      </div>
    </div>
  )
}
