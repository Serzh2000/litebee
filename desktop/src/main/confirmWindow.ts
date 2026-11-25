import { BrowserWindow, nativeTheme } from 'electron'
import { tr } from '../core/i18n'
import { confirmHtml, type LaunchInfo } from './confirm'

const WIDTH = 520
const MAX_HEIGHT = 680

/**
 * The last word before drones fly. It is a window of its own that only the main process opens, and its two buttons can
 * only be pressed by a person at this computer: nothing in the page of the app can answer it. Closing it, Esc and
 * Cancel all mean "no"; Enter does not start anything, because the focus rests on Cancel.
 */
export function askToLaunch(parent: BrowserWindow | undefined, info: LaunchInfo): Promise<boolean> {
  const dark = nativeTheme.shouldUseDarkColors
  return new Promise((resolve) => {
    const win = new BrowserWindow({
      parent,
      modal: Boolean(parent),
      width: WIDTH,
      height: 420,
      useContentSize: true,
      resizable: false,
      minimizable: false,
      maximizable: false,
      fullscreenable: false,
      show: false,
      autoHideMenuBar: true,
      title: tr('Старт'),
      backgroundColor: dark ? '#1b1b1e' : '#ffffff',
      webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false },
    })
    win.removeMenu()
    let done = false
    const finish = (ok: boolean) => {
      if (done) return
      done = true
      resolve(ok)
      if (!win.isDestroyed()) win.close()
    }
    win.webContents.on('will-navigate', (e, url) => {
      e.preventDefault()
      if (url === 'litebee-confirm:yes') finish(true)
      else if (url === 'litebee-confirm:no') finish(false)
    })
    win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    win.on('closed', () => finish(false))
    void win
      .loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(confirmHtml(info, dark))}`)
      .then(async () => {
        const height = Number(await win.webContents.executeJavaScript('document.documentElement.scrollHeight'))
        win.setContentSize(WIDTH, Math.min(Math.max(height, 220), MAX_HEIGHT))
        win.show()
      })
      .catch(() => finish(false))
  })
}
