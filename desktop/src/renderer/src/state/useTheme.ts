import { useSyncExternalStore } from 'react'

export type ThemePref = 'auto' | 'light' | 'dark'
export type Theme = 'light' | 'dark'

const KEY = 'litebee.theme'
const listeners = new Set<() => void>()
let pref: ThemePref = 'auto'
let systemDark = false

const resolve = (): Theme => (pref === 'auto' ? (systemDark ? 'dark' : 'light') : pref)

/** The theme that is shown now (the page asks for it to pick colours that are drawn by code, not by the style sheet). */
export const currentTheme = (): Theme => resolve()

function apply() {
  document.documentElement.dataset.theme = resolve()
  listeners.forEach((f) => f())
}

export function setThemePref(next: ThemePref): void {
  pref = next
  try {
    localStorage.setItem(KEY, next)
  } catch {
    /* the choice is simply not remembered */
  }
  apply()
}

/** At start: the address (?theme=dark), the last choice, else what the system wants; follows the system while on auto. */
export function initTheme(): void {
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  systemDark = media.matches
  let saved: string | null = null
  try {
    saved = localStorage.getItem(KEY)
  } catch {
    /* no storage */
  }
  const wanted = new URLSearchParams(window.location.search).get('theme') ?? saved
  pref = wanted === 'light' || wanted === 'dark' ? wanted : 'auto'
  media.addEventListener('change', (e) => {
    systemDark = e.matches
    apply()
  })
  apply()
}

const subscribe = (f: () => void) => {
  listeners.add(f)
  return () => listeners.delete(f)
}

/** The theme and the choice behind it; the component that calls it redraws when either changes. */
export function useTheme(): { theme: Theme; pref: ThemePref } {
  const state = useSyncExternalStore(subscribe, () => `${pref}|${resolve()}`)
  const [p, theme] = state.split('|') as [ThemePref, Theme]
  return { theme, pref: p }
}
