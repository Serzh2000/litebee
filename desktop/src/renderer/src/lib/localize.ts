import { getLang, tr } from '@core/i18n'

const CYR = /[А-Яа-яЁё]/

/**
 * A show opened as an example is written in Russian: its comment lines and its name. In English they are swapped for
 * the English text (the code is the same), so that the file reads in the language of the interface. Lines without an
 * English text stay as they are.
 */
export function localizeSource(source: string): string {
  if (getLang() === 'ru') return source
  return source
    .split('\n')
    .map((line) => {
      const comment = /^(\s*#\s?)(.*?)(\r?)$/.exec(line)
      if (comment && CYR.test(comment[2])) return comment[1] + tr(comment[2]) + comment[3]
      return line.replace(/\bShow\('((?:[^'\\]|\\.)*)'\)/, (whole, name: string) => (CYR.test(name) ? `Show('${tr(name).replace(/'/g, "\\'")}')` : whole))
    })
    .join('\n')
}
