import { describe, expect, it } from 'vitest'
import { addDrone, freeStartCell, setStartCell } from '@core/placement'
import { startCell } from '@core/roles'
import { splitDrones } from '@core/sections'
import { buildShow, type ShowData } from '@core/show'
import squareSource from '../../shows/quarter_square.py?raw'
import dreamSource from '../../shows/my_dream.py?raw'
import square from '../shows/quarter_square.json'

const show = buildShow(square as unknown as ShowData)

describe('standing a drone on another cell', () => {
  it('changes the cell of the short first move that is the start', () => {
    const edit = setStartCell(squareSource, 1, 14)
    expect(edit.error).toBeUndefined()
    const section = splitDrones(edit.source)!.sections[0].text
    expect(section).toContain('d.code(14, 1)')
    expect(section).not.toContain('d.code(13, 1)')
    // the other drones are not touched
    expect(splitDrones(edit.source)!.sections.slice(1).map((s) => s.text)).toEqual(splitDrones(squareSource)!.sections.slice(1).map((s) => s.text))
  })

  it('puts a start move after the take-off when the first move is a real flight', () => {
    const edit = setStartCell(dreamSource, 1, 37)
    expect(edit.error).toBeUndefined()
    const lines = splitDrones(edit.source)!.sections[0].text.split(/\r?\n/) // the file of the app has Windows line ends
    const takeoff = lines.findIndex((l) => l.includes('takeoff'))
    expect(lines[takeoff + 1]).toContain("d.rgb('green')")
    expect(lines[takeoff + 2]).toBe('d.code(37, 1)')
    expect(lines[takeoff + 3]).toBe('d.code(25, 4)') // the old first flight is still there
  })

  it('refuses a drone that a loop makes, and says why', () => {
    const edit = setStartCell("for i in range(3):\n    d = show.drone(i + 1)\n    d.takeoff(100, 5)\n", 1, 5)
    expect(edit.error).toMatch(/руками/)
    expect(edit.source).toContain('range(3)')
  })
})

describe('adding a drone', () => {
  it('appends a block with the next number and a free cell, and the file still splits by drone', () => {
    const edit = addDrone(squareSource, show)
    expect(edit.error).toBeUndefined()
    const split = splitDrones(edit.source)!
    expect(split.sections.map((s) => s.number)).toEqual([1, 2, 3, 4, 5])
    expect(split.sections[4].text).toMatch(/d = show\.drone\(5\)\nd\.calibrate\(5\)\nd\.takeoff\(100, 5\)/)
    const cell = Number(/d\.code\((\d+), 1\)/.exec(split.sections[4].text)![1])
    expect(show.drones.map((d) => startCell(d.steps))).not.toContain(cell)
    expect(cell).toBe(freeStartCell(show))
  })

  it('keeps every start two cells from the others, drone after drone', () => {
    let source = squareSource
    const starts: number[] = [13, 16, 52, 49]
    for (let i = 0; i < 4; i++) {
      const current = buildShow({ name: 't', drones: Object.fromEntries(starts.map((c, k) => [String(k + 1), [{ kind: 'code', seconds: 1, args: { cell: c }, line: null }]])) } as unknown as ShowData)
      const edit = addDrone(source, current)
      source = edit.source
      starts.push(freeStartCell(current))
    }
    for (let a = 0; a < starts.length; a++) {
      for (let b = a + 1; b < starts.length; b++) {
        const d = Math.hypot((starts[a] % 12) - (starts[b] % 12), Math.floor(starts[a] / 12) - Math.floor(starts[b] / 12))
        expect(d).toBeGreaterThanOrEqual(2)
      }
    }
  })

  it('keeps the new drone inside the area that is shown', () => {
    const quarter = { col0: 0, row0: 0, cols: 6, rows: 6 }
    const cell = freeStartCell(show, quarter)
    expect(cell % 12).toBeLessThan(6)
    expect(Math.floor(cell / 12)).toBeLessThan(6)
    expect(freeStartCell(show, { col0: 6, row0: 6, cols: 6, rows: 6 }) % 12).toBeGreaterThanOrEqual(6)
  })

  it('stops at ten drones', () => {
    const many = buildShow({ name: 'm', drones: Object.fromEntries(Array.from({ length: 10 }, (_, i) => [String(i + 1), []])) } as unknown as ShowData)
    expect(addDrone('x\n', many).error).toMatch(/10 дронов/)
  })
})
