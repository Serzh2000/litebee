import { useEffect, useRef, useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { HARD_MAX_HEIGHT_CM, MIN_TAKEOFF_CM } from '@core/checks'
import { tr } from '@core/i18n'

/** The input of the height limit, for a menu or a popover. */
export function LimitField({ value, onChange, autoFocus = false }: { value: number; onChange: (cm: number) => void; autoFocus?: boolean }) {
  const [text, setText] = useState(String(value))
  useEffect(() => setText(String(value)), [value])
  const n = Number(text)
  const valid = Number.isInteger(n) && n >= MIN_TAKEOFF_CM && n <= HARD_MAX_HEIGHT_CM
  const commit = () => valid && onChange(n)
  return (
    <>
      <label htmlFor="max-height">{tr('Лимит высоты, см')}</label>
      <input
        id="max-height"
        type="number"
        min={MIN_TAKEOFF_CM}
        max={HARD_MAX_HEIGHT_CM}
        value={text}
        aria-invalid={!valid}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => e.key === 'Enter' && commit()}
        autoFocus={autoFocus}
      />
      <p className={valid ? 'hint' : 'hint bad'}>
        {valid ? tr('После смены нажмите «Проверить»') : tr('Нужно целое число от {min} до {max}', { min: MIN_TAKEOFF_CM, max: HARD_MAX_HEIGHT_CM })}
      </p>
    </>
  )
}

/** The height limit of the flight: one number, kept out of the way until it is needed. */
export function LimitPopover({ value, onChange }: { value: number; onChange: (cm: number) => void }) {
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

  return (
    <div className="limit" ref={box}>
      <button type="button" className="quiet" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <SlidersHorizontal size={15} strokeWidth={1.75} aria-hidden="true" />
        {tr('Высота до {value} см', { value })}
      </button>
      {open && (
        <div className="popover" role="dialog" aria-label={tr('Ограничение высоты')}>
          <LimitField value={value} onChange={onChange} autoFocus />
        </div>
      )}
    </div>
  )
}
