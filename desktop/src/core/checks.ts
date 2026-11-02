/**
 * Show checks. A port of litebee/safety.py check_show: mat bounds, heights, fast cell moves, steps that cannot be
 * uploaded, and the closest approaches. The wording is the same as in Python (tests compare it).
 */
import { areaName, CELL_CM, type Area } from './area'
import { closestApproaches, GRID_CELLS, stepAt, type Show, type Vec3 } from './show'

export const MIN_APPROACH_CM = 60
export const MAX_LEG_SPEED_CM_S = 100
export const MAX_START_DISTANCE_CM = 200
export const DEFAULT_MAX_HEIGHT_CM = 150
export const MIN_TAKEOFF_CM = 20
export const HARD_MAX_HEIGHT_CM = 200

/** Steps the Python app lets through (proven on a live drone before the circle was flown). */
const PROVEN_PY = new Set(['calibrate', 'takeoff', 'rgb', 'code', 'set_z', 'land'])
/** Steps that have flown: the ones above and circle. */
const FLOWN = new Set([...PROVEN_PY, 'circle'])
/** Steps the new app also packs, the way LiteBee Go does (the official examples use them), but nobody has flown yet. */
const OFFICIAL = new Set(['code_z'])

export type Level = 'error' | 'warn' | 'info'

export interface Finding {
  level: Level
  message: string
  drone: number | null
  t: number | null
  line: number | null
}

/** Python's `{value:g}`: the shortest form without a trailing .0. */
function g(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toPrecision(6)))
}

/** Python rounds halves to even, JavaScript rounds them up; the numbers shown here are never exactly .5. */
function fixed0(value: number): string {
  return value.toFixed(0)
}

export function resolveMaxHeight(value: number = DEFAULT_MAX_HEIGHT_CM): number {
  if (!Number.isInteger(value) || value < MIN_TAKEOFF_CM || value > HARD_MAX_HEIGHT_CM) {
    throw new RangeError(`Лимит высоты должен быть целым от ${MIN_TAKEOFF_CM} до ${HARD_MAX_HEIGHT_CM} см`)
  }
  return value
}

function finding(level: Level, message: string, extra: Partial<Finding> = {}): Finding {
  return { level, message, drone: null, t: null, line: null, ...extra }
}

export function checkShow(
  show: Show,
  {
    minDistanceCm = MIN_APPROACH_CM,
    top = 5,
    maxHeightCm = DEFAULT_MAX_HEIGHT_CM,
    area = null as Area | null,
    /** the rules of the Python app: only steps proven on a live drone may be uploaded */
    strictUpload = false,
  } = {},
): Finding[] {
  const limit = resolveMaxHeight(maxHeightCm)
  if (show.drones.length === 0) return [finding('warn', 'В шоу нет ни одного дрона')]
  const out: Finding[] = []

  for (const d of show.drones) {
    const n = d.number
    for (const s of d.steps) {
      for (const key of ['cell', 'cell1', 'cell2']) {
        const c = s.args[key]
        if (c !== undefined && !(c >= 0 && c < GRID_CELLS)) {
          out.push(finding('error', `Дрон ${n}: клетка ${c} вне коврика 0-${GRID_CELLS - 1}`, { drone: n, line: s.line }))
        }
      }
    }

    const zOf = (seg: { p0: Vec3; p1: Vec3 }) => Math.max(seg.p0[2], seg.p1[2])
    const zmax = d.path.reduce((m, seg) => Math.max(m, zOf(seg)), 0)
    if (zmax > limit) {
      const seg = d.path.find((p) => zOf(p) > limit)!
      out.push(
        finding('error', `Дрон ${n}: высота ${g(zmax)} см больше лимита ${limit} см, полёт будет отклонён`, {
          drone: n,
          t: seg.t0,
          line: d.steps[seg.step].line,
        }),
      )
    }

    // Not in the Python checks: the working area is a choice made in the app (the mat folded in four).
    if (area) {
      const lo = [CELL_CM * area.col0 - CELL_CM / 2, CELL_CM * area.row0 - CELL_CM / 2]
      const hi = [CELL_CM * (area.col0 + area.cols) - CELL_CM / 2, CELL_CM * (area.row0 + area.rows) - CELL_CM / 2]
      const outside = (p: Vec3) => p[0] < lo[0] - 0.5 || p[0] > hi[0] + 0.5 || p[1] < lo[1] - 0.5 || p[1] > hi[1] + 0.5
      const seg = d.path.find((s) => outside(s.p0) || outside(s.p1))
      if (seg) {
        out.push(
          finding('error', `Дрон ${n}: полёт выходит за рабочую область (${areaName(area)}) на ${g(Number(seg.t0.toFixed(1)))} с`, {
            drone: n,
            t: seg.t0,
            line: d.steps[seg.step].line,
          }),
        )
      }
    }

    for (const seg of d.path) {
      if (seg.kind !== 'code' && seg.kind !== 'code_z') continue
      const legCm = Math.hypot(seg.p1[0] - seg.p0[0], seg.p1[1] - seg.p0[1], seg.p1[2] - seg.p0[2])
      const legS = seg.t1 - seg.t0
      const speed = legS > 0 ? legCm / legS : legCm > 0 ? Infinity : 0
      if (speed > MAX_LEG_SPEED_CM_S) {
        const step = d.steps[seg.step]
        const took = legS > 0 ? `за ${g(legS)} с` : 'мгновенно'
        const rate = legS > 0 ? `${fixed0(speed)} см/с` : 'без времени'
        out.push(
          finding(
            'warn',
            `Дрон ${n}: переход на клетку ${step.args.cell} ${took} (${fixed0(legCm)} см, ${rate}) быстрее порога ` +
              `${fixed0(MAX_LEG_SPEED_CM_S)} см/с: дрон может перелететь клетку`,
            { drone: n, t: seg.t0, line: step.line },
          ),
        )
      }
    }

    const allowed = (kind: string) => (strictUpload ? PROVEN_PY.has(kind) : FLOWN.has(kind) || OFFICIAL.has(kind))
    const blocked = d.steps.find((s) => !allowed(s.kind))
    if (blocked) {
      out.push(
        finding(
          'info',
          `Дрон ${n}: загрузка в дрон недоступна. Шаг '${blocked.kind}' (строка ${blocked.line}) пока нельзя загрузить: ` +
            'его формат не проверен на живом дроне (загружаются калибровка, взлёт, высота, посадка, цвет и ' +
            'движение по клеткам code)',
          { drone: n },
        ),
      )
    } else {
      const unproven = d.steps.find((s) => !FLOWN.has(s.kind))
      if (unproven) {
        out.push(
          finding(
            'warn',
            `Дрон ${n}: в миссии шаги, формат которых не проверен на живом дроне (${[...new Set(d.steps.filter((s) => !FLOWN.has(s.kind)).map((s) => s.kind))].join(', ')}): ` +
              'они упакованы так же, как в LiteBee Go. Первый полёт делайте одним дроном и держите под рукой аварийную посадку',
            { drone: n, line: unproven.line },
          ),
        )
      }
      const circle = d.steps.find((s) => s.kind === 'circle')
      if (circle && !strictUpload) {
        out.push(
          finding(
            'info',
            `Дрон ${n}: время круга. В блоке circle время относится к одному полуобороту: на дроне шаг идёт count × время, ` +
              'а симуляция считает время за весь шаг, поэтому круги на дроне будут дольше',
            { drone: n, line: circle.line },
          ),
        )
      }
      const first = d.steps.find((s) => s.kind === 'code')
      if (first) {
        out.push(
          finding(
            'info',
            `Дрон ${n}: шаги движения по клеткам. Перед загрузкой поставьте дрон на клетку ${first.args.cell} ` +
              `(не дальше ${fixed0(MAX_START_DISTANCE_CM)} см) и сделайте короткий взлёт на 50 см: без позиции по ` +
              'коврику дрон не выполнит миссию',
            { drone: n, line: first.line },
          ),
        )
      }
    }
  }

  for (const a of closestApproaches(show, 0.1, top)) {
    if (a.distance < minDistanceCm) {
      const drone = show.drones.find((d) => d.number === a.a)!
      const step = stepAt(drone.steps, drone.path, a.t)
      out.push(
        finding(
          'warn',
          `Дроны ${a.a} и ${a.b} сближаются до ${fixed0(a.distance)} см на ${a.t.toFixed(1)} с (порог ${fixed0(minDistanceCm)} см)`,
          { drone: a.a, t: a.t, line: step ? step.line : null },
        ),
      )
    }
  }
  return out
}
