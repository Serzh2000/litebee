/**
 * Two languages for the interface: Russian (the language the texts are written in) and English.
 *
 * A text is written in Russian in the code and goes through `tr()`. For English the table in i18n/en.ts has the same text
 * as the key. A key may hold `{name}` places: `tr('Лимит {n} см', { n: 160 })` fills the place, and a text that was already
 * made by the core (a message of the checks with its numbers in it) is recognised by the same table, so the core can stay
 * in Russian and the page translates what it shows.
 */
import { EN } from './i18n/en'

export type Lang = 'ru' | 'en'

let lang: Lang = 'ru'
const listeners = new Set<() => void>()

export const getLang = (): Lang => lang

export function setLang(next: Lang): void {
  if (next === lang) return
  lang = next
  listeners.forEach((f) => f())
}

export function subscribeLang(f: () => void): () => void {
  listeners.add(f)
  return () => listeners.delete(f)
}

type Params = Record<string, string | number>

const CYRILLIC = /[А-Яа-яЁё]/

const fill = (text: string, params?: Params) => (params ? text.replace(/\{(\w+)\}/g, (m, k) => (k in params ? String(params[k]) : m)) : text)

const exact = new Map<string, string>(EN)

interface Rule {
  re: RegExp
  en: string
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Templates with `{name}` places turn into patterns, longest and most specific first. */
const rules: Rule[] = EN.filter(([ru]) => /\{\w+\}/.test(ru))
  .map(([ru, en]): Rule => {
    const parts = ru.split(/(\{\w+\})/)
    const body = parts.map((p) => (/^\{\w+\}$/.test(p) ? `(?<${p.slice(1, -1)}>.+?)` : escape(p))).join('')
    return { re: new RegExp(`^${body}$`, 's'), en }
  })
  .sort((a, b) => b.re.source.length - a.re.source.length)

/** Translates a Russian text into the current language. Unknown texts stay as they are. */
export function tr(ru: string, params?: Params): string {
  if (lang === 'ru') return fill(ru, params)
  const known = exact.get(ru)
  if (known !== undefined) return fill(known, params)
  if (!params) {
    for (const r of rules) {
      const m = r.re.exec(ru)
      if (!m?.groups) continue
      // a piece that was filled into the message («за 3 с», «45 см/с») is translated by its own entry
      const parts: Params = {}
      for (const [k, v] of Object.entries(m.groups)) parts[k] = CYRILLIC.test(v) ? tr(v) : v
      return fill(r.en, parts)
    }
  }
  if (!params && ru.includes('; ')) {
    // several messages joined by «; » (the reasons a drone refuses a mission)
    const parts = ru.split('; ')
    const out = parts.map((p) => tr(p))
    if (out.some((p, i) => p !== parts[i])) return out.join('; ')
  }
  return fill(ru, params)
}

/** The right form of a word after a number: Russian has three forms, English two. */
export function plural(n: number, ru: [one: string, few: string, many: string], en: [one: string, other: string]): string {
  if (lang === 'en') return n === 1 ? en[0] : en[1]
  const k = Math.abs(n) % 100
  if (k >= 11 && k <= 14) return ru[2]
  const last = k % 10
  return last === 1 ? ru[0] : last >= 2 && last <= 4 ? ru[1] : ru[2]
}
