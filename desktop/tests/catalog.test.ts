import { describe, expect, it } from 'vitest'
import { countFor, filterCatalog, lengthOf, NO_FILTERS, options, toggle, type CatalogItem } from '@core/catalog'
import catalog from '../src/renderer/src/data/catalog.json'

const item = (id: string, p: Partial<CatalogItem>): CatalogItem => ({
  id, title: id, note: '', area: 'quarter', drones: 4, seconds: 40, themes: ['Строи'], tags: ['Перемещения', 'Проверенные шаги'], ...p,
})
const items = [
  item('a', { area: 'quarter', drones: 4 }),
  item('b', { area: 'quarter', drones: 6, themes: ['Игры света'], tags: ['Только свет', 'Проверенные шаги'], seconds: 20 }),
  item('c', { area: 'full', drones: 6, tags: ['Перемещения', 'Круги circle'], seconds: 90 }),
  item('d', { area: 'full', drones: 10, themes: ['Кольцо'] }),
]
const ids = (f = NO_FILTERS) => filterCatalog(items, f).map((i) => i.id)

describe('filters of the wizard', () => {
  it('shows everything with no filters', () => expect(ids()).toEqual(['a', 'b', 'c', 'd']))

  it('treats the options of one group as alternatives and the groups as a combination', () => {
    expect(ids(toggle(NO_FILTERS, 'areas', 'quarter'))).toEqual(['a', 'b'])
    expect(ids(toggle(toggle(NO_FILTERS, 'areas', 'quarter'), 'areas', 'full'))).toEqual(['a', 'b', 'c', 'd'])
    const f = toggle(toggle(toggle(NO_FILTERS, 'areas', 'quarter'), 'drones', 4), 'drones', 6)
    expect(ids(f)).toEqual(['a', 'b'])
    expect(ids(toggle(f, 'themes', 'Игры света'))).toEqual(['b'])
  })

  it('narrows by features one at a time', () => {
    expect(ids(toggle(NO_FILTERS, 'features', 'Проверенные шаги'))).toEqual(['a', 'b', 'd'])
    expect(ids(toggle(toggle(NO_FILTERS, 'features', 'Проверенные шаги'), 'features', 'Только свет'))).toEqual(['b'])
  })

  it('sorts shows by length and by words of the query', () => {
    expect([20, 30, 60, 61].map((s) => lengthOf(s))).toEqual(['short', 'middle', 'middle', 'long'])
    expect(ids(toggle(NO_FILTERS, 'lengths', 'long'))).toEqual(['c'])
    expect(ids({ ...NO_FILTERS, query: 'Кольцо' })).toEqual(['d'])
    expect(ids({ ...NO_FILTERS, query: 'свет 6' })).toEqual([])
  })

  it('counts what a chip would give with the other filters kept, and toggles it off again', () => {
    const f = toggle(NO_FILTERS, 'areas', 'quarter')
    expect(countFor(items, f, 'drones', 6)).toBe(1)
    expect(countFor(items, f, 'drones', 10)).toBe(0)
    expect(countFor(items, f, 'areas', 'full')).toBe(2)
    expect(toggle(f, 'areas', 'quarter')).toEqual(NO_FILTERS)
  })
})

describe('the real catalog', () => {
  const all = [...catalog.gallery, ...catalog.classic] as unknown as CatalogItem[]
  it('has over a hundred new shows on both mats and with 2 to 10 drones', () => {
    expect(catalog.gallery.length).toBeGreaterThanOrEqual(100)
    const o = options(all)
    expect(o.drones[0]).toBe(2)
    expect(o.drones[o.drones.length - 1]).toBe(10)
    expect(new Set(all.map((i) => i.area))).toEqual(new Set(['quarter', 'full']))
    expect(o.features).toContain('Только свет')
  })
  it('has plenty of shows for seven drones on the 6 x 6 quarter, with an inner and an outer ring', () => {
    const seven = (catalog.gallery as unknown as CatalogItem[]).filter((i) => i.drones === 7 && i.area === 'quarter')
    expect(seven.length).toBeGreaterThanOrEqual(8)
    expect(seven.some((i) => i.title.startsWith('Два кольца'))).toBe(true)
  })
  it('keeps the shows long: most of the gallery runs a minute and a half or more', () => {
    const long = catalog.gallery.filter((i) => i.seconds >= 90).length
    expect(long / catalog.gallery.length).toBeGreaterThan(0.6)
    expect(Math.max(...catalog.gallery.map((i) => i.seconds))).toBeLessThanOrEqual(300)
  })
  it('gives every gallery show its own id and a title', () => {
    expect(new Set(catalog.gallery.map((i) => i.id)).size).toBe(catalog.gallery.length)
    for (const i of catalog.gallery) expect(i.title.length).toBeGreaterThan(3)
  })
})
