/**
 * Show model and simulator. A port of litebee/show.py: the same path model, segment by segment, so the numbers
 * match the Python simulator (desktop/tests/show.test.ts compares them with values exported from Python).
 *
 * Position is a QR-mat cell (code = col + 12 * row, 40 cm cells), heights are cm, step durations seconds.
 * Model assumptions, guesses and not measured: a drone starts under its first target cell on the ground, landing
 * takes the step's own seconds, a circle is centred between two cells and `count` is in half turns.
 */
export const CELL_CM = 40
export const GRID_W = 12
export const GRID_CELLS = GRID_W * GRID_W

export type StepKind = 'calibrate' | 'takeoff' | 'rgb' | 'code' | 'code_z' | 'set_z' | 'circle' | 'circle_z' | 'land'

export interface Step {
  kind: StepKind
  seconds: number
  args: Record<string, any>
  line: number | null
}

export interface ShowData {
  name: string
  drones: Record<string, Step[]>
}

export type Vec3 = [number, number, number]

/** One straight (or circle-chord) piece of a drone's path: [t0, t1], from p0 to p1, made by step `step`. */
export interface Segment {
  t0: number
  t1: number
  p0: Vec3
  p1: Vec3
  kind: StepKind
  step: number
}

export type Rgb = [number, number, number]

/** Cell number to (x, y) in cm: x along the columns, y along the rows. */
export function cellXY(code: number): [number, number] {
  return [(code % GRID_W) * CELL_CM, Math.floor(code / GRID_W) * CELL_CM]
}

/** Cell under a point (cm), or null outside the mat. Cells are centred on multiples of 40 cm. */
export function cellFromXY(x: number, y: number): number | null {
  const col = Math.round(x / CELL_CM)
  const row = Math.round(y / CELL_CM)
  return col >= 0 && col < GRID_W && row >= 0 && row < GRID_W ? col + GRID_W * row : null
}

export function droneDuration(steps: Step[]): number {
  return steps.reduce((sum, s) => sum + s.seconds, 0)
}

/** Piecewise path of a drone, as in Drone.path(). */
export function dronePath(steps: Step[]): Segment[] {
  const first = steps.find((s) => 'cell' in s.args)
  let [x, y] = first ? cellXY(first.args.cell) : [0, 0]
  let z = 0
  let t = 0
  const out: Segment[] = []
  steps.forEach((s, idx) => {
    const t1 = t + s.seconds
    let nx = x
    let ny = y
    let nz = z
    if (s.kind === 'takeoff' || s.kind === 'set_z') {
      nz = s.args.z
    } else if (s.kind === 'code') {
      ;[nx, ny] = cellXY(s.args.cell)
    } else if (s.kind === 'code_z') {
      ;[nx, ny] = cellXY(s.args.cell)
      nz = s.args.z
    } else if (s.kind === 'land') {
      nz = 0
    } else if (s.kind === 'circle' || s.kind === 'circle_z') {
      // The centre is the midpoint of the two cells; `count` is in half turns, so the drone orbits through its
      // current position. Which way "cw" turns on the mat is a guess.
      const [ax, ay] = cellXY(s.args.cell1)
      const [bx, by] = cellXY(s.args.cell2)
      const cx = (ax + bx) / 2
      const cy = (ay + by) / 2
      const r = Math.hypot(x - cx, y - cy)
      const aStart = Math.atan2(y - cy, x - cx)
      const turns = s.args.count ?? 1
      const sweep = (s.args.rotate === 'cw' ? -1 : 1) * Math.PI * turns
      const dz = s.args.dz ?? 0
      const n = Math.max(8, Math.trunc(s.seconds * 10))
      for (let i = 0; i < n; i++) {
        const a0 = aStart + (sweep * i) / n
        const a1 = aStart + (sweep * (i + 1)) / n
        out.push({
          t0: t + (s.seconds * i) / n,
          t1: t + (s.seconds * (i + 1)) / n,
          p0: [cx + r * Math.cos(a0), cy + r * Math.sin(a0), z + (dz * i) / n],
          p1: [cx + r * Math.cos(a1), cy + r * Math.sin(a1), z + (dz * (i + 1)) / n],
          kind: s.kind,
          step: idx,
        })
      }
      x = cx + r * Math.cos(aStart + sweep)
      y = cy + r * Math.sin(aStart + sweep)
      z += dz
      t = t1
      return
    }
    out.push({ t0: t, t1, p0: [x, y, z], p1: [nx, ny, nz], kind: s.kind, step: idx })
    x = nx
    y = ny
    z = nz
    t = t1
  })
  return out
}

/** First index whose end time is >= t (Python's bisect_left over the segment ends). */
function firstEndAtOrAfter(path: Segment[], t: number): number {
  let lo = 0
  let hi = path.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (path[mid].t1 < t) lo = mid + 1
    else hi = mid
  }
  return lo
}

/** Index of the segment that holds time t (path.length once the show is over). */
export const segmentIndexAt = firstEndAtOrAfter

export function positionAt(path: Segment[], t: number): Vec3 {
  if (path.length === 0) return [0, 0, 0]
  const i = firstEndAtOrAfter(path, t)
  if (i >= path.length) return path[path.length - 1].p1
  const { t0, t1, p0, p1 } = path[i]
  const k = t1 === t0 ? 0 : (t - t0) / (t1 - t0)
  return [p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k, p0[2] + (p1[2] - p0[2]) * k]
}

/** The step being executed at time t (null for an empty program). */
export function stepAt(steps: Step[], path: Segment[], t: number): Step | null {
  if (path.length === 0) return null
  const i = Math.min(firstEndAtOrAfter(path, t), path.length - 1)
  return steps[path[i].step]
}

/** LED colour at time t: [name, rgb]; the LED is off until the first rgb step. */
export function colorAt(steps: Step[], t: number): [string, Rgb] {
  let cur: [string, Rgb] = ['black', [0, 0, 0]]
  let now = 0
  for (const s of steps) {
    if (now > t) break
    if (s.kind === 'rgb') cur = [s.args.color, s.args.rgb]
    now += s.seconds
  }
  return cur
}

export interface DroneModel {
  number: number
  steps: Step[]
  path: Segment[]
  duration: number
}

export interface Show {
  name: string
  drones: DroneModel[]
  duration: number
  stepCount: number
}

export function buildShow(data: ShowData): Show {
  const drones = Object.keys(data.drones)
    .map(Number)
    .sort((a, b) => a - b)
    .map((number) => {
      const steps = data.drones[String(number)]
      return { number, steps, path: dronePath(steps), duration: droneDuration(steps) }
    })
  return {
    name: data.name,
    drones,
    duration: drones.reduce((m, d) => Math.max(m, d.duration), 0),
    stepCount: drones.reduce((n, d) => n + d.steps.length, 0),
  }
}

export function positionsAt(show: Show, t: number): Map<number, Vec3> {
  return new Map(show.drones.map((d) => [d.number, positionAt(d.path, t)]))
}

export interface Approach {
  distance: number
  t: number
  a: number
  b: number
}

/** Smallest 3D distance between each drone pair, worst `top` pairs (as Show.closest_approaches). */
export function closestApproaches(show: Show, step = 0.1, top = 5): Approach[] {
  const best = new Map<string, Approach>()
  const n = show.drones.length
  for (let t = 0; t <= show.duration; t += step) {
    const pos = show.drones.map((d) => positionAt(d.path, t))
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const distance = Math.hypot(pos[i][0] - pos[j][0], pos[i][1] - pos[j][1], pos[i][2] - pos[j][2])
        const key = `${i}:${j}`
        const prev = best.get(key)
        if (!prev || distance < prev.distance) {
          best.set(key, { distance, t, a: show.drones[i].number, b: show.drones[j].number })
        }
      }
    }
  }
  // Ties (equal to a micrometre) go by time, then by drone numbers: floating-point noise must not decide the order.
  const key = (a: Approach) => Math.round(a.distance * 1e6)
  return [...best.values()]
    .sort((p, q) => key(p) - key(q) || p.t - q.t || p.a - q.a || p.b - q.b)
    .slice(0, top)
}
