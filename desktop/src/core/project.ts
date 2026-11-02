import type { ShowData, Step } from './show'

/** A project is a show: its name and, per drone number, the steps it flies. It is saved as pretty JSON. */
export const MAX_DRONES = 10
export const START_HEIGHT_CM = 100

/**
 * Where the drones of a new project stand: a lattice two cells (80 cm) apart, the quarter of the mat first, so that
 * drones never touch on the ground. A drone stands on the cell of the first `d.code(...)` of its code.
 */
export function startCells(count: number): number[] {
  const cells: { cell: number; inQuarter: boolean }[] = []
  for (let row = 0; row < 12; row += 2) {
    for (let col = 0; col < 12; col += 2) cells.push({ cell: col + 12 * row, inQuarter: col < 6 && row < 6 })
  }
  cells.sort((a, b) => Number(b.inQuarter) - Number(a.inQuarter))
  return cells.slice(0, count).map((c) => c.cell)
}

/** A new project: every drone calibrates, takes off, shows its colour and lands where it stands (cell = its number). */
export function newProject(name: string, count: number): ShowData {
  const n = Math.min(Math.max(Math.round(count), 1), MAX_DRONES)
  const palette: [string, [number, number, number]][] = [
    ['green', [0, 255, 0]],
    ['blue', [0, 0, 255]],
    ['yellow', [255, 255, 0]],
    ['red', [255, 0, 0]],
    ['cyan', [0, 255, 255]],
  ]
  const drones: Record<string, Step[]> = {}
  const starts = startCells(n)
  for (let i = 1; i <= n; i++) {
    const [color, rgb] = palette[(i - 1) % palette.length]
    drones[String(i)] = [
      { kind: 'calibrate', seconds: 5, args: {}, line: null },
      { kind: 'takeoff', seconds: 5, args: { z: START_HEIGHT_CM }, line: null },
      { kind: 'rgb', seconds: 0, args: { color, rgb }, line: null },
      { kind: 'code', seconds: 1, args: { cell: starts[i - 1] }, line: null },
      { kind: 'set_z', seconds: 5, args: { z: START_HEIGHT_CM }, line: null },
      { kind: 'rgb', seconds: 0, args: { color: 'black', rgb: [0, 0, 0] }, line: null },
      { kind: 'land', seconds: 3, args: {}, line: null },
    ]
  }
  return { name: name.trim() || 'Новый проект', drones }
}

/** The Python source of a new project: the same steps as newProject, written the way a person writes a show. */
export function newSource(name: string, count: number): string {
  const n = Math.min(Math.max(Math.round(count), 1), MAX_DRONES)
  const title = (name.trim() || 'Новый проект').replace(/\\/g, '\\\\').replace(/'/g, "\\'")
  const colors = ['green', 'blue', 'yellow', 'red', 'cyan']
  const starts = startCells(n)
  const blocks = Array.from({ length: n }, (_, i) =>
    [
      `d = show.drone(${i + 1})`,
      'd.calibrate(5)',
      `d.takeoff(${START_HEIGHT_CM}, 5)`,
      `d.rgb('${colors[i % colors.length]}')`,
      `d.code(${starts[i]}, 1)`,
      `d.set_z(${START_HEIGHT_CM}, 5)`,
      "d.rgb('black')",
      'd.land()',
    ].join('\n'),
  )
  return `from litebee_show import Show\n\nshow = Show('${title}')\n\n${blocks.join('\n\n')}\n`
}

export const serializeProject = (data: ShowData): string => JSON.stringify(data, null, 2) + '\n'

/** Reads a saved project. Throws an Error whose message says in Russian what is wrong with the file. */
export function parseProject(text: string): ShowData {
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    throw new Error('Файл не похож на проект: это не JSON.')
  }
  const o = raw as { name?: unknown; drones?: unknown }
  if (!o || typeof o !== 'object' || typeof o.name !== 'string' || !o.drones || typeof o.drones !== 'object') {
    throw new Error('Файл не похож на проект: нет имени или списка дронов.')
  }
  const drones = o.drones as Record<string, unknown>
  for (const [number, steps] of Object.entries(drones)) {
    const ok =
      /^\d+$/.test(number) &&
      Array.isArray(steps) &&
      steps.every((s) => s && typeof s.kind === 'string' && typeof s.seconds === 'number' && typeof s.args === 'object')
    if (!ok) throw new Error(`В проекте испорчен дрон ${number}: шаги записаны неверно.`)
  }
  return raw as ShowData
}

/** A file name for the project: the name without characters Windows refuses. */
export const projectFileName = (name: string, ext = 'json'): string =>
  (name.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '').trim() || 'project') + '.' + ext
