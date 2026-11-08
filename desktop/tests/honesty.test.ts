import { describe, expect, it } from 'vitest'
import { honestyNotes } from '../src/renderer/src/state/preflight'

describe('honestyNotes', () => {
  it('is silent for one proven drone', () => {
    expect(honestyNotes(1, 0)).toEqual([])
  })
  it('warns about several drones', () => {
    expect(honestyNotes(4, 0)).toEqual(['Несколько дронов вместе пока не проверены в полёте'])
  })
  it('warns about unproven steps, after the multi-drone line', () => {
    expect(honestyNotes(2, 1)).toEqual(['Несколько дронов вместе пока не проверены в полёте', 'В шоу есть шаги, не проверенные на дроне'])
    expect(honestyNotes(1, 1)).toEqual(['В шоу есть шаги, не проверенные на дроне'])
  })
})
