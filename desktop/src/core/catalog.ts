/**
 * The catalog of example shows and the filters of the new-project wizard.
 *
 * Within one group of filters the chosen options are alternatives (6 x 6 or 12 x 12, 4 or 6 drones); the groups are
 * combined (a 6 x 6 show with 4 or 6 drones), and the features narrow the list one by one (only light AND only steps
 * that have flown).
 */
export type Area = 'quarter' | 'full'
export type Length = 'short' | 'middle' | 'long'

export interface CatalogItem {
  id: string
  title: string
  note: string
  area: Area
  drones: number
  seconds: number
  /** what the show is about: formations, a carousel, a wave of height, play of light */
  themes: string[]
  /** what the show does: only light, moves, circles, different heights, proven steps only */
  tags: string[]
}

export interface Filters {
  areas: Area[]
  drones: number[]
  themes: string[]
  lengths: Length[]
  features: string[]
  query: string
}

export const NO_FILTERS: Filters = { areas: [], drones: [], themes: [], lengths: [], features: [], query: '' }

export const AREA_NAME: Record<Area, string> = { quarter: '6 × 6', full: '12 × 12' }
export const LENGTH_NAME: Record<Length, string> = { short: 'до 30 с', middle: '30–60 с', long: 'дольше минуты' }
export const lengthOf = (seconds: number): Length => (seconds < 30 ? 'short' : seconds <= 60 ? 'middle' : 'long')

const norm = (s: string) => s.toLowerCase().replace(/ё/g, 'е')

/** True when the item passes the filters of every group except `skip` (used to count what a chip would add). */
function passes(item: CatalogItem, f: Filters, skip?: keyof Filters): boolean {
  if (skip !== 'areas' && f.areas.length && !f.areas.includes(item.area)) return false
  if (skip !== 'drones' && f.drones.length && !f.drones.includes(item.drones)) return false
  if (skip !== 'themes' && f.themes.length && !f.themes.some((t) => item.themes.includes(t))) return false
  if (skip !== 'lengths' && f.lengths.length && !f.lengths.includes(lengthOf(item.seconds))) return false
  if (skip !== 'features' && !f.features.every((t) => item.tags.includes(t))) return false
  if (skip !== 'query' && f.query.trim()) {
    const hay = norm(`${item.title} ${item.note} ${item.themes.join(' ')} ${item.tags.join(' ')}`)
    if (!norm(f.query.trim()).split(/\s+/).every((w) => hay.includes(w))) return false
  }
  return true
}

export const filterCatalog = (items: CatalogItem[], f: Filters): CatalogItem[] => items.filter((i) => passes(i, f))

/** How many shows a chip of one group would give, with all the other filters kept: 0 means it leads nowhere. */
export function countFor(items: CatalogItem[], f: Filters, group: Exclude<keyof Filters, 'query'>, option: string | number): number {
  const only: Filters = { ...f, [group]: group === 'features' ? [...f.features, option as string] : [option as never] }
  return items.filter((i) => passes(i, only)).length
}

export const isFiltered = (f: Filters) =>
  f.areas.length + f.drones.length + f.themes.length + f.lengths.length + f.features.length > 0 || f.query.trim() !== ''

/** The options each group offers, taken from the catalog itself, so a new show brings its own chips. */
export function options(items: CatalogItem[]) {
  const uniq = <T,>(list: T[]) => [...new Set(list)]
  return {
    drones: uniq(items.map((i) => i.drones)).sort((a, b) => a - b),
    themes: uniq(items.flatMap((i) => i.themes)).sort((a, b) => a.localeCompare(b, 'ru')),
    features: ['Только свет', 'Перемещения', 'Разная высота', 'Круги circle', 'Проверенные шаги'].filter((t) => items.some((i) => i.tags.includes(t))),
  }
}

/** Switches one option of a group on or off. */
export function toggle<K extends Exclude<keyof Filters, 'query'>>(f: Filters, group: K, value: Filters[K][number]): Filters {
  const list = f[group] as unknown[]
  const next = list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
  return { ...f, [group]: next }
}
