import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { checkShow } from '@core/checks'
import { getLang, plural, setLang, tr } from '@core/i18n'
import { EN } from '@core/i18n/en'
import { groupFindings } from '@core/groups'
import { stepText } from '@core/labels'
import { compileDrone, UploadUnsupported, uploadProblems } from '@core/mission'
import { preflight } from '../src/renderer/src/state/preflight'
import { buildShow, type ShowData, type Step } from '@core/show'
import catalog from '../src/renderer/src/data/catalog.json'
import reference from '../src/renderer/src/data/reference.json'
import dream from '../shows/my_dream.json'
import square from '../shows/quarter_square.json'

const CYR = /[А-Яа-яЁё]/
afterEach(() => setLang('ru'))

const walk = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? (name === 'i18n' ? [] : walk(path)) : /\.tsx?$/.test(name) ? [path] : []
  })

describe('the English table', () => {
  it('has an entry for every text that the source puts through tr()', () => {
    const have = new Set(EN.map(([ru]) => ru))
    const missing: string[] = []
    for (const file of walk(join(__dirname, '..', 'src'))) {
      const text = readFileSync(file, 'utf8')
      for (const m of text.matchAll(/\btr\(\s*'((?:[^'\\]|\\.)*)'/g)) {
        const key = m[1].replace(/\\'/g, "'")
        if (CYR.test(key) && !have.has(key)) missing.push(`${file.split(/[\\/]/).pop()}: ${key}`)
      }
    }
    expect(missing).toEqual([])
  })

  it('keeps the places of a template the same in both languages, and no entry is empty', () => {
    const places = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(',')
    for (const [ru, en] of EN) {
      expect(en.length, ru).toBeGreaterThan(0)
      expect(places(en), ru).toBe(places(ru))
    }
  })
})

describe('tr', () => {
  it('leaves Russian alone and fills the places', () => {
    expect(tr('Дрон {n}', { n: 3 })).toBe('Дрон 3')
    expect(tr('Старт')).toBe('Старт')
    expect(getLang()).toBe('ru')
  })

  it('translates a text, a template with places, and a finished message of the core', () => {
    setLang('en')
    expect(tr('Старт')).toBe('Start')
    expect(tr('Дрон {n}', { n: 3 })).toBe('Drone 3')
    expect(tr('Дрон 4: высота 160 см больше лимита 150 см, полёт будет отклонён')).toBe('Drone 4: height 160 cm is above the 150 cm limit, the flight will be refused')
    // a piece filled into a message has an entry of its own
    expect(tr('Дрон 2: переход на клетку 25 за 1 с (120 см, 120 см/с) быстрее порога 100 см/с: дрон может перелететь клетку')).toBe(
      'Drone 2: the move to cell 25 in 1 s (120 cm, 120 cm/s) is faster than the 100 cm/s threshold: the drone may overshoot the cell',
    )
    // several reasons joined by «; »
    expect(tr('Высота 170 см больше лимита 150 см; Батарея 6.8 В ниже 7.0 В, полёт отменён')).toBe(
      'Height 170 cm is above the 150 cm limit; Battery 6.8 V is below 7.0 V, the flight is cancelled',
    )
    expect(tr('Совсем неизвестный текст')).toBe('Совсем неизвестный текст')
  })

  it('picks the form of a word after a number', () => {
    expect([1, 2, 5, 11, 21, 22].map((n) => plural(n, ['дрон', 'дрона', 'дронов'], ['drone', 'drones']))).toEqual(['дрон', 'дрона', 'дронов', 'дронов', 'дрон', 'дрона'])
    setLang('en')
    expect([1, 2, 5].map((n) => plural(n, ['дрон', 'дрона', 'дронов'], ['drone', 'drones']))).toEqual(['drone', 'drones', 'drones'])
  })
})

describe('what the app shows in English has no Russian left', () => {
  const left = (texts: string[]) => texts.filter((t) => CYR.test(t))

  it('the findings and the groups of the checks of the big shows', () => {
    setLang('en')
    for (const data of [dream, square]) {
      const show = buildShow(data as unknown as ShowData)
      const findings = checkShow(show, { maxHeightCm: 150 })
      expect(left(findings.map((f) => tr(f.message)))).toEqual([])
      const groups = groupFindings(findings, 150)
      expect(left(groups.flatMap((g) => [g.title, g.detail]))).toEqual([])
    }
  })

  it('the text of every kind of step', () => {
    setLang('en')
    const steps: [Parameters<typeof stepText>[0], Record<string, unknown>][] = [
      ['code', { cell: 5 }], ['code_z', { cell: 5, z: 100 }], ['takeoff', { z: 100 }], ['set_z', { z: 80 }],
      ['circle', { cell1: 1, cell2: 2, count: 2 }], ['circle_z', { cell1: 1, cell2: 2, dz: 20 }], ['rgb', { color: 'red' }],
      ['calibrate', {}], ['land', {}],
    ]
    expect(left(steps.map(([k, a]) => tr(stepText(k, a))))).toEqual([])
  })

  it('the reasons and the steps before a flight, in every state', () => {
    setLang('en')
    const base = { connected: true, loading: false, loaded: false, armed: false, flying: false, loadBlock: null as string | null }
    const states = [
      preflight({ ...base, check: null, errors: 0 }),
      preflight({ ...base, check: 'stale', errors: 0 }),
      preflight({ ...base, check: 'errors', errors: 1 }),
      preflight({ ...base, check: 'errors', errors: 3 }),
      preflight({ ...base, check: 'ok', errors: 0 }),
      preflight({ ...base, check: 'ok', errors: 0, connected: false, loadBlock: 'Нет дронов на связи' }),
      preflight({ ...base, check: 'ok', errors: 0, loading: true }),
      preflight({ ...base, check: 'ok', errors: 0, loaded: true }),
      preflight({ ...base, check: 'ok', errors: 0, loaded: true, armed: true }),
      preflight({ ...base, check: 'ok', errors: 0, loaded: true, armed: true, flying: true }),
    ]
    const texts = states.flatMap((s) => [s.reason, ...s.steps.flatMap((x) => [x.label, x.word, x.why ?? ''])]).filter(Boolean)
    expect(left(texts.map((t) => tr(t)))).toEqual([])
  })

  it('the reasons a mission is refused', () => {
    setLang('en')
    const hold = (z: number): Step[] => [
      { kind: 'takeoff', seconds: 5, args: { z }, line: 1 },
      { kind: 'code', seconds: 3, args: { cell: 40 }, line: 2 },
      { kind: 'set_z', seconds: 90, args: { z }, line: 3 },
    ] as Step[]
    const problems = uploadProblems(compileDrone(hold(190)), { batteryV: 6.5, x: 0, y: 0 })
    expect(problems.length).toBeGreaterThan(2)
    expect(left(problems.map((p) => tr(p)))).toEqual([])
    const refused: string[] = []
    for (const steps of [
      [{ kind: 'circle_z', seconds: 3, args: { cell1: 1, cell2: 2, dz: 5, rotate: 'cw' }, line: 4 }],
      [{ kind: 'code', seconds: 3, args: { cell: 500 }, line: 4 }],
      [{ kind: 'circle', seconds: 3, args: { cell1: 1, cell2: 2, count: 0, rotate: 'cw' }, line: 4 }],
      [],
    ] as Step[][]) {
      try {
        compileDrone(steps)
      } catch (e) {
        if (e instanceof UploadUnsupported) refused.push(tr(e.message))
      }
    }
    expect(refused).toHaveLength(4)
    expect(left(refused)).toEqual([])
  })

  it('the command reference', () => {
    setLang('en')
    const texts: string[] = [...reference.topics.map((t) => t.title), ...Object.entries(reference.statusHint).flat()]
    for (const e of reference.entries) {
      texts.push(e.summary, e.status, e.example, ...e.notes)
      for (const p of e.params) texts.push(p.unit, p.text)
    }
    const stay = texts.filter((t) => CYR.test(tr(t)))
    expect(stay.map((t) => t.slice(0, 80))).toEqual([])
  })

  it('every title and note of the catalog, and its themes and tags', () => {
    setLang('en')
    const items = [...catalog.gallery, ...catalog.classic]
    const texts = items.flatMap((i) => [(i as { title?: string }).title ?? '', (i as { note?: string }).note ?? '', ...i.themes, ...i.tags])
    expect(left(texts.filter(Boolean).map((t) => tr(t))).slice(0, 5)).toEqual([])
  })
})
