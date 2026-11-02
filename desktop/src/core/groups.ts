import type { Finding, Level } from './checks'
import { plural, tr } from './i18n'

/** What the findings of a show say once the same thing said about many drones is put in one row. */
export interface Group {
  level: Level
  title: string
  /** how many and which: "у дронов 1–10, быстрейший 120 см/с" */
  detail: string
  items: Finding[]
}

const ORDER: Record<Level, number> = { error: 0, warn: 1, info: 2 }

/** "1, 2, 3, 5" -> "1–3, 5" */
export function droneList(numbers: number[]): string {
  const sorted = [...new Set(numbers)].sort((a, b) => a - b)
  const parts: string[] = []
  for (let i = 0; i < sorted.length; ) {
    let j = i
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j++
    parts.push(j - i >= 2 ? `${sorted[i]}–${sorted[j]}` : sorted.slice(i, j + 1).join(', '))
    i = j + 1
  }
  return parts.join(', ')
}

const who = (items: Finding[]): string => {
  const numbers = items.map((f) => f.drone).filter((n): n is number => n !== null)
  if (numbers.length === 0) return ''
  const unique = new Set(numbers).size
  return tr(unique === 1 ? 'дрон {list}' : 'дроны {list}', { list: droneList(numbers) })
}

const biggest = (items: Finding[], pattern: RegExp): number =>
  Math.max(...items.map((f) => Number(f.message.match(pattern)?.[1] ?? 0)))

type Rule = { test: RegExp; make: (items: Finding[], limit: number) => Omit<Group, 'level' | 'items'> }

const RULES: Rule[] = [
  {
    test: /выходит за рабочую область/,
    make: (items) => ({
      title: tr('Полёт выходит за рабочую область'),
      detail: tr('{who}. Поменяйте область, перенесите шоу в нужную четверть или поправьте клетки', { who: who(items) }),
    }),
  },
  {
    test: /больше лимита/,
    make: (items, limit) => ({
      title: tr('Выше лимита {limit} см', { limit }),
      detail: tr('{who}, до {max} см. Поднимите лимит высоты над картой, если потолок позволяет', { who: who(items), max: biggest(items, /высота (\d+(?:\.\d+)?) см/) }),
    }),
  },
  {
    test: /быстрее порога/,
    make: (items) => ({
      title: tr('Переход быстрее порога: дрон может перелететь клетку'),
      detail: `${items.length} ${plural(items.length, ['переход', 'перехода', 'переходов'], ['move', 'moves'])}, ${who(items)}, ${tr('быстрейший {v} см/с', { v: biggest(items, /(\d+) см\/с\)/) })}`,
    }),
  },
  {
    test: /загрузка в дрон недоступна/,
    make: (items) => {
      const kinds = [...new Set(items.map((f) => f.message.match(/Шаг '(\w+)'/)?.[1]).filter(Boolean))]
      return {
        title: tr('В дрон нельзя загрузить шаги {kinds}', { kinds: kinds.join(', ') }),
        detail: tr('{who}. Их формат не проверен на живом дроне, в симуляции они работают', { who: who(items) }),
      }
    },
  },
  {
    test: /время круга/,
    make: (items) => ({
      title: tr('Круги на дроне идут дольше, чем в симуляции'),
      detail: tr('{who}. В блоке circle время относится к одному полуобороту: шаг на дроне длится count × время, симуляция считает его за весь шаг', { who: who(items) }),
    }),
  },
  {
    test: /в миссии шаги, формат которых не проверен/,
    make: (items) => {
      const kinds = [...new Set(items.flatMap((f) => (f.message.match(/\(([\w, ]+)\)/)?.[1] ?? '').split(', ')).filter(Boolean))]
      return {
        title: tr('Шаги {kinds} ещё не летали на живом дроне', { kinds: kinds.join(', ') }),
        detail: tr('{who}. Упакованы как в LiteBee Go. Первый полёт делайте одним дроном и держите под рукой аварийную посадку (Esc)', { who: who(items) }),
      }
    },
  },
  {
    test: /шаги движения по клеткам/,
    make: (items) => ({
      title: tr('Перед загрузкой поставьте дрон на его первую клетку'),
      detail: tr('{who}. Не дальше 30 см от клетки, потом короткий взлёт на 50 см', { who: who(items) }),
    }),
  },
]

/** Groups the findings by what they say. Findings no rule knows stay as rows of their own; errors come first. */
export function groupFindings(findings: Finding[], limit: number): Group[] {
  const groups: Group[] = []
  const byRule = new Map<number, Group>()
  for (const f of findings) {
    const at = RULES.findIndex((r) => r.test.test(f.message))
    if (at < 0) {
      groups.push({ level: f.level, title: tr(f.message), detail: [f.t !== null && `${f.t.toFixed(1)} ${tr('с')}`, f.line && tr('строка {n}', { n: f.line })].filter(Boolean).join(', '), items: [f] })
      continue
    }
    let g = byRule.get(at)
    if (!g) {
      g = { level: f.level, title: '', detail: '', items: [] }
      byRule.set(at, g)
      groups.push(g)
    }
    g.items.push(f)
  }
  for (const [at, g] of byRule) Object.assign(g, RULES[at].make(g.items, limit))
  return groups.sort((a, b) => ORDER[a.level] - ORDER[b.level])
}
