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
