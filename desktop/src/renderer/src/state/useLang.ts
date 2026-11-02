import { useEffect, useSyncExternalStore } from 'react'
import { getLang, setLang, subscribeLang, type Lang } from '@core/i18n'

const KEY = 'litebee.lang'

/** The language at start: the address (?lang=en), what the person chose last time, else the language of the system. */
export function initLang(): void {
  const wanted = new URLSearchParams(window.location.search).get('lang')
  let saved: string | null = null
  try {
    saved = localStorage.getItem(KEY)
  } catch {
    /* no storage: the system language decides */
  }
  const pick = wanted ?? saved ?? (navigator.language.toLowerCase().startsWith('ru') ? 'ru' : 'en')
  setLang(pick === 'en' ? 'en' : 'ru')
}

/** The current language; the component that calls it redraws when the language changes, and so does everything below it. */
export function useLang(): Lang {
  const lang = useSyncExternalStore(subscribeLang, getLang)
  useEffect(() => {
    document.documentElement.lang = lang
    void window.litebee?.setLang(lang)
    try {
      localStorage.setItem(KEY, lang)
    } catch {
      /* the choice is simply not remembered */
    }
  }, [lang])
  return lang
}

export { setLang }
