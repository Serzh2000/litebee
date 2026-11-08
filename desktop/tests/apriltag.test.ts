import { describe, expect, it } from 'vitest'
import { TAG36H11 } from '@core/apriltag'

describe('the markers of the mat', () => {
  it('has a tag36h11 for each of the 144 cells, all different', () => {
    expect(TAG36H11).toHaveLength(144)
    expect(new Set(TAG36H11).size).toBe(144)
    for (const t of TAG36H11) expect(t).toMatch(/^[01]{36}$/)
  })

  it('draws id 0 as the printed tag of the repository (apriltag_36h11_id0_A4.png)', () => {
    // the data field of the printed tag, rows from the top (1 = light)
    const printed = ['001000', '011010', '000101', '000110', '101110', '101011']
    expect(TAG36H11[0]).toBe(printed.join(''))
  })
})
