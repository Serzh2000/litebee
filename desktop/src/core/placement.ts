/**
 * Editing the code of a show for what a person does on the map: stand a drone on another cell, or add one more drone.
 * Both work on the text of the Python file, so the code stays the one truth and Ctrl+Z undoes them.
 */
import { MAX_DRONES, START_HEIGHT_CM, startCells } from './project'
import { joinDrones, splitDrones } from './sections'
import { FULL, cellInArea, type Area } from './area'
import type { Show } from './show'

export interface Edit {
  source: string
  /** a reason in Russian when nothing could be done */
  error?: string
}

const COLORS = ['green', 'blue', 'yellow', 'red', 'cyan', 'purple', 'white']
const DRONE_LINE = /^([A-Za-z_]\w*)\s*=\s*show\.drone\(\s*(\d+)\s*\)/
const FIRST_MOVE = /^(\s*)([A-Za-z_]\w*)\.(code|code_z)\(\s*(\d+)\s*,\s*(?:(\d+(?:\.\d+)?)\s*[,)]|[^,)]*[,)])/
const TAKEOFF = /^\s*[A-Za-z_]\w*\.takeoff\(/

/**
 * The cell that is free to stand on: inside the shown area and at least two cells (80 cm) from every start and every
 * route of the show; the lattice of starts is tried first, then any cell, then the one that is farthest.
 */
export function freeStartCell(show: Show, area: Area = FULL): number {
  // every route of the show, in cells: a new drone only stands, so it must stay clear of all of them
  const legs = show.drones.flatMap((d) => d.path.map((s) => [s.p0[0] / 40, s.p0[1] / 40, s.p1[0] / 40, s.p1[1] / 40] as const))
  const starts = show.drones.flatMap((d) => d.steps.filter((s) => s.kind === 'code' || s.kind === 'code_z').map((s) => [(Number(s.args.cell) % 12), Math.floor(Number(s.args.cell) / 12)] as const))
  const toLeg = (x: number, y: number, [x0, y0, x1, y1]: readonly [number, number, number, number]) => {
    const dx = x1 - x0
    const dy = y1 - y0
    const len = dx * dx + dy * dy
    const k = len === 0 ? 0 : Math.max(0, Math.min(1, ((x - x0) * dx + (y - y0) * dy) / len))
    return Math.hypot(x - (x0 + k * dx), y - (y0 + k * dy))
  }
  const gap = (c: number) => {
    const x = c % 12
    const y = Math.floor(c / 12)
    return Math.min(99, ...legs.map((l) => toLeg(x, y, l)), ...starts.map(([sx, sy]) => Math.hypot(x - sx, y - sy)))
  }
  const cells = Array.from({ length: 144 }, (_, c) => c).filter((c) => cellInArea(area, c))
  const lattice = startCells(144).find((c) => cellInArea(area, c) && gap(c) >= 2)
  if (lattice !== undefined) return lattice
  const clear = cells.find((c) => gap(c) >= 2)
  if (clear !== undefined) return clear
  // a crowded area: the cell of it that is farthest from every route (the checks warn if it is still too close)
  return cells.reduce((best, c) => (gap(c) > gap(best) ? c : best), cells[0] ?? 0)
}

/** One more drone after the last one: calibrates, takes off, shows a colour, stands on a free cell and lands. */
export function addDrone(source: string, show: Show, area: Area = FULL): Edit {
  const number = Math.max(0, ...show.drones.map((d) => d.number)) + 1
  if (show.drones.length >= MAX_DRONES) return { source, error: `В шоу уже ${MAX_DRONES} дронов: больше добавить нельзя` }
  const cell = freeStartCell(show, area)
  const block = [
    `d = show.drone(${number})`,
    'd.calibrate(5)',
    `d.takeoff(${START_HEIGHT_CM}, 5)`,
    `d.rgb('${COLORS[(number - 1) % COLORS.length]}')`,
    `d.code(${cell}, 1)`,
    `d.set_z(${START_HEIGHT_CM}, 5)`,
    "d.rgb('black')",
    'd.land()',
  ].join('\n')
  // a file written on Windows has \r\n at the ends of its lines: the new lines follow it
  const eol = source.includes('\r\n') ? '\r\n' : '\n'
  const body = source.endsWith('\n') ? source : source + eol
  return { source: `${body}${eol}${block.replace(/\n/g, eol)}${eol}` }
}

/**
 * Stands drone `number` on `cell`: the cell of its first short move is changed, or such a move is put right after the
 * take-off. A drone that is made by a loop (not by a plain `d = show.drone(N)` line) cannot be edited this way.
 */
export function setStartCell(source: string, number: number, cell: number): Edit {
  const split = splitDrones(source)
  const section = split?.sections.find((s) => s.number === number)
  if (!split || !section) return { source, error: 'Дрон создан не отдельным блоком d = show.drone(N): поменяйте клетку в коде руками' }
  const lines = section.text.split('\n')
  const header = lines.findIndex((l) => DRONE_LINE.test(l))
  const name = header >= 0 ? (DRONE_LINE.exec(lines[header])?.[1] ?? 'd') : 'd'
  // the first move to a cell; it is the start when it is short (a second or less), as in every example of the app
  const move = lines.findIndex((l) => FIRST_MOVE.test(l))
  if (move >= 0) {
    const m = FIRST_MOVE.exec(lines[move])!
    if (m[5] !== undefined && Number(m[5]) <= 1) {
      lines[move] = lines[move].replace(/(\.(?:code|code_z)\(\s*)\d+/, `$1${cell}`)
      return { source: joinDrones(split, number, lines.join('\n')) }
    }
  }
  const takeoff = lines.findIndex((l) => TAKEOFF.test(l))
  if (takeoff < 0) return { source, error: 'У дрона нет взлёта: сначала добавьте d.takeoff(...)' }
  // after the take-off and the colour lines that follow it
  let at = takeoff + 1
  while (at < lines.length && /^\s*[A-Za-z_]\w*\.rgb\(/.test(lines[at])) at++
  const CR = String.fromCharCode(13)
  const cr = lines[takeoff].endsWith(CR) ? CR : ''
  lines.splice(at, 0, `${name}.code(${cell}, 1)${cr}`)
  return { source: joinDrones(split, number, lines.join('\n')) }
}
