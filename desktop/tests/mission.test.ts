import { createHash } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import { compileDrone, missionChecksum, missionFrames, missionMaxHeight, missionMaxHover, unprovenSteps, UploadUnsupported, uploadProblems } from '@core/mission'
import type { Step } from '@core/show'
import square from '../shows/quarter_square.json'
import dream from '../shows/my_dream.json'

const drone = (data: { drones: Record<string, unknown> }, n: string) => data.drones[n] as Step[]

describe('mission', () => {
  it('packs a drone the same bytes as litebee/mission.py', () => {
    const m = compileDrone(drone(square, '1'))
    expect(m).toHaveLength(10)
    expect(missionChecksum(m)).toBe(118)
    expect(missionMaxHeight(m)).toBe(100)
    expect(missionMaxHover(m)).toBe(0)
    const all = Buffer.concat(missionFrames(m))
    expect(all.toString('hex').slice(0, 64)).toBe('fa130003020a000100320000000000000000000000000000d130fa130003020a')
    // the whole upload, hashed in Python: md5 of the 10 concatenated frames
    expect(createHash('md5').update(all).digest('hex')).toBe('f05fdeeea9487a037396bac2d75fd03a')
  })

  const step = (kind: string, seconds: number, args: Record<string, unknown>): Step => ({ kind, seconds, args, line: 1 }) as Step
  const hex = (b: Uint8Array) => Buffer.from(b).toString('hex')

  it('packs circle and code_z as step_packers.py (the packers of LiteBee Go) does', () => {
    // values printed by step_packers.step_circle / step_move_xyz_cell
    const [c1] = compileDrone([step('circle', 13, { count: 2, cell1: 66, cell2: 77, rotate: 'cw' })])
    expect([c1.cmd, c1.tEnd, hex(c1.data)]).toEqual([12, 260, 'dc00dc008200020000000000']) // lasts count x TIME
    const [c2] = compileDrone([step('circle', 2.5, { count: 3, cell1: 66, cell2: 77, rotate: 'ccw' })])
    expect([c2.cmd, c2.tEnd, hex(c2.data)]).toEqual([12, 75, 'dc00dc001900030001000000'])
    const [z1] = compileDrone([step('code_z', 2, { cell: 85, z: 130 })])
    expect([z1.cmd, z1.tEnd, hex(z1.data)]).toEqual([10, 20, '180128008200000000000000'])
    const [z2] = compileDrone([step('code_z', 0.3, { cell: 13, z: 90 })])
    expect([z2.cmd, z2.tEnd, hex(z2.data)]).toEqual([10, 3, '280028005a00000000000000'])
  })

  it('compiles the whole of My Dream and flags only the step nobody has flown (code_z; circle has flown)', () => {
    for (const n of Object.keys(dream.drones)) {
      const m = compileDrone(drone(dream, n))
      expect(unprovenSteps(m).sort()).toEqual(['code_z'])
    }
    expect(unprovenSteps(compileDrone(drone(square, '1')))).toEqual([])
  })

  it('still refuses what has no known layout (circle_z)', () => {
    expect(() => compileDrone([step('circle_z', 3, { cell1: 1, cell2: 2, dz: 20, rotate: 'cw' })])).toThrow(UploadUnsupported)
    expect(() => compileDrone([step('circle', 3, { count: 0, cell1: 1, cell2: 2, rotate: 'cw' })])).toThrow(/полуоборотов/)
  })

  it('judges the battery, the height and the standing place before an upload', () => {
    const m = compileDrone(drone(square, '1')) // first move: cell 13 (40, 40)
    expect(uploadProblems(m, { batteryV: 7.9, x: 40, y: 40 })).toEqual([])
    expect(uploadProblems(m, { batteryV: 6.9, x: 40, y: 40 })[0]).toMatch(/Батарея 6,9|Батарея 6.9/)
    expect(uploadProblems(m, { batteryV: 7.9, x: 0, y: 0 })[0]).toMatch(/нет позиции/)
    expect(uploadProblems(m, { batteryV: 7.9, x: 440, y: 440 })[0]).toMatch(/Переставьте дрон/)
    expect(uploadProblems(m, { batteryV: 7.9, x: 40, y: 40 }, 80)[0]).toMatch(/больше лимита 80/)
  })
})

describe('two-drone examples', () => {
  const pairs = import.meta.glob('../shows/quarter_pair_*.json', { eager: true, import: 'default' }) as Record<string, { drones: Record<string, unknown> }>
  it('every one has two drones and uploads with nothing but proven steps', () => {
    expect(Object.keys(pairs)).toHaveLength(8)
    for (const [file, show] of Object.entries(pairs)) {
      expect(Object.keys(show.drones), file).toHaveLength(2)
      for (const n of Object.keys(show.drones)) expect(unprovenSteps(compileDrone(show.drones[n] as Step[])), `${file} ${n}`).toEqual([])
    }
  })
})

describe('hover limit', () => {
  const hold = (seconds: number): Step[] => [
    { kind: 'calibrate', seconds: 5, args: {}, line: 1 },
    { kind: 'takeoff', seconds: 5, args: { z: 100 }, line: 2 },
    { kind: 'set_z', seconds, args: { z: 100 }, line: 3 },
    { kind: 'land', seconds: 3, args: {}, line: 4 },
  ] as Step[]
  it('lets a drone wait 18 s for the others, as the official shows do, but not 70 s', () => {
    const ok = { batteryV: 7.9, x: 0, y: 0 }
    expect(uploadProblems(compileDrone(hold(18)), ok)).toEqual([])
    expect(uploadProblems(compileDrone(hold(70)), ok)[0]).toMatch(/Зависание 70 с больше лимита 60 с/)
  })
})

describe('five to eight drones in a quarter', () => {
  const many = import.meta.glob('../shows/quarter_{five,six,seven,eight}_*.json', { eager: true, import: 'default' }) as Record<string, { drones: Record<string, unknown> }>
  it('upload with proven steps only and stay inside the six by six cells of the quarter', () => {
    expect(Object.keys(many)).toHaveLength(6)
    for (const [file, show] of Object.entries(many)) {
      const n = Object.keys(show.drones).length
      expect(n, file).toBeGreaterThanOrEqual(5)
      expect(n, file).toBeLessThanOrEqual(8)
      for (const k of Object.keys(show.drones)) {
        const steps = show.drones[k] as Step[]
        expect(unprovenSteps(compileDrone(steps)), `${file} ${k}`).toEqual([])
        for (const s of steps) if (s.kind === 'code') expect((s.args.cell % 12) <= 5 && Math.floor(s.args.cell / 12) <= 5, `${file} ${k}`).toBe(true)
      }
    }
  })
})

describe('the gallery', () => {
  const gallery = import.meta.glob('../shows/gallery/*.json', { eager: true, import: 'default' }) as Record<string, { drones: Record<string, unknown> }>
  it('compiles for upload: only steps that have flown, nothing over five minutes', () => {
    const files = Object.keys(gallery)
    expect(files.length).toBeGreaterThanOrEqual(100)
    for (const [file, show] of Object.entries(gallery)) {
      for (const k of Object.keys(show.drones)) {
        const steps = show.drones[k] as Step[]
        const mission = compileDrone(steps)
        const unproven = unprovenSteps(mission)
        expect(unproven, `${file} ${k}`).toEqual([]) // circle has flown, the gallery has no code_z
        expect(missionChecksum(mission), `${file} ${k}`).toBeGreaterThan(0)
        expect(mission[mission.length - 1].tEnd / 10, `${file} ${k}`).toBeLessThanOrEqual(310)
      }
    }
  })
})
