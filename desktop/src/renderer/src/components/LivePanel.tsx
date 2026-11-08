import { batteryFraction, batteryLevel, fmtVolts } from '../state/useLink'
import './LivePanel.css'
import { tr } from '@core/i18n'

const LEVEL_WORD = { ok: '', warn: 'Батарея ниже 7,4 В: лучше заменить', low: 'Батарея ниже 7,0 В: взлёт запрещён' } // shown through tr()

/** Where the cell of a drone is, in words. */
export function placeText(d: LiveDrone): string {
  if (!d.fix) return tr('позиции нет')
  if (d.cell === null) return tr('вне коврика')
  return tr('клетка {n}', { n: d.cell })
}

/** How far the drone is from the centre of its cell, in cm: east (+) and north (+) on the mat. Null without a cell. */
export function offsetFromCentre(d: LiveDrone): { dx: number; dy: number } | null {
  if (!d.fix || d.cell === null) return null
  return { dx: Math.round(d.x - 40 * (d.cell % 12)), dy: Math.round(d.y - 40 * Math.floor(d.cell / 12)) }
}

const sign = (n: number) => (n > 0 ? `+${n}` : String(n))
export const tail = (ip: string) => `…${ip.split('.').pop()}`

interface Props {
  /** drones that are talking to the PC now */
  active: LiveDrone[]
  /** drones that fell silent or lost the link: kept out of the way until they come back or are cleared */
  archive: LiveDrone[]
  /** numbers of the drones of the show */
  numbers: number[]
  roles: Record<string, number | null>
  /** drones whose number was found from the cell they stand on, not picked by the person */
  autoIps: Set<string>
  onRole: (ip: string, n: number | null) => void
  /** result of the last upload per drone */
  uploads: Record<string, { ok: boolean; message: string }>
  onForget: () => void
}

/** Drones on the link: battery and the place on the mat, as the fleet rail of the original app; the silent ones go to the archive. */
export function LivePanel({ active, archive, numbers, roles, autoIps, onRole, uploads, onForget }: Props) {
  if (active.length === 0 && archive.length === 0) return null
  return (
    <section className="live" aria-label={tr('Дроны на связи')}>
      <h2>{tr('Дроны на связи')}<span>{active.length}</span></h2>
      {active.length === 0 && <p className="live-none">{tr('Включите дроны: они найдут компьютер сами.')}</p>}
      <ul>
        {active.map((d) => {
          const level = batteryLevel(d.batteryV)
          const off = offsetFromCentre(d)
          const far = off !== null && Math.max(Math.abs(off.dx), Math.abs(off.dy)) > 12
          return (
            <li key={d.ip} title={tr(LEVEL_WORD[level])}>
              <span className="live-ip">{tail(d.ip)}</span>
              <span className="live-batt" data-level={level} role="img" aria-label={tr('Батарея {v}', { v: fmtVolts(d.batteryV) })}>
                <b>
                  {level !== 'ok' && '▲ '}
                  {fmtVolts(d.batteryV)}
                </b>
                <i style={{ width: `${batteryFraction(d.batteryV) * 100}%` }} />
              </span>
              <span
                className="live-cell"
                title={off ? tr('От центра клетки: {dx} / {dy} см (вправо и вверх на карте)', { dx: sign(off.dx), dy: sign(off.dy) }) : undefined}
              >
                {placeText(d)}
                {far && off && <small className="live-off"> {sign(off.dx)}/{sign(off.dy)}</small>}
                {d.z > 0 && <small className="live-off"> · {d.z} {tr('см')}</small>}
              </span>
              <select
                className="live-role"
                data-auto={autoIps.has(d.ip)}
                aria-label={tr('Какой дрон шоу {ip}', { ip: tail(d.ip) })}
                title={autoIps.has(d.ip) ? tr('Номер найден по клетке, на которой стоит дрон') : tr('Какой дрон шоу это')}
                value={roles[d.ip] ?? ''}
                onChange={(e) => onRole(d.ip, e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">—</option>
                {numbers.map((n) => (
                  <option key={n} value={n} disabled={active.some((o) => o.ip !== d.ip && roles[o.ip] === n)}>
                    № {n}
                  </option>
                ))}
              </select>
              {uploads[d.ip] && (
                <p className="live-result" data-ok={uploads[d.ip].ok} role="status">
                  {tr(uploads[d.ip].message)}
                </p>
              )}
            </li>
          )
        })}
      </ul>

      {archive.length > 0 && (
        <details className="live-archive">
          <summary>{tr('Архив: {n}', { n: archive.length })}</summary>
          <ul>
            {archive.map((d) => (
              <li key={d.ip}>
                <span className="live-ip">{tail(d.ip)}</span>
                <span className="live-v">{fmtVolts(d.batteryV)}</span>
                <span className="live-cell">{d.lost ? tr('связь потеряна') : tr('не отвечает')}</span>
              </li>
            ))}
          </ul>
          <button type="button" className="live-clear" onClick={onForget}>
            {tr('Очистить архив')}
          </button>
          <p className="live-note">{tr('Дрон, который снова заговорит, вернётся в список сам.')}</p>
        </details>
      )}
    </section>
  )
}
