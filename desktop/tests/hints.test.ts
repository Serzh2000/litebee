import { describe, expect, it } from 'vitest'
import { LED_COLORS, NOTE_SECONDS, PIANO, buzzArgsAt, colorText, hexToRgb, noteName, parseColorArg, rgbArgAt, rgbToHex, snippetFor } from '@core/hints'
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

describe('the note of d.buzz(...)', () => {
  const at = (line: string) => buzzArgsAt(line.replace('|', ''), line.indexOf('|'))
  const text = (line: string) => {
    const clean = line.replace('|', '')
    return at(line)?.args.map((a) => clean.slice(a.from, a.to))
  }

  it('finds both arguments, with or without spaces', () => {
    expect(text("d.buzz('C|3', 0.5)")).toEqual(["'C3'", '0.5'])
    expect(text("d.buzz( 'C3' ,0.5 |)")).toEqual(["'C3'", '0.5'])
  })

  it('finds what is written so far', () => {
    expect(text('d.buzz(|)')).toEqual([])
    expect(text("d.buzz('E3'|")).toEqual(["'E3'"])
    expect(text("d.buzz('E3', |")).toEqual(["'E3'"])
  })

  it('is null outside the call and in other calls', () => {
    expect(at("d.buzz('C3', 0.5)|")).toBeNull()
    expect(at("d.rgb('re|d')")).toBeNull()
    expect(at("|d.buzz('C3', 0.5)")).toBeNull()
  })

  it('does not split at a comma inside a string or brackets', () => {
    expect(text("d.buzz('C,3', max(1, |2))")).toEqual(["'C,3'", 'max(1, 2)'])
  })
})

describe('the notes of the buzzer', () => {
  it('names the notes as the table of the buzzer does', () => {
    expect([0, 1, 2, 25, 26, 29, 37, 44].map(noteName)).toEqual(['B0', 'C1', 'CS1', 'C3', 'CS3', 'E3', 'C4', 'G4'])
  })

  it('offers the notes that were checked by ear: C3 to G4, twenty keys, seven black ones', () => {
    expect(PIANO.map((k) => k.name).slice(0, 3)).toEqual(['C3', 'CS3', 'D3'])
    expect(PIANO).toHaveLength(20)
    expect(PIANO[PIANO.length - 1].name).toBe('G4')
    expect(PIANO.filter((k) => k.black)).toHaveLength(8)
  })

  it('offers lengths of a note in seconds', () => {
    expect(NOTE_SECONDS).toEqual([0.25, 0.5, 1, 2])
  })
})
