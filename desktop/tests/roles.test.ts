import { describe, expect, it } from 'vitest'
import { assignRole, autoRoles, missionsReady, resolveRoles, rolesFrozen, startCell } from '@core/roles'
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

describe('rolesFrozen', () => {
  it('reads numbers from cells only on the ground with nothing on board', () => {
    expect(rolesFrozen(null)).toBe(false)
    expect(rolesFrozen({ loaded: [], armed: false, flying: false })).toBe(false)
    expect(rolesFrozen({ loaded: ['192.168.13.104'], armed: false, flying: false })).toBe(true)
    expect(rolesFrozen({ loaded: [], armed: true, flying: false })).toBe(true)
    expect(rolesFrozen({ loaded: [], armed: false, flying: true })).toBe(true)
  })
})

describe('resolveRoles', () => {
  it('gives the number from the cell when the person picked nothing', () => {
    expect(resolveRoles({}, { a: 1, b: 2 }, ['a', 'b'])).toEqual({ a: 1, b: 2 })
  })
  it('lets the person win over the cell', () => {
    expect(resolveRoles({ b: 1 }, { a: 1, b: 2 }, ['a', 'b'])).toEqual({ a: null, b: 1 })
  })
  it('does not give from a cell the number a silent drone holds by choice', () => {
    expect(resolveRoles({ gone: 3 }, { a: 3 }, ['a'])).toEqual({ a: null })
  })
  it('never gives one number to two drones, even from old choices', () => {
    expect(resolveRoles({ a: 2, b: 2 }, {}, ['a', 'b'])).toEqual({ a: 2, b: null })
  })
})

describe('assignRole', () => {
  it('takes the number from whoever had it', () => {
    expect(assignRole({}, { a: 1, b: 2 }, 1, 'b')).toEqual({ a: null, b: 1 })
  })
  it('takes the number also from a drone that is silent for now', () => {
    // a has number 1 by choice and drops off the link for a moment; the person gives 1 to b
    const manual = assignRole({ a: 1 }, { b: 2 }, 1, 'b')
    // a comes back: only b flies program 1
    expect(resolveRoles(manual, {}, ['a', 'b'])).toEqual({ a: null, b: 1 })
  })
  it('takes the number away when no drone is given', () => {
    expect(assignRole({ a: 1 }, { a: 1 }, 1, null)).toEqual({ a: null })
  })
})

describe('missionsReady', () => {
  const ok = (role: number) => ({ ok: true, message: '', role })
  it('needs every drone with a number to hold the program of that number', () => {
    expect(missionsReady(['a', 'b'], { a: 1, b: 2 }, { a: ok(1), b: ok(2) }, new Set(['a', 'b']))).toBe(true)
    expect(missionsReady(['a', 'b'], { a: 1, b: 2 }, { a: ok(1) }, new Set(['a']))).toBe(false)
  })
  it('wants a new upload after the number of a drone changed', () => {
    // two drones swapped numbers after the upload: each holds the other's program
    expect(missionsReady(['a', 'b'], { a: 2, b: 1 }, { a: ok(1), b: ok(2) }, new Set(['a', 'b']))).toBe(false)
  })
  it('wants a new upload when the program is no longer on board', () => {
    expect(missionsReady(['a'], { a: 1 }, { a: ok(1) }, new Set())).toBe(false)
  })
  it('leaves drones without a number out, but needs at least one', () => {
    expect(missionsReady(['a', 'b'], { a: 1, b: null }, { a: ok(1) }, new Set(['a']))).toBe(true)
    expect(missionsReady(['a'], { a: null }, {}, new Set())).toBe(false)
  })
})

describe('numbers in flight', () => {
  it('the square moves every drone onto the cell of the next one', () => {
    const show = buildShow(square as ShowData)
    const start = show.drones.map((d) => ({ ip: `ip${d.number}`, cell: startCell(d.steps) }))
    const before = autoRoles(show, start)
    // every drone one corner further: read from cells, every number would move to another drone at once
    const cells = start.map((d) => d.cell)
    const moved = start.map((d, i) => ({ ip: d.ip, cell: cells[(i + 1) % cells.length] }))
    const after = autoRoles(show, moved)
    expect(Object.keys(after).some((ip) => after[ip] !== before[ip])).toBe(true)
    // which is why the numbers are not read again once a mission is on board
    expect(rolesFrozen({ loaded: start.map((d) => d.ip), armed: false, flying: false })).toBe(true)
  })
})
