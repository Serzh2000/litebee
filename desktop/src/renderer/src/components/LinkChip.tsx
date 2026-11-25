import { useEffect, useRef, useState } from 'react'
import { WifiOff } from 'lucide-react'
import { isAlive, type Link } from '../state/useLink'
import './LinkChip.css'
import { tr } from '@core/i18n'

/** Link status in the top bar: who is on the line, and which network adapter the PC listens on. */
export function LinkChip({ link }: { link: Link }) {
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

  if (!link.available) {
    return (
      <span className="link-state" title={tr('Связь с дронами работает только в приложении для компьютера, не в браузере')}>
        <WifiOff size={15} strokeWidth={1.75} aria-hidden="true" />
        <span className="lc-text">{tr('Без дронов')}</span>
      </span>
    )
  }

  const listening = link.state?.pcIp ?? null
  const allowed = link.state?.allowed ?? false
  const alive = link.drones.filter(isAlive).length
  const label = !allowed
    ? tr('Опрос выключен')
    : alive > 0
      ? tr('Дронов на связи: {n}', { n: alive })
      : listening
        ? tr('Ждём дроны')
        : tr('Подключить дроны')

  return (
    <div className="link-chip" ref={box}>
      <button type="button" className="quiet" aria-expanded={open} data-on={alive > 0} onClick={() => setOpen((o) => !o)}>
        <span className="lc-dot" data-on={alive > 0} data-wait={allowed && alive === 0 && Boolean(listening)} aria-hidden="true" />
        <span className="lc-text">{label}</span>
      </button>
      {open && (
        <div className="popover link-pop" role="dialog" aria-label={tr('Связь с дронами')}>
          <strong>{tr('Связь с дронами')}</strong>
          <button type="button" role="switch" aria-checked={allowed} className="allow" onClick={() => void link.allow(!allowed)}>
            <span className="allow-track" aria-hidden="true">
              <span className="allow-knob" />
            </span>
            <span>{tr('Опрашивать дроны')}</span>
          </button>
          <p className="hint">
            {!allowed
              ? tr('Выключено: компьютер ничего не рассылает по сети и не отбирает дронов у другого компьютера. Включайте только на том, с которого летите.')
              : listening
                ? tr('Приложение слушает на {ip}. Включите дроны: они найдут компьютер сами. Если в сети есть другой компьютер с этой программой, на нём опрос должен быть выключен.', { ip: listening })
                : tr('Выберите сетевой адаптер, который подключён к Wi-Fi дронов (адрес 192.168.13.x).')}
          </p>
          {allowed && link.state?.error && <p className="hint bad">{tr(link.state.error)}</p>}
          {allowed && link.adapters.length === 0 && <p className="hint bad">{tr('Сетевых адаптеров не найдено.')}</p>}
          <ul className="adapters" hidden={!allowed}>
            {link.adapters.map((a) => (
              <li key={a.ip}>
                <button type="button" aria-pressed={listening === a.ip} onClick={() => void (listening === a.ip ? link.stop() : link.start(a.ip))}>
                  <span>{a.ip}</span>
                  <small>{a.name}</small>
                  <em>{listening === a.ip ? tr('Отключить') : tr('Слушать')}</em>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
