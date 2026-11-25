import { describe, expect, it } from 'vitest'
import { honestyNotes } from '../src/renderer/src/state/preflight'

describe('honestyNotes', () => {
  it('is silent when every step has flown', () => {
    expect(honestyNotes(0)).toEqual([])
  })
  it('does not warn about several drones: they have flown together from one start', () => {
    expect(honestyNotes(0)).not.toContain('Несколько дронов вместе пока не проверены в полёте')
  })
  it('warns about steps that are not proven', () => {
    expect(honestyNotes(1)).toEqual(['В шоу есть шаги, не проверенные на дроне'])
    expect(honestyNotes(3)).toEqual(['В шоу есть шаги, не проверенные на дроне'])
  })
})
