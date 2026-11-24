/**
 * Help while typing the code of a show: where the cursor stands inside the colour of `d.rgb(...)`, the eight colours
 * of the LEDs, and the snippet a command is inserted as. Plain functions on text, so the editor only draws them.
 */

export type Rgb = [number, number, number]

/** The eight colours the drones were proven with, in the order of `d.rgb(0..7)` (litebee/mission.py: COLORS). */
export const LED_COLORS: { name: string; rgb: Rgb }[] = [
  { name: 'black', rgb: [0, 0, 0] },
  { name: 'red', rgb: [255, 0, 0] },
  { name: 'green', rgb: [0, 255, 0] },
  { name: 'yellow', rgb: [255, 255, 0] },
  { name: 'blue', rgb: [0, 0, 255] },
  { name: 'purple', rgb: [255, 0, 255] },
  { name: 'cyan', rgb: [0, 255, 255] },
  { name: 'white', rgb: [255, 255, 255] },
]

const RGB_CALL = /\.rgb\(/g

/**
 * The argument of the `.rgb(` call that the cursor (a column of the line) is inside: where it starts and ends in the line.
 * An argument that is not closed yet runs to the end of the line. Null when the cursor is not inside such a call.
 */
export function rgbArgAt(line: string, col: number): { from: number; to: number } | null {
  let found: { from: number; to: number } | null = null
  for (const m of line.matchAll(RGB_CALL)) {
    const from = (m.index ?? 0) + m[0].length
    if (from > col) break
    let depth = 0
    let quote = ''
    let to = line.length
    for (let i = from; i < line.length; i++) {
      const c = line[i]
      if (quote) {
        if (c === quote) quote = ''
      } else if (c === "'" || c === '"') quote = c
      else if (c === '#') {
        to = i
        break
      } else if (c === '(') depth++
      else if (c === ')') {
        if (depth === 0) {
          to = i
          break
        }
        depth--
      }
    }
    if (col <= to) found = { from, to }
  }
  return found
}

/** How a colour is written in the code: its name when it is one of the eight, otherwise the triple. */
export function colorText(rgb: Rgb): string {
  const named = LED_COLORS.find((c) => c.rgb.every((v, i) => v === rgb[i]))
  return named ? `'${named.name}'` : `(${rgb.join(', ')})`
}

/** `#ff8000` -> [255, 128, 0] */
export function hexToRgb(hex: string): Rgb {
  const n = Number.parseInt(hex.replace('#', ''), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

export const rgbToHex = ([r, g, b]: Rgb): string => `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`

/** The colour written in an argument: a name, a number 0..7 or a triple; null for anything else (a variable, a sum). */
export function parseColorArg(arg: string): Rgb | null {
  const text = arg.trim()
  const name = /^(['"])(\w+)\1$/.exec(text)
  if (name) return LED_COLORS.find((c) => c.name === name[2])?.rgb ?? null
  if (/^[0-7]$/.test(text)) return LED_COLORS[Number(text)].rgb
  const triple = /^\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/.exec(text)
  if (triple && triple.slice(1).every((v) => Number(v) <= 255)) return [Number(triple[1]), Number(triple[2]), Number(triple[3])]
  return null
}

/**
 * The text a command is inserted as, with a place for every required argument: `code(cell, seconds)` ->
 * `code(${cell}, ${seconds})` (the snippet syntax of the editor). Arguments with a default value are left out.
 */
export function snippetFor(signature: string): string {
  const open = signature.indexOf('(')
  const close = signature.lastIndexOf(')')
  if (open < 0 || close < open) return signature
  const params = signature
    .slice(open + 1, close)
    .split(',')
    .map((p) => p.trim())
    .filter((p) => p && !p.includes('='))
  return `${signature.slice(0, open)}(${params.map((p) => `\${${p}}`).join(', ')})`
}
