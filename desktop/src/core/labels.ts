import type { StepKind } from './show'

/** Names of steps for hints and lists (a port of the tables in app/cue_sheet.py). */
export const STEP_NAME: Record<StepKind, string> = {
  calibrate: 'калибровка',
  takeoff: 'взлёт',
  land: 'посадка',
  code: 'переход между клетками',
  code_z: 'переход между клетками с высотой',
  set_z: 'смена высоты',
  rgb: 'цвет светодиода',
  circle: 'круг',
  circle_z: 'круг с подъёмом',
}

const n0 = (v: unknown) => String(Math.round(Number(v ?? 0)))

/** A short phrase for a step: "к клетке 25", "взлёт на 100 см". */
export function stepText(kind: StepKind, args: Record<string, any> = {}): string {
  switch (kind) {
    case 'code':
      return `к клетке ${args.cell}`
    case 'code_z':
      return `к клетке ${args.cell}, высота ${n0(args.z)} см`
    case 'takeoff':
      return `взлёт на ${n0(args.z)} см`
    case 'set_z':
      return `высота ${n0(args.z)} см`
    case 'circle':
      return `круг вокруг клеток ${args.cell1} и ${args.cell2}, полуоборотов ${args.count}`
    case 'circle_z':
      return `круг вокруг клеток ${args.cell1} и ${args.cell2} с подъёмом ${n0(args.dz)} см`
    case 'rgb':
      return `цвет ${args.color ?? ''}`.trim()
    default:
      return STEP_NAME[kind] ?? kind
  }
}
