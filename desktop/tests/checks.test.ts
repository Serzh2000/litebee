import { describe, expect, it } from 'vitest'
import { checkShow, resolveMaxHeight } from '../src/core/checks'
import { buildShow, type ShowData } from '../src/core/show'
import myDream from '../shows/my_dream.json'
import myPeople from '../shows/my_people_my_country_5.json'
import goldenDream from './golden/my_dream.json'
import goldenPeople from './golden/my_people_my_country_5.json'

const CASES: [string, ShowData, any][] = [
  ['my_dream', myDream as unknown as ShowData, goldenDream],
  ['my_people_my_country_5', myPeople as unknown as ShowData, goldenPeople],
]

describe.each(CASES)('the checks match the Python ones: %s', (_name, data, golden) => {
  const isApproach = (f: { message: string }) => f.message.includes('сближаются')

  it('gives the same findings in the same order with the same wording', () => {
    const got = checkShow(buildShow(data), { maxHeightCm: 150, strictUpload: true })
    const want = golden.findings as any[]
    // Pairs that come as close as each other tie to a micrometre; Python orders such ties by floating-point noise.
    // Everything else keeps its order; the approach warnings are compared as a set.
    expect(got.filter((f) => !isApproach(f)).map((f) => [f.level, f.message, f.drone, f.line])).toEqual(
      want.filter((f) => !isApproach(f)).map((f) => [f.level, f.message, f.drone, f.line]),
    )
    const key = (f: any) => `${f.level}|${f.message}|${f.drone}|${f.line}`
    expect(got.filter(isApproach).map(key).sort()).toEqual(want.filter(isApproach).map(key).sort())
    expect(got).toHaveLength(want.length)
  })

  it('has the same times', () => {
    const got = checkShow(buildShow(data), { maxHeightCm: 150, strictUpload: true })
    const times = (list: any[]) => list.map((f) => (f.t === null ? 'null' : f.t.toFixed(3))).sort()
    expect(times(got)).toEqual(times(golden.findings))
  })
})

describe('limits', () => {
  it('keeps the height limit between 20 and 200 cm', () => {
    expect(resolveMaxHeight()).toBe(150)
    expect(resolveMaxHeight(20)).toBe(20)
    expect(resolveMaxHeight(200)).toBe(200)
    for (const bad of [19, 201, 150.5, NaN]) expect(() => resolveMaxHeight(bad)).toThrow(RangeError)
  })

  it('refuses a show with no drones with a warning, not a crash', () => {
    const empty = checkShow(buildShow({ name: 'x', drones: {} }))
    expect(empty).toHaveLength(1)
    expect(empty[0].level).toBe('warn')
  })

  it('raising the limit removes the height errors', () => {
    const show = buildShow(myDream as unknown as ShowData)
    expect(checkShow(show, { maxHeightCm: 150, strictUpload: true }).filter((f) => f.level === 'error').length).toBeGreaterThan(0)
    expect(checkShow(show, { maxHeightCm: 170 }).filter((f) => f.level === 'error')).toHaveLength(0)
  })
})
