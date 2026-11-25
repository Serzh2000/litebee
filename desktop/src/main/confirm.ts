/**
 * The window that asks for the last word before drones fly: what the app is about to do, drone by drone, and two buttons.
 * Pure text in, HTML out, so it can be looked at and tested without a window. The window itself is in confirmWindow.ts.
 */
import { getLang, tr } from '../core/i18n'

export interface LaunchDrone {
  ip: string
  /** the checksum the drone reported back, equal to the one of the mission */
  checksum: number
  maxHeightCm: number
  limitCm: number
  seconds: number
  /** the cell the drone stands on (null: no position yet) */
  cell: number | null
  /** the cell of its first move (null: it does not move over the mat) */
  firstCell: number | null
  /** steps of the mission that nobody has flown on a live drone */
  unproven: string[]
}

export interface LaunchInfo {
  flies: boolean
  drones: LaunchDrone[]
}

const escape = (s: string) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)

const LIGHT =
  '--bg:#ffffff;--text:#131416;--muted:#5d5f60;--border:#e8eaec;--control:#cdced1;--primary:#1d1f20;--primary-ink:#ffffff;--primary-hover:#34373a;--accent:#1b6c80;--warn-bg:#fffbeb;--warn-ink:#92400e;--warn-line:#fde68a;--raised:#f6f6f3'
const DARK =
  '--bg:#1b1b1e;--text:#f1f1ef;--muted:#b4b4bb;--border:#2c2c30;--control:#4a4a52;--primary:#f1f1ef;--primary-ink:#131416;--primary-hover:#d8d8d4;--accent:#8ecbd2;--warn-bg:#2b2410;--warn-ink:#f2c879;--warn-line:#5a4a1c;--raised:#202023'

const CSS = `
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--bg);color:var(--text);font:14px/1.45 Bahnschrift,'Segoe UI',system-ui,sans-serif;padding:24px 24px 20px;-webkit-font-smoothing:antialiased;user-select:none}
h1{margin:0;font-size:20px;line-height:1.25;font-weight:600}
.lead{margin:6px 0 0;color:var(--muted);font-size:13px}
.drone{margin-top:18px;padding-top:14px;border-top:1px solid var(--border)}
.drone h2{margin:0 0 8px;font-size:13px;font-weight:600;display:flex;gap:8px;align-items:baseline}
.drone h2 code{font:13px Consolas,monospace}
dl{margin:0;display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;font-size:13px}
dt{color:var(--muted)}
dd{margin:0}
.warn{margin:10px 0 0;padding:8px 10px;border:1px solid var(--warn-line);border-radius:7px;background:var(--warn-bg);color:var(--warn-ink);font-size:13px}
.warn b{font-weight:600}
.buttons{display:flex;justify-content:flex-end;gap:10px;margin-top:22px}
button{height:36px;padding:0 18px;border-radius:7px;font:600 14px Bahnschrift,'Segoe UI',system-ui,sans-serif;cursor:pointer}
.no{background:transparent;color:var(--text);border:1px solid var(--control)}
.no:hover{background:var(--raised)}
.go{background:var(--primary);color:var(--primary-ink);border:1px solid var(--primary)}
.go:hover{background:var(--primary-hover);border-color:var(--primary-hover)}
button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
`

function droneBlock(d: LaunchDrone): string {
  const stands = d.cell !== null ? tr('клетка {c}', { c: d.cell }) : tr('клетка неизвестна')
  const rows: [string, string][] = [[tr('Сейчас'), stands]]
  if (d.firstCell !== null) rows.push([tr('Первое движение'), tr('к клетке {c}', { c: d.firstCell })])
  rows.push([tr('Высота'), tr('до {h} см, лимит {l} см', { h: d.maxHeightCm, l: d.limitCm })])
  rows.push([tr('Длится'), tr('около {s} с', { s: Math.round(d.seconds) })])
  rows.push([tr('Миссия на борту'), tr('дрон принял её, контрольная сумма {n}', { n: d.checksum })])
  const warn = d.unproven.length
    ? `<p class="warn"><b>${escape(tr('Не проверено на живом дроне'))}:</b> ${escape(d.unproven.join(', '))}. ${escape(tr('Будьте готовы к аварийной посадке.'))}</p>`
    : ''
  return (
    `<section class="drone"><h2>${escape(tr('Дрон'))} <code>${escape(d.ip)}</code></h2>` +
    `<dl>${rows.map(([k, v]) => `<dt>${escape(k)}</dt><dd>${escape(v)}</dd>`).join('')}</dl>${warn}</section>`
  )
}

/** The page of the window. The buttons only navigate to `litebee-confirm:yes` / `litebee-confirm:no`, which the window catches. */
export function confirmHtml(info: LaunchInfo, dark: boolean): string {
  const title = info.flies ? tr('Дроны полетят') : tr('Миссия только со светодиодами')
  const lead = info.flies
    ? tr('Вокруг дронов никого нет, сетка закрыта. Аварийная посадка: Esc или красная кнопка в окне программы.')
    : tr('Моторы не запустятся: дроны только зажгут светодиоды.')
  const go = info.flies ? tr('Взлететь') : tr('Запустить')
  return (
    `<!doctype html><html lang="${getLang()}"><head><meta charset="utf-8">` +
    `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">` +
    `<title>${escape(tr('Старт'))}</title><style>:root{${dark ? DARK : LIGHT};color-scheme:${dark ? 'dark' : 'light'}}${CSS}</style></head><body>` +
    `<h1>${escape(title)}</h1><p class="lead">${escape(lead)}</p>` +
    info.drones.map(droneBlock).join('') +
    `<div class="buttons"><button type="button" class="no" id="no">${escape(tr('Отмена'))}</button>` +
    `<button type="button" class="go" id="go">${escape(go)}</button></div>` +
    `<script>` +
    `const send=(v)=>{location.href='litebee-confirm:'+v};` +
    `document.getElementById('no').addEventListener('click',()=>send('no'));` +
    `document.getElementById('go').addEventListener('click',()=>send('yes'));` +
    `document.addEventListener('keydown',(e)=>{if(e.key==='Escape')send('no')});` +
    `document.getElementById('no').focus();` +
    `</script></body></html>`
  )
}
