import { stepAt, type Show } from './show'

/** The lines of the source that are in effect at time t. */
export interface NowLines {
  /** the step that is running (a move, a climb, a circle, a wait), per drone */
  run: number[]
  /** the last colour command that has already happened, per drone */
  light: number[]
}

/**
 * Which lines of the show source are in effect at time t: for the selected drone, or for every drone when none is
 * selected. A step belongs to its drone, so in a show written drone after drone these are separate lines; in a show
 * with a loop over drones several drones may point at the same line.
 */
export function linesAt(show: Show, t: number, only: number | null): NowLines {
  const run = new Set<number>()
  const light = new Set<number>()
  for (const d of show.drones) {
    if (only !== null && d.number !== only) continue
    const step = stepAt(d.steps, d.path, t)
    if (step?.line) run.add(step.line)
    let now = 0
    let colour: number | null = null
    for (const s of d.steps) {
      if (now > t) break
      if (s.kind === 'rgb' && s.line) colour = s.line
      now += s.seconds
    }
    if (colour !== null) light.add(colour)
  }
  return { run: [...run].sort((a, b) => a - b), light: [...light].sort((a, b) => a - b) }
}
