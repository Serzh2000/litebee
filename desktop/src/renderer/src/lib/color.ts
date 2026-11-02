import { getLang } from '@core/i18n'
import { currentTheme } from '../state/useTheme'
import type { Rgb } from '@core/show'

/** WCAG relative luminance of an sRGB colour (channels 0-255). */
export function luminance([r, g, b]: Rgb): number {
  const lin = (v: number) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

export function contrast(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((p, q) => q - p)
  return (hi + 0.05) / (lo + 0.05)
}

export const PAPER: Rgb = [246, 247, 249]
export const SHEET: Rgb = [251, 252, 253]
const DARK_PAPER: Rgb = [17, 21, 26]
const DARK_SHEET: Rgb = [27, 32, 39]

/** The ground the colours are read on now: the paper of the field (or the sheet of a panel) of the current theme. */
export const paper = (): Rgb => (currentTheme() === 'dark' ? DARK_PAPER : PAPER)
export const sheet = (): Rgb => (currentTheme() === 'dark' ? DARK_SHEET : SHEET)

/** The LED colour moved until it reads on the ground: darkened on light paper, lightened on dark paper (a white LED stays visible as a path or a ring). */
export function readable(rgb: Rgb, on: Rgb = paper(), ratio = 3): Rgb {
  let out = rgb
  const lighten = luminance(on) < 0.2
  for (let i = 0; i < 14 && contrast(out, on) < ratio; i++) {
    out = lighten
      ? [Math.round(out[0] + (255 - out[0]) * 0.18), Math.round(out[1] + (255 - out[1]) * 0.18), Math.round(out[2] + (255 - out[2]) * 0.18)]
      : [Math.round(out[0] * 0.87), Math.round(out[1] * 0.87), Math.round(out[2] * 0.87)]
  }
  return out
}

export const css = ([r, g, b]: Rgb, alpha = 1) => (alpha === 1 ? `rgb(${r} ${g} ${b})` : `rgb(${r} ${g} ${b} / ${alpha})`)

export const isLit = (rgb: Rgb) => rgb[0] + rgb[1] + rgb[2] > 0

/** "30,0" the way Russian text writes seconds. */
/** A number with the decimal mark of the language: a comma in Russian, a point in English. */
export const decimal = (v: number, digits = 1) => (getLang() === 'ru' ? v.toFixed(digits).replace('.', ',') : v.toFixed(digits))

export const seconds = (t: number, digits = 1) => decimal(t, digits)
