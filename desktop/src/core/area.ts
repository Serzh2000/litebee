import type { ShowData } from './show'

/**
 * The working area: a rectangle of cells cut out of the 12 x 12 mat (4.8 m, "5 x 5" of the original). The mat folded in
 * four is a quarter, 6 x 6 cells (2.4 m). Cell numbers always count over the whole mat (cell = column + 12 x row), so a
 * quarter is a window onto it: moving a show to another quarter means shifting its cell numbers.
 */
export const GRID = 12
export const CELL_CM = 40

export interface Area {
  col0: number
  row0: number
  cols: number
  rows: number
}

export const FULL: Area = { col0: 0, row0: 0, cols: GRID, rows: GRID }

/** Quarters in reading order of the mat seen from above: cell 0 is bottom left. */
export const QUARTERS: { id: string; title: string; area: Area }[] = [
  { id: 'q1', title: 'Четверть 1, слева внизу', area: { col0: 0, row0: 0, cols: 6, rows: 6 } },
  { id: 'q2', title: 'Четверть 2, справа внизу', area: { col0: 6, row0: 0, cols: 6, rows: 6 } },
  { id: 'q3', title: 'Четверть 3, слева вверху', area: { col0: 0, row0: 6, cols: 6, rows: 6 } },
  { id: 'q4', title: 'Четверть 4, справа вверху', area: { col0: 6, row0: 6, cols: 6, rows: 6 } },
]

export const sameArea = (a: Area, b: Area): boolean =>
  a.col0 === b.col0 && a.row0 === b.row0 && a.cols === b.cols && a.rows === b.rows

export function areaName(a: Area): string {
  if (sameArea(a, FULL)) return 'весь коврик'
  const q = QUARTERS.find((x) => sameArea(x.area, a))
  return q ? q.title.toLowerCase() : `область ${a.cols}×${a.rows}`
}

export function validArea(a: Area): boolean {
  const ints = [a.col0, a.row0, a.cols, a.rows].every(Number.isInteger)
  return ints && a.col0 >= 0 && a.row0 >= 0 && a.cols >= 1 && a.rows >= 1 && a.col0 + a.cols <= GRID && a.row0 + a.rows <= GRID
}

export const cellInArea = (a: Area, cell: number): boolean => {
  const col = cell % GRID
  const row = Math.floor(cell / GRID)
  return cell >= 0 && cell < GRID * GRID && col >= a.col0 && col < a.col0 + a.cols && row >= a.row0 && row < a.row0 + a.rows
}

/** Every cell number a show names: targets of moves and the two cells of a circle. */
export function cellsOfShow(data: ShowData): number[] {
  const out: number[] = []
  for (const steps of Object.values(data.drones)) {
    for (const s of steps) {
      for (const key of ['cell', 'cell1', 'cell2']) {
        const c = s.args[key]
        if (typeof c === 'number') out.push(c)
      }
    }
  }
  return out
}

/** The smallest of the mat and its quarters that holds every cell of the show. */
export function detectArea(data: ShowData): Area {
  const cells = cellsOfShow(data)
  if (cells.length === 0) return FULL
  return QUARTERS.find((q) => cells.every((c) => cellInArea(q.area, c)))?.area ?? FULL
}

// ---- moving a show: shifting the cell numbers written in its Python source ----------------------------------------

/** Where a method keeps its cells: argument positions, or 'text' for code_s, whose cells are words of one string. */
const CELL_ARGS: Record<string, (number | 'text')[]> = {
  code: [0],
  code_z: [0],
  code_s: ['text'],
  circle: [1, 2],
  circle_z: [0, 1],
}

export interface Migration {
  source: string
  /** cell numbers shifted */
  changed: number
  /** cell arguments left alone because they are not plain numbers (a variable, a sum) */
  skipped: number
}

const isQuote = (ch: string) => ch === '"' || ch === "'"

/** End of the string literal that starts at `i` (index just after the closing quote). */
function stringEnd(src: string, i: number): number {
  const q = src[i]
  const close = src.startsWith(q.repeat(3), i) ? q.repeat(3) : q
  let j = i + close.length
  while (j < src.length && !src.startsWith(close, j)) j += src[j] === '\\' ? 2 : 1
  return Math.min(j + close.length, src.length)
}

/** Splits the text between a call's parentheses at its top-level commas; the pieces keep their whitespace. */
function splitArgs(text: string): string[] {
  const parts: string[] = []
  let depth = 0
  let from = 0
  for (let i = 0; i < text.length; ) {
    const ch = text[i]
    if (isQuote(ch)) i = stringEnd(text, i)
    else {
      if ('([{'.includes(ch)) depth++
      else if (')]}'.includes(ch)) depth--
      else if (ch === ',' && depth === 0) {
        parts.push(text.slice(from, i))
        from = i + 1
      }
      i++
    }
  }
  parts.push(text.slice(from))
  return parts
}

/**
 * Shifts every cell number the source writes as a plain number (in code, code_z, code_s, circle and circle_z) by
 * `dCol` columns and `dRow` rows. Throws a RangeError naming the cell when one would leave the mat.
 */
export function migrateCells(source: string, dCol: number, dRow: number): Migration {
  let changed = 0
  let skipped = 0
  const shift = (cell: number): number => {
    const col = (cell % GRID) + dCol
    const row = Math.floor(cell / GRID) + dRow
    if (cell < 0 || cell >= GRID * GRID || col < 0 || col >= GRID || row < 0 || row >= GRID) {
      throw new RangeError(`Клетка ${cell} при переносе вышла бы за коврик`)
    }
    changed++
    return col + GRID * row
  }

  let out = ''
  for (let i = 0; i < source.length; ) {
    const ch = source[i]
    if (ch === '#') {
      const end = source.indexOf('\n', i)
      const stop = end < 0 ? source.length : end
      out += source.slice(i, stop)
      i = stop
      continue
    }
    if (isQuote(ch)) {
      const end = stringEnd(source, i)
      out += source.slice(i, end)
      i = end
      continue
    }
    const call = ch === '.' ? /^\.(code_s|code_z|code|circle_z|circle)\(/.exec(source.slice(i, i + 11)) : null
    if (!call) {
      out += ch
      i++
      continue
    }
    const start = i + call[0].length
    let depth = 1
    let k = start
    while (k < source.length && depth > 0) {
      if (isQuote(source[k])) k = stringEnd(source, k)
      else {
        if (source[k] === '(') depth++
        else if (source[k] === ')') depth--
        k++
      }
    }
    const args = splitArgs(source.slice(start, k - 1))
    for (const at of CELL_ARGS[call[1]]) {
      const index = at === 'text' ? 0 : at
      const piece = args[index]
      if (piece === undefined) continue
      if (at === 'text') {
        const words = /^(\s*)(['"])([\d\s]*)\2(\s*)$/.exec(piece)
        if (words) args[index] = `${words[1]}${words[2]}${words[3].replace(/\d+/g, (d) => String(shift(Number(d))))}${words[2]}${words[4]}`
        else skipped++
      } else {
        const num = /^(\s*)(\d+)(\s*)$/.exec(piece)
        if (num) args[index] = `${num[1]}${shift(Number(num[2]))}${num[3]}`
        else skipped++
      }
    }
    out += call[0] + args.join(',') + ')'
    i = k
  }
  return { source: out, changed, skipped }
}
