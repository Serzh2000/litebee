import { describe, expect, it } from 'vitest'
import { checkShow } from '../src/core/checks'
import { newProject, newSource, parseProject, projectFileName, serializeProject } from '../src/core/project'
import { buildShow } from '../src/core/show'

describe('project', () => {
  it('makes the asked number of drones and clamps it', () => {
    expect(Object.keys(newProject('A', 3).drones)).toEqual(['1', '2', '3'])
    expect(Object.keys(newProject('A', 99).drones)).toHaveLength(10)
    expect(Object.keys(newProject('A', 0).drones)).toHaveLength(1)
  })

  it('a new project builds, has no errors and ends on the ground', () => {
    const data = newProject('Тест', 2)
    const show = buildShow(data)
    expect(checkShow(show).filter((f) => f.level === 'error')).toEqual([])
    expect(show.duration).toBeGreaterThan(0)
  })

  it('writes the Python source of a new project', () => {
    const source = newSource("It's mine", 2)
    expect(source).toContain("from litebee_show import Show")
    expect(source).toContain("show = Show('It\\'s mine')")
    expect(source.match(/show\.drone\(\d+\)/g)).toEqual(['show.drone(1)', 'show.drone(2)'])
    expect(source.endsWith('d.land()\n')).toBe(true)
  })

  it('survives a save and a load', () => {
    const data = newProject('Тест', 4)
    expect(parseProject(serializeProject(data))).toEqual(data)
  })

  it('refuses files that are not projects, with a reason', () => {
    expect(() => parseProject('not json')).toThrow('не JSON')
    expect(() => parseProject('{"name": 1}')).toThrow('нет имени')
    expect(() => parseProject('{"name":"x","drones":{"1":[{"kind":3}]}}')).toThrow('дрон 1')
  })

  it('makes a Windows-safe file name', () => {
    expect(projectFileName('a/b:c?')).toBe('abc.json')
    expect(projectFileName('  ')).toBe('project.json')
  })
})
