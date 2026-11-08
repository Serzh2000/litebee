import { splitDrones } from '@core/sections'
import { stepAt, type DroneModel } from '@core/show'

export interface CodeLine {
  n: number
  text: string
  now: boolean
}

export interface DroneNow {
  /** the line of the source that runs at the time (null: none) */
  line: number | null
  state: 'runs' | 'waits' | 'done'
  /** the trimmed text of that line */
  text: string
  /** the line, with the one before and the one after, inside this drone's own block of the code */
  around: CodeLine[]
}

/** The first and last line of each drone's block of the source (by drone number). */
export function blockBounds(source: string): Map<number, [number, number]> {
  const m = new Map<number, [number, number]>()
  for (const s of splitDrones(source)?.sections ?? []) m.set(s.number, [s.line, s.line + s.lines - 1])
  return m
}

/** The line of the code a drone runs at time t, with the lines around it. */
export function droneNow(d: DroneModel, file: string[], bounds: Map<number, [number, number]>, t: number): DroneNow {
  const [first, last] = bounds.get(d.number) ?? [1, file.length]
  const step = stepAt(d.steps, d.path, t)
  const line = step?.line ?? null
  const state: DroneNow['state'] = step && line ? 'runs' : t >= d.duration ? 'done' : 'waits'
  const around =
    line === null ? [] : [line - 1, line, line + 1].filter((n) => n >= first && n <= last).map((n) => ({ n, text: file[n - 1] ?? '', now: n === line }))
  return { line, state, around, text: line ? (file[line - 1] ?? '').trim() : '' }
}
