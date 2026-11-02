/**
 * Mission of one drone as the drone takes it: a port of litebee/mission.py (packing), drone_to_mission (compiling a
 * show drone) and the upload rules of litebee/safety.py. Only step layouts proven on live drones are packed.
 *
 * Times are cumulative, in 0.1 s, u16 little endian; moveXY data is (row_cm, col_cm) as u16 LE + 8 zero bytes.
 */
import { DEFAULT_MAX_HEIGHT_CM, MAX_START_DISTANCE_CM } from './checks'
import { frame } from './protocol'
import { CELL_CM, GRID_CELLS, GRID_W, cellFromXY, type Step } from './show'

export const CMD = { calibrate: 0, takeoff: 1, autoland: 2, moveXY: 3, moveZ: 5, moveXYZ: 10, circle: 12, rgb: 50 } as const

/** Commands that have flown on a live drone; moveXYZ is packed as LiteBee Go packs it but has not been flown yet. */
export const PROVEN_CMDS: ReadonlySet<number> = new Set([CMD.calibrate, CMD.takeoff, CMD.autoland, CMD.moveXY, CMD.moveZ, CMD.circle, CMD.rgb])
/** The longest wait in one place. Official shows hold drones 12-18 s while others fly; this catches typos like 600 s. */
export const MAX_HOVER_S = 60
export const MIN_VOLTS = 7.0
export const MAX_STEPS = 255

export interface MissionStep {
  cmd: number
  /** cumulative end time, 0.1 s */
  tEnd: number
  data: Uint8Array
}

export type Mission = MissionStep[]

/** Why a show drone cannot be compiled into a mission. */
export class UploadUnsupported extends Error {}

const ticks = (seconds: number) => Math.round(seconds * 10)

/** 12 data bytes with little-endian i16/u16 values at the given offsets (no Buffer: this runs in the page too). */
function data12(...fields: [offset: number, value: number][]): Uint8Array {
  const b = new Uint8Array(12)
  const v = new DataView(b.buffer)
  for (const [at, value] of fields) v.setUint16(at, value, true)
  return b
}

function dataI16(...fields: [offset: number, value: number][]): Uint8Array {
  const b = new Uint8Array(12)
  const v = new DataView(b.buffer)
  for (const [at, value] of fields) v.setInt16(at, value, true)
  return b
}

const u16 = (b: Uint8Array, at: number) => new DataView(b.buffer, b.byteOffset).getUint16(at, true)
const zData = (z: number) => data12([0, Math.round(z)])
const xyData = (cell: number) => data12([0, CELL_CM * Math.floor(cell / GRID_W)], [2, CELL_CM * (cell % GRID_W)])

const rowCol = (cell: number): [number, number] => [CELL_CM * Math.floor(cell / GRID_W), CELL_CM * (cell % GRID_W)]
/** The JavaScript of LiteBee Go: Math.floor(10 * seconds). */
const goTicks = (seconds: number) => Math.floor(10 * seconds)

/** RGB step data; the wire order is g, r, b. */
const rgbData = (r: number, g: number, b: number) => Uint8Array.from([5, 0, 2, 255, g, r, b, 0, 0, 0, 0, 0])

/** Compile a drone's program. Throws UploadUnsupported for steps whose wire layout is not verified (circle, code_z). */
export function compileDrone(steps: Step[]): Mission {
  let now = 0
  const out: Mission = []
  for (const s of steps) {
    if (s.kind === 'calibrate') {
      now += ticks(s.seconds)
      out.push({ cmd: CMD.calibrate, tEnd: now, data: new Uint8Array(12) })
    } else if (s.kind === 'takeoff') {
      now += ticks(s.seconds)
      out.push({ cmd: CMD.takeoff, tEnd: now, data: zData(s.args.z) })
    } else if (s.kind === 'set_z') {
      now += ticks(s.seconds)
      out.push({ cmd: CMD.moveZ, tEnd: now, data: zData(s.args.z) })
    } else if (s.kind === 'rgb') {
      const [r, g, b] = s.args.rgb
      out.push({ cmd: CMD.rgb, tEnd: now, data: rgbData(r, g, b) })
    } else if (s.kind === 'code') {
      if (!(s.args.cell >= 0 && s.args.cell < GRID_CELLS)) {
        throw new UploadUnsupported(`Клетка ${s.args.cell} (строка ${s.line}) вне коврика 0-${GRID_CELLS - 1}`)
      }
      now += ticks(s.seconds)
      out.push({ cmd: CMD.moveXY, tEnd: now, data: xyData(s.args.cell) })
    } else if (s.kind === 'code_z') {
      if (!(s.args.cell >= 0 && s.args.cell < GRID_CELLS)) {
        throw new UploadUnsupported(`Клетка ${s.args.cell} (строка ${s.line}) вне коврика 0-${GRID_CELLS - 1}`)
      }
      // moveXYZ as LiteBee Go packs it: row, col and the absolute height, all i16, the time is floor(10 * seconds)
      now += goTicks(s.seconds)
      const [row, col] = rowCol(s.args.cell)
      out.push({ cmd: CMD.moveXYZ, tEnd: now, data: dataI16([0, row], [2, col], [4, Math.round(s.args.z)]) })
    } else if (s.kind === 'circle') {
      const { count, cell1, cell2 } = s.args
      for (const c of [cell1, cell2]) {
        if (!(c >= 0 && c < GRID_CELLS)) throw new UploadUnsupported(`Клетка ${c} (строка ${s.line}) вне коврика 0-${GRID_CELLS - 1}`)
      }
      if (!Number.isInteger(count) || count < 1 || count > 255) {
        throw new UploadUnsupported(`circle: число полуоборотов ${count} (строка ${s.line}) должно быть целым от 1 до 255`)
      }
      // The block's TIME is ONE half turn: the whole step lasts count x TIME, as in LiteBee Go (docs/PROTOCOL_STEPS.md, 5.1).
      const t = goTicks(s.seconds)
      if (t < 1 || t > 0xffff) throw new UploadUnsupported(`circle: время полуоборота ${s.seconds} с (строка ${s.line}) не подходит`)
      const [r1, c1] = rowCol(cell1)
      const [r2, c2] = rowCol(cell2)
      const data = dataI16([0, Math.floor(0.5 * (r1 + r2))], [2, Math.floor(0.5 * (c1 + c2))])
      new DataView(data.buffer).setUint16(4, t, true)
      data[6] = count
      data[8] = s.args.rotate === 'ccw' ? 1 : 0
      now += t * count
      out.push({ cmd: CMD.circle, tEnd: now, data })
    } else if (s.kind === 'land') {
      out.push({ cmd: CMD.autoland, tEnd: now, data: new Uint8Array(12) })
    } else {
      throw new UploadUnsupported(
        `Шаг «${s.kind}» (строка ${s.line}) пока нельзя загрузить: его раскладка байтов не известна ` +
          '(загружаются калибровка, взлёт, высота, посадка, цвет, движение по клеткам code и code_z и круги circle)',
      )
    }
  }
  if (out.length === 0) throw new UploadUnsupported('У дрона нет шагов')
  if (out.length > MAX_STEPS) throw new UploadUnsupported(`У дрона ${out.length} шагов: в миссию помещается не больше ${MAX_STEPS}`)
  if (out[out.length - 1].tEnd > 0xffff) throw new UploadUnsupported('Шоу длиннее 6553 секунд')
  return out
}

/** Frames of the step packets, in order. */
export function missionFrames(m: Mission): Uint8Array[] {
  return m.map((s, i) => frame([19, 0, 3, 2, m.length, 0, i + 1, 0, s.tEnd & 255, s.tEnd >> 8, s.cmd, ...s.data]))
}

/** The value the drone must report back: the sum of the cmd bytes, u16. */
export const missionChecksum = (m: Mission) => m.reduce((n, s) => n + s.cmd, 0) & 0xffff

export const clearMissionFrame = () => frame([1, 0, 3, 0, 1])

const heightOf = (s: MissionStep) =>
  s.cmd === CMD.takeoff || s.cmd === CMD.moveZ ? u16(s.data, 0) : s.cmd === CMD.moveXYZ ? u16(s.data, 4) : 0

export const missionMaxHeight = (m: Mission) => m.reduce((h, s) => Math.max(h, heightOf(s)), 0)

/** Longest moveZ that keeps the current height (a hover), seconds. */
export function missionMaxHover(m: Mission): number {
  let longest = 0
  let z = 0
  let prev = 0
  for (const s of m) {
    const dur = (s.tEnd - prev) / 10
    if (s.cmd === CMD.moveZ && heightOf(s) === z) longest = Math.max(longest, dur)
    if (s.cmd === CMD.takeoff || s.cmd === CMD.moveZ || s.cmd === CMD.moveXYZ) z = heightOf(s)
    else if (s.cmd === CMD.autoland) z = 0
    prev = s.tEnd
  }
  return longest
}

/** First cell the drone moves to, or null when the mission has no cell moves. */
export function firstMoveCell(m: Mission): number | null {
  const s = m.find((x) => x.cmd === CMD.moveXY || x.cmd === CMD.moveXYZ)
  if (!s) return null
  return u16(s.data, 2) / CELL_CM + GRID_W * (u16(s.data, 0) / CELL_CM)
}

/** Why a drone at (x, y) cm may not take a mission whose first cell move goes to `firstCell`; null when it may. */
export function positionProblem(firstCell: number, x: number, y: number): string | null {
  if (!x && !y) {
    return 'У дрона нет позиции по коврику. Поставьте его на коврик и сделайте короткий взлёт на 50 см, затем повторите'
  }
  const tx = (firstCell % GRID_W) * CELL_CM
  const ty = Math.floor(firstCell / GRID_W) * CELL_CM
  const d = Math.hypot(x - tx, y - ty)
  if (d <= MAX_START_DISTANCE_CM) return null
  const cur = cellFromXY(x, y)
  const where = cur !== null ? `на клетке ${cur}` : 'вне коврика'
  return (
    `Дрон стоит ${where}, а шоу ждёт его на клетке ${firstCell}: расстояние ${d.toFixed(0)} см больше ` +
    `${MAX_START_DISTANCE_CM} см. Переставьте дрон ближе к клетке ${firstCell} и повторите`
  )
}

export interface DroneState {
  batteryV: number
  x: number
  y: number
}

/**
 * Everything that must hold before a mission goes to a drone (litebee/safety.py preflight): the mission can fly,
 * its height and hover are within the limits, the battery is enough, and for cell moves the drone stands near the
 * first cell. Returns the reasons it may not go; empty when it may.
 */
export function uploadProblems(m: Mission, drone: DroneState, maxHeightCm = DEFAULT_MAX_HEIGHT_CM): string[] {
  const out: string[] = []
  const flies = m.some((s) => s.cmd !== CMD.rgb)
  if (!flies) return out
  if (missionMaxHeight(m) > maxHeightCm) out.push(`Высота ${missionMaxHeight(m)} см больше лимита ${maxHeightCm} см`)
  if (missionMaxHover(m) > MAX_HOVER_S) out.push(`Зависание ${missionMaxHover(m)} с больше лимита ${MAX_HOVER_S} с`)
  if (drone.batteryV < MIN_VOLTS) out.push(`Батарея ${drone.batteryV.toFixed(1)} В ниже ${MIN_VOLTS.toFixed(1)} В, полёт отменён`)
  const first = firstMoveCell(m)
  if (first !== null) {
    const why = positionProblem(first, drone.x, drone.y)
    if (why) out.push(why)
  }
  return out
}

/** Anything other than pure LED steps may spin the motors. */
export const missionCanFly = (m: Mission) => m.some((s) => s.cmd !== CMD.rgb)

export const missionSeconds = (m: Mission) => (m.length ? m[m.length - 1].tEnd : 0) / 10

/** Names of the steps of a mission that nobody has flown yet (empty: everything is proven). */
export function unprovenSteps(m: Mission): string[] {
  const name: Record<number, string> = { [CMD.moveXYZ]: 'code_z', [CMD.circle]: 'circle' }
  return [...new Set(m.filter((s) => !PROVEN_CMDS.has(s.cmd)).map((s) => name[s.cmd] ?? String(s.cmd)))]
}
