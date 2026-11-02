import { describe, expect, it } from 'vitest'
import { joinDrones, sectionAt, splitDrones } from '@core/sections'
import squareSource from '../../shows/quarter_square.py?raw'
import dreamSource from '../../shows/my_dream.py?raw'

describe('splitDrones', () => {
  it('splits a show into a head and one section per drone, and joins back to the same file', () => {
    const split = splitDrones(squareSource)!
    expect(split.sections.map((s) => s.number)).toEqual([1, 2, 3, 4])
    expect(split.head).toContain("show = Show('Квадрат в четверти')")
    expect(split.head).not.toContain('show.drone')
    expect(split.sections[0].text.startsWith('d = show.drone(1)')).toBe(true)
    expect(split.head + split.sections.map((s) => s.text).join('')).toBe(squareSource)
    expect(joinDrones(split, 2, split.sections[1].text)).toBe(squareSource)
  })

  it('knows the line each section starts on', () => {
    const split = splitDrones(squareSource)!
    const src = squareSource.split('\n')
    for (const s of split.sections) expect(src[s.line - 1]).toContain(`show.drone(${s.number})`)
    expect(sectionAt(split, split.sections[1].line + 2)?.number).toBe(2)
    expect(sectionAt(split, 1)).toBeNull()
  })

  it('takes the comment lines right above a drone into its section', () => {
    const src = "from litebee_show import Show\nshow = Show('t')\n\n# Дрон один\n# летит прямо\nd = show.drone(1)\nd.land()\n\n# Дрон два\nd = show.drone(2)\nd.land()\n"
    const split = splitDrones(src)!
    expect(split.sections[0].text.startsWith('# Дрон один')).toBe(true)
    expect(split.sections[1].text.startsWith('# Дрон два')).toBe(true)
    expect(split.head.endsWith('\n\n')).toBe(true)
    expect(split.head + split.sections.map((s) => s.text).join('')).toBe(src)
  })

  it('edits one drone and leaves the rest alone', () => {
    const split = splitDrones(squareSource)!
    const edited = joinDrones(split, 3, split.sections[2].text.replace('d.land()', 'd.land_on(52)'))
    expect(edited).toContain('d.land_on(52)')
    expect(edited.length).toBe(squareSource.length + 'land_on(52)'.length - 'land()'.length)
    expect(splitDrones(edited)!.sections.map((s) => s.number)).toEqual([1, 2, 3, 4])
  })

  it('does not split what a loop makes, or a number used twice, or a show without drones', () => {
    expect(splitDrones("for i in range(3):\n    d = show.drone(i + 1)\n    d.land()\n")).toBeNull()
    expect(splitDrones('d = show.drone(1)\nd.land()\nd = show.drone(1)\nd.land()\n')).toBeNull()
    expect(splitDrones("show = Show('x')\n")).toBeNull()
  })

  it('splits the big official shows too', () => {
    expect(splitDrones(dreamSource)!.sections).toHaveLength(10)
  })
})
