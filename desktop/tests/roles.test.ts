import { describe, expect, it } from 'vitest'
import { autoRoles, startCell } from '@core/roles'
import { buildShow, type ShowData } from '@core/show'
import square from '../shows/quarter_square.json'

const show = buildShow(square as unknown as ShowData) // drones 1-4 start on cells 13, 16, 52, 49

describe('autoRoles', () => {
  it('knows where each drone of the show starts', () => {
    expect(show.drones.map((d) => startCell(d.steps))).toEqual([13, 16, 52, 49])
  })

  it('names a drone after the show drone that starts on its cell', () => {
    const got = autoRoles(show, [
      { ip: 'a', cell: 52 },
      { ip: 'b', cell: 13 },
      { ip: 'c', cell: 99 }, // a cell no drone of the show starts on
      { ip: 'd', cell: null }, // no position yet
    ])
    expect(got).toEqual({ a: 3, b: 1 })
  })

  it('leaves two drones on one cell open', () => {
    expect(autoRoles(show, [{ ip: 'a', cell: 13 }, { ip: 'b', cell: 13 }])).toEqual({})
  })

  it('leaves a cell open when two show drones start on it', () => {
    const twin = buildShow({
      name: 't',
      drones: {
        '1': [{ kind: 'code', seconds: 1, args: { cell: 5 }, line: 1 }],
        '2': [{ kind: 'code', seconds: 1, args: { cell: 5 }, line: 2 }],
      },
    } as ShowData)
    expect(autoRoles(twin, [{ ip: 'a', cell: 5 }])).toEqual({})
  })
})
