/**
 * The code of a show split by drone: the lines before the first `d = show.drone(N)` (the head: imports, `show = Show(..)`)
 * and one section per drone, from its `show.drone(N)` line (and the comment lines right above it) to the next drone.
 * The editor can show one section at a time; joining the head and the sections gives the file back unchanged.
 */
export interface Section {
  number: number
  text: string
  /** the 1-based line of the file on which the section starts */
  line: number
  /** how many lines the section has */
  lines: number
}

export interface Sections {
  head: string
  sections: Section[]
}

const DRONE = /^[A-Za-z_]\w*\s*=\s*show\.drone\(\s*(\d+)\s*\)\s*(#.*)?$/

/** Lines with their line ends, so that joining them gives the text back. */
const lines = (text: string) => text.match(/[^\n]*\n|[^\n]+$/g) ?? []

/**
 * Splits the source, or returns null when it cannot be done safely: a `show.drone(` that is not a plain
 * `name = show.drone(N)` line (a loop, a function), a drone number used twice, or no drone at all.
 */
export function splitDrones(source: string): Sections | null {
  const all = lines(source)
  const starts: { index: number; number: number }[] = []
  all.forEach((l, i) => {
    const m = DRONE.exec(l.replace(/\r?\n$/, ''))
    if (m) starts.push({ index: i, number: Number(m[1]) })
  })
  const calls = (source.match(/show\.drone\(/g) ?? []).length
  if (starts.length === 0 || starts.length !== calls) return null
  if (new Set(starts.map((s) => s.number)).size !== starts.length) return null

  // a block starts at its comment lines too, if they sit directly above it
  const from = starts.map((s, k) => {
    let i = s.index
    const floor = k === 0 ? 0 : starts[k - 1].index + 1
    while (i > floor && all[i - 1].trimStart().startsWith('#')) i--
    return i
  })
  const sections = starts.map((s, k): Section => {
    const end = k + 1 < starts.length ? from[k + 1] : all.length
    return { number: s.number, text: all.slice(from[k], end).join(''), line: from[k] + 1, lines: end - from[k] }
  })
  return { head: all.slice(0, from[0]).join(''), sections }
}

/** The file again, with the text of one section replaced. */
export function joinDrones(split: Sections, number: number, text: string): string {
  return split.head + split.sections.map((s) => (s.number === number ? text : s.text)).join('')
}

/** The section that holds a 1-based line of the file, or null for a line of the head. */
export function sectionAt(split: Sections, line: number): Section | null {
  return split.sections.find((s) => line >= s.line && line < s.line + s.lines) ?? null
}
