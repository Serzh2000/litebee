import { describe, expect, it } from 'vitest'
import { checkShow } from '../src/core/checks'
import { cellInArea, detectArea, FULL, migrateCells, QUARTERS, validArea } from '../src/core/area'
import { buildShow, type ShowData } from '../src/core/show'
import dream from '../shows/my_dream.json'

const q = (n: number) => QUARTERS[n - 1].area

const SOURCE = `from litebee_show import Show
show = Show('Q')
d = show.drone(1)
d.takeoff(100, 5)
d.code(13, 4)          # cell 13
d.code_s('14 15', 4)
d.circle(2, 14, 15, 6, 'cw')
d.code(cell_var, 2)
d.rgb('green')
d.land()
`

describe('area', () => {
  it('knows its cells', () => {
    expect(cellInArea(q(1), 0)).toBe(true)
    expect(cellInArea(q(1), 6)).toBe(false)
    expect(cellInArea(q(2), 6)).toBe(true)
    expect(cellInArea(q(3), 72)).toBe(true)
    expect(cellInArea(FULL, 143)).toBe(true)
    expect(validArea({ col0: 8, row0: 0, cols: 6, rows: 6 })).toBe(false)
  })

  it('detects the quarter a show lives in, and the whole mat otherwise', () => {
    const small = { name: 's', drones: { '1': [{ kind: 'code', seconds: 2, args: { cell: 13 }, line: 1 }] } } as ShowData
    expect(detectArea(small)).toEqual(q(1))
    expect(detectArea(dream as unknown as ShowData)).toEqual(FULL)
  })

  it('moves plain cell numbers to another quarter and leaves the rest alone', () => {
    const moved = migrateCells(SOURCE, 6, 6)
    expect(moved.source).toContain('d.code(91, 4)          # cell 13')
    expect(moved.source).toContain("d.code_s('92 93', 4)")
    expect(moved.source).toContain("d.circle(2, 92, 93, 6, 'cw')")
    expect(moved.source).toContain('d.code(cell_var, 2)')
    expect(moved.changed).toBe(5)
    expect(moved.skipped).toBe(1)
  })

  it('goes there and back unchanged', () => {
    const there = migrateCells(SOURCE, 6, 0)
    expect(migrateCells(there.source, -6, 0).source).toBe(SOURCE)
  })

  it('refuses a move that would leave the mat', () => {
    expect(() => migrateCells(SOURCE, 12, 0)).toThrow('вышла бы за коврик')
  })

  it('flags a flight that leaves the working area', () => {
    const show = buildShow(dream as unknown as ShowData)
    const findings = checkShow(show, { area: q(1) })
    expect(findings.filter((f) => f.message.includes('выходит за рабочую область'))).toHaveLength(10)
    expect(checkShow(show, { area: FULL }).some((f) => f.message.includes('выходит за рабочую область'))).toBe(false)
  })
})
