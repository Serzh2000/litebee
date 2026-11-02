import { describe, expect, it } from 'vitest'
import { linesAt } from '../src/core/now'
import { buildShow, type ShowData } from '../src/core/show'

const data: ShowData = {
  name: 't',
  drones: {
    '1': [
      { kind: 'calibrate', seconds: 5, args: {}, line: 4 },
      { kind: 'takeoff', seconds: 5, args: { z: 100 }, line: 5 },
      { kind: 'rgb', seconds: 0, args: { color: 'green', rgb: [0, 255, 0] }, line: 6 },
      { kind: 'code', seconds: 4, args: { cell: 25 }, line: 7 },
      { kind: 'rgb', seconds: 0, args: { color: 'blue', rgb: [0, 0, 255] }, line: 8 },
      { kind: 'code', seconds: 4, args: { cell: 26 }, line: 9 },
    ],
    '2': [{ kind: 'takeoff', seconds: 5, args: { z: 100 }, line: 12 }, { kind: 'code', seconds: 4, args: { cell: 30 }, line: 13 }],
  },
}

describe('lines at a time', () => {
  const show = buildShow(data)

  it('names the running step and the last colour of the selected drone', () => {
    expect(linesAt(show, 2, 1)).toEqual({ run: [4], light: [] })
    expect(linesAt(show, 12, 1)).toEqual({ run: [7], light: [6] })
    expect(linesAt(show, 15, 1)).toEqual({ run: [9], light: [8] })
  })

  it('names the lines of every drone when none is selected', () => {
    expect(linesAt(show, 12, null).run).toEqual([7, 13])
  })
})
