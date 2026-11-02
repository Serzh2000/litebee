import { describe, expect, it } from 'vitest'
import { buildShow, cellFromXY, cellXY, colorAt, positionAt, positionsAt, stepAt, type ShowData } from '../src/core/show'
import myDream from '../shows/my_dream.json'
import myPeople from '../shows/my_people_my_country_5.json'
import goldenDream from './golden/my_dream.json'
import goldenPeople from './golden/my_people_my_country_5.json'

const CASES: [string, ShowData, any][] = [
  ['my_dream', myDream as unknown as ShowData, goldenDream],
  ['my_people_my_country_5', myPeople as unknown as ShowData, goldenPeople],
]

describe.each(CASES)('the simulator matches the Python one: %s', (_name, data, golden) => {
  const show = buildShow(data)

  it('has the same size', () => {
    expect(show.name).toBe(golden.name)
    expect(show.stepCount).toBe(golden.step_count)
    expect(show.duration).toBeCloseTo(golden.duration, 9)
    expect(show.drones.map((d) => d.number)).toEqual(Object.keys(golden.drones).map(Number))
  })

  it('has the same paths, positions and LED colours at every sample time', () => {
    const maxDiff = { v: 0 }
    for (const drone of show.drones) {
      const g = golden.drones[String(drone.number)]
      expect(drone.duration).toBeCloseTo(g.duration, 9)
      expect(drone.path.length).toBe(g.segments)
      g.path_head.forEach((seg: any, i: number) => {
        const s = drone.path[i]
        expect([s.t0, s.t1, s.kind, s.step]).toEqual([seg[0], seg[1], seg[4], seg[5]])
        s.p0.forEach((v, k) => expect(v).toBeCloseTo(seg[2][k], 9))
        s.p1.forEach((v, k) => expect(v).toBeCloseTo(seg[3][k], 9))
      })
      golden.times.forEach((t: number, i: number) => {
        const p = positionAt(drone.path, t)
        for (let k = 0; k < 3; k++) maxDiff.v = Math.max(maxDiff.v, Math.abs(p[k] - g.positions[i][k]))
        const [name, rgb] = colorAt(drone.steps, t)
        expect(rgb).toEqual(g.colors[i])
        expect(name).toBe(g.color_names[i])
      })
    }
    expect(maxDiff.v).toBeLessThan(1e-6)
  })
})

describe('cells and steps', () => {
  it('maps cells to centimetres and back, cell 0 at the bottom left', () => {
    expect(cellXY(0)).toEqual([0, 0])
    expect(cellXY(97)).toEqual([40, 320])
    expect(cellXY(143)).toEqual([440, 440])
    expect(cellFromXY(40, 320)).toBe(97)
    expect(cellFromXY(-30, 0)).toBeNull()
    expect(cellFromXY(0, 0)).toBe(0)
  })

  it('knows the step being executed and the positions of all drones', () => {
    const show = buildShow(myDream as unknown as ShowData)
    const d1 = show.drones[0]
    expect(stepAt(d1.steps, d1.path, 0)?.kind).toBe('calibrate')
    expect(positionsAt(show, 0).size).toBe(10)
    expect(positionAt([], 5)).toEqual([0, 0, 0])
  })
})
