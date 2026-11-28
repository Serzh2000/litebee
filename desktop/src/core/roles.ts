/**
 * Which drone of the show a drone on the link is, found from where it stands: a drone that knows its place on the mat
 * and stands on the first cell of drone N of the show is drone N. The person's own choice always wins.
 */
import type { Show } from './show'

/** The cell a show drone must stand on before it flies: the target of its first cell move. */
export function startCell(steps: Show['drones'][number]['steps']): number | null {
  const first = steps.find((s) => s.kind === 'code' || s.kind === 'code_z')
  return first ? (first.args.cell as number) : null
}

export interface Placed {
  ip: string
  /** mat cell under the drone; null without a position fix */
  cell: number | null
}

/**
 * IP -> show drone number. A drone gets a number only when exactly one show drone starts on its cell and no other
 * drone on the link stands there, so two drones on one cell, or two show drones that start on one cell, stay open.
 */
export function autoRoles(show: Show, drones: Placed[]): Record<string, number> {
  const startsOn = new Map<number, number[]>()
  for (const d of show.drones) {
    const c = startCell(d.steps)
    if (c !== null) startsOn.set(c, [...(startsOn.get(c) ?? []), d.number])
  }
  const standing = new Map<number, number>()
  for (const d of drones) if (d.cell !== null) standing.set(d.cell, (standing.get(d.cell) ?? 0) + 1)

  const out: Record<string, number> = {}
  for (const d of drones) {
    if (d.cell === null || standing.get(d.cell) !== 1) continue
    const want = startsOn.get(d.cell)
    if (want?.length === 1) out[d.ip] = want[0]
  }
  return out
}

/**
 * Whether the numbers found from cells must stay as they are: once a mission is on board, while armed and in flight.
 * The drones then change cells (the square, the carousel), and numbers read from cells would swap between them.
 */
export const rolesFrozen = (s: { loaded: string[]; armed: boolean; flying: boolean } | null | undefined): boolean =>
  Boolean(s && (s.flying || s.armed || s.loaded.length > 0))

/** The number the person picked for a drone on the link; null: they took the number away. Keyed by IP. */
export type Manual = Record<string, number | null>

/**
 * IP -> show drone number for the drones on the link: the person's choice first, then the number from the cell when
 * nobody holds it. A number goes to one drone only, even when old choices disagree.
 */
export function resolveRoles(manual: Manual, auto: Record<string, number>, ips: string[]): Record<string, number | null> {
  // a number the person gave to any drone, also one silent for now, is not given from a cell
  const taken = new Set(Object.values(manual).filter((n): n is number => n !== null))
  const out: Record<string, number | null> = {}
  const used = new Set<number>()
  for (const ip of ips) {
    let n: number | null
    if (ip in manual) n = manual[ip]
    else n = auto[ip] !== undefined && !taken.has(auto[ip]) ? auto[ip] : null
    if (n !== null && used.has(n)) n = null
    if (n !== null) used.add(n)
    out[ip] = n
  }
  return out
}

/**
 * The person gives number `number` to the drone `ip` (null: takes the number away from whoever has it). Whoever held
 * the number gives it up, also a drone that fell silent for a moment: otherwise it brings the number back with it and
 * two drones fly one program.
 */
export function assignRole(manual: Manual, roles: Record<string, number | null>, number: number, ip: string | null): Manual {
  const next: Manual = { ...manual }
  for (const other of new Set([...Object.keys(roles), ...Object.keys(manual)])) {
    if (roles[other] === number || manual[other] === number) next[other] = null
  }
  if (ip) next[ip] = number
  return next
}

/** What an upload left: the drone's answer and the number whose program went on board. */
export interface Upload {
  ok: boolean
  message: string
  role?: number | null
}

/**
 * Every drone with a number holds the program of that number: uploaded fine, still on board, and the number has not
 * changed since (a new number needs its own program).
 */
export function missionsReady(ips: string[], roles: Record<string, number | null>, uploads: Record<string, Upload>, onBoard: Set<string>): boolean {
  const flying = ips.filter((ip) => roles[ip])
  return flying.length > 0 && flying.every((ip) => uploads[ip]?.ok === true && uploads[ip].role === roles[ip] && onBoard.has(ip))
}
