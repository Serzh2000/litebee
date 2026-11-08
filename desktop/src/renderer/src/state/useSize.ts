import { useCallback, useLayoutEffect, useState } from 'react'

/** Width and height of an element in CSS pixels, kept up to date by a ResizeObserver. */
export function useSize<T extends HTMLElement>() {
  const [element, setElement] = useState<T | null>(null)
  const ref = useCallback((node: T | null) => setElement(node), [])
  const [size, setSize] = useState({ width: 0, height: 0 })
  useLayoutEffect(() => {
    const el = element
    if (!el) return
    const measure = () => setSize({ width: el.clientWidth, height: el.clientHeight })
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [element])
  return [ref, size] as const
}
