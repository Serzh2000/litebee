import { useEffect, useRef, type RefObject } from 'react'

/** Shared keyboard containment for the start dialog and the project wizard. */
export function useModalFocus(root: RefObject<HTMLElement | null>, active = true) {
  const trigger = useRef(document.activeElement instanceof HTMLElement ? document.activeElement : null)
  useEffect(() => {
    const dialog = root.current
    if (!active || !dialog) return
    const controls = () => Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), [tabindex="0"]')).filter((el) => el.getClientRects().length > 0 && !el.closest('[inert]'))
    if (!dialog.contains(document.activeElement)) controls()[0]?.focus()
    const trap = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return
      const elements = controls()
      const first = elements[0]
      const last = elements[elements.length - 1]
      if (!first || !last) return
      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        event.preventDefault()
        first.focus()
      }
    }
    dialog.addEventListener('keydown', trap)
    return () => {
      dialog.removeEventListener('keydown', trap)
      const previous = trigger.current
      queueMicrotask(() => { if (previous?.isConnected && !previous.closest('[inert]')) previous.focus() })
    }
  }, [root, active])
}
