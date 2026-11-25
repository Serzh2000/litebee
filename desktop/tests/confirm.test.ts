import { afterEach, describe, expect, it } from 'vitest'
import { setLang } from '@core/i18n'
import { confirmHtml, type LaunchDrone, type LaunchInfo } from '../src/main/confirm'

afterEach(() => setLang('ru'))

const drone = (over: Partial<LaunchDrone> = {}): LaunchDrone => ({
  ip: '192.168.13.107', checksum: 13, maxHeightCm: 130, limitCm: 150, seconds: 18, cell: 0, firstCell: 27, unproven: [], ...over,
})
const info = (over: Partial<LaunchInfo> = {}): LaunchInfo => ({ flies: true, drones: [drone()], ...over })

describe('the window that asks before the drones fly', () => {
  it('says what will happen, drone by drone', () => {
    const html = confirmHtml(info(), false)
    for (const text of ['Дроны полетят', '192.168.13.107', 'клетка 0', 'к клетке 27', 'до 130 см, лимит 150 см', 'около 18 с', 'контрольная сумма 13', 'Взлететь', 'Отмена']) {
      expect(html).toContain(text)
    }
    expect(html).not.toContain('Не проверено')
  })

  it('warns in words about steps nobody has flown', () => {
    expect(confirmHtml(info({ drones: [drone({ unproven: ['circle_z'] })] }), false)).toContain('Не проверено на живом дроне:</b> circle_z')
  })

  it('has one block per drone, says the cell is unknown and names an LED-only mission as such', () => {
    const html = confirmHtml(info({ flies: false, drones: [drone(), drone({ ip: '192.168.13.108', cell: null, firstCell: null })] }), true)
    expect(html.match(/class="drone"/g)).toHaveLength(2)
    expect(html).toContain('клетка неизвестна')
    expect(html).toContain('Миссия только со светодиодами')
    expect(html).toContain('Запустить')
    expect(html).not.toContain('Взлететь')
  })

  it('cannot be written into: what comes from outside is escaped', () => {
    const html = confirmHtml(info({ drones: [drone({ ip: '<img src=x onerror=alert(1)>', unproven: ['<b>'] })] }), false)
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img')
    expect(html).not.toContain('<b>,')
  })

  it('is in English, light and dark', () => {
    setLang('en')
    const html = confirmHtml(info(), true)
    expect(html).toContain('The drones will fly')
    expect(html).toContain('Take off')
    expect(html).toContain('color-scheme:dark')
    expect(html).toContain('lang="en"')
  })

  it('only the two buttons and Esc answer, by the two addresses the window listens to; Cancel has the focus', () => {
    const html = confirmHtml(info(), false)
    expect(html).toContain("'litebee-confirm:'+v")
    expect(html).toContain("getElementById('no').focus()")
    expect(html).toContain("e.key==='Escape')send('no')")
  })
})
