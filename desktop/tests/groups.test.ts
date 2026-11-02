import { describe, expect, it } from 'vitest'
import { checkShow } from '../src/core/checks'
import { droneList, groupFindings } from '../src/core/groups'
import { buildShow, type ShowData } from '../src/core/show'
import dream from '../shows/my_dream.json'

describe('groups', () => {
  it('writes runs of drones short', () => {
    expect(droneList([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])).toBe('1–10')
    expect(droneList([1, 2, 4, 5, 6, 9])).toBe('1, 2, 4–6, 9')
  })

  it('My Dream: ten identical findings per kind become one row', () => {
    const findings = checkShow(buildShow(dream as unknown as ShowData))
    const groups = groupFindings(findings, 150)
    expect(findings.length).toBeGreaterThan(40)
    expect(groups.length).toBeLessThan(12)
    const height = groups.find((g) => g.title.startsWith('Выше лимита'))!
    expect(height.level).toBe('error')
    expect(height.items).toHaveLength(10)
    expect(height.detail).toContain('дроны 1–10')
    expect(height.detail).toContain('до 160 см')
    expect(groups[0].level).toBe('error')
    expect(groups.reduce((n, g) => n + g.items.length, 0)).toBe(findings.length)
  })
})
