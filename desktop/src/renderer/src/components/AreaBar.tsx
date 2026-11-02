import { useEffect, useRef, useState } from 'react'
import { ArrowRightLeft, MapPin } from 'lucide-react'
import { FULL, QUARTERS, sameArea, validArea, type Area } from '@core/area'
import { LimitPopover } from './LimitPopover'
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
  /** stand the selected drone on a cell chosen on the map */
  placing: boolean
  onPlace: () => void
}

const PRESETS = [{ id: 'full', title: 'Весь коврик, 12×12', area: FULL }, ...QUARTERS.map((q) => ({ id: q.id, title: q.title + ', 6×6', area: q.area }))]

/** Which part of the mat is shown and used for checks, and the move of a show into another quarter. */
export function AreaBar({ area, onArea, from, onMigrate, maxHeight, onMaxHeight, placing, onPlace }: Props) {
  const preset = PRESETS.find((p) => sameArea(p.area, area))
  const [custom, setCustom] = useState(false)
  const [menu, setMenu] = useState(false)
  const box = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!menu) return
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
      <button type="button" className="areabar-button" aria-pressed={placing} onClick={onPlace} title={tr('Возьмите дрона на карте и перетащите на клетку, или выберите дрона, нажмите эту кнопку и потом клетку')}>
          <MapPin size={15} strokeWidth={1.9} aria-hidden="true" />
          {placing ? tr('Нажмите клетку на карте') : tr('Поставить дрона')}
        </button>
      <LimitPopover value={maxHeight} onChange={onMaxHeight} />
      <div className="areabar-move" ref={box}>
        <button type="button" className="areabar-button" aria-expanded={menu} onClick={() => setMenu((m) => !m)}>
          <ArrowRightLeft size={15} strokeWidth={1.9} aria-hidden="true" />
          {tr('Перенести шоу')}
        </button>
        {menu && (
          <div className="areabar-menu" role="menu" aria-label={tr('Перенести шоу в четверть')}>
            <p>{tr('Сдвинет номера клеток в коде. Отменить можно Ctrl+Z в редакторе.')}</p>
            {QUARTERS.map((q) => (
              <button
                key={q.id}
                type="button"
                role="menuitem"
                disabled={from !== null && sameArea(from, q.area)}
                onClick={() => {
                  setMenu(false)
                  onMigrate(q.area)
                }}
              >
                {q.title}
              </button>
            ))}
          </div>
        )}
      </div>
      </div>
    </div>
  )
}
