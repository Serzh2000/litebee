import { describe, expect, it } from 'vitest'
import { LED_COLORS, colorText, hexToRgb, parseColorArg, rgbArgAt, rgbToHex, snippetFor } from '@core/hints'
import missionPy from '../../litebee/mission.py?raw'

describe('the colour of d.rgb(...)', () => {
  const at = (line: string, mark = '|') => rgbArgAt(line.replace(mark, ''), line.indexOf(mark))

  it('finds the argument the cursor is inside', () => {
    expect(at("d.rgb('gr|een')")).toEqual({ from: 6, to: 13 })
    expect(at('d.rgb(|)')).toEqual({ from: 6, to: 6 })
    expect(at('d.rgb((255, 1|28, 0))')).toEqual({ from: 6, to: 19 })
  })

  it('runs to the end of the line while the call is not closed', () => {
    expect(at("d.rgb('re|")).toEqual({ from: 6, to: 9 })
  })

  it('is null outside the call or in another call', () => {
    expect(at("|d.rgb('red')")).toBeNull()
    expect(at("d.rgb('red')|")).toBeNull()
    expect(at('d.code(1|3, 2)')).toBeNull()
    expect(at("d.rgb('red'); d.code(1|3, 2)")).toBeNull()
  })

  it('knows a closing bracket inside a string is not the end', () => {
    expect(at("d.rgb('a)b|')")).toEqual({ from: 6, to: 11 })
  })
})

describe('colours as text', () => {
  it('writes a name for the eight colours and a triple for the rest', () => {
    expect(colorText([255, 0, 0])).toBe("'red'")
    expect(colorText([255, 128, 0])).toBe('(255, 128, 0)')
  })

  it('reads a name, a number and a triple back', () => {
    expect(parseColorArg("'blue'")).toEqual([0, 0, 255])
    expect(parseColorArg('1')).toEqual([255, 0, 0])
    expect(parseColorArg('( 10,20 ,30)')).toEqual([10, 20, 30])
    expect(parseColorArg('(1, 2, 300)')).toBeNull()
    expect(parseColorArg('c')).toBeNull()
  })

  it('goes to hex and back', () => {
    expect(rgbToHex([255, 128, 0])).toBe('#ff8000')
    expect(hexToRgb('#ff8000')).toEqual([255, 128, 0])
  })

  it('has the same eight colours, in the same order, as the Python of the app', () => {
    const block = /COLORS\s*=\s*\{([^}]*)\}/.exec(missionPy)![1]
    const python = [...block.matchAll(/["'](\w+)["']\s*:\s*\((\d+),\s*(\d+),\s*(\d+)\)/g)].map((m) => ({ name: m[1], rgb: [Number(m[2]), Number(m[3]), Number(m[4])] }))
    expect(LED_COLORS).toEqual(python)
  })
})

describe('snippets of commands', () => {
  it('puts a place on every required argument and skips the ones with a default', () => {
    expect(snippetFor('code(cell, seconds)')).toBe('code(${cell}, ${seconds})')
    expect(snippetFor('land()')).toBe('land()')
    expect(snippetFor("circle(count, cell1, cell2, seconds, rotate='cw')")).toBe('circle(${count}, ${cell1}, ${cell2}, ${seconds})')
  })
})
