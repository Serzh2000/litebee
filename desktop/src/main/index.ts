import { writeFileSync } from 'node:fs'
import { readFile, writeFile } from 'node:fs/promises'
import { join, normalize } from 'node:path'
import { pathToFileURL } from 'node:url'
import { app, BrowserWindow, dialog, ipcMain, nativeTheme, net, protocol, shell } from 'electron'
import type { Step } from '../core/show'
import { setLang, tr } from '../core/i18n'
import { adapters, Link } from './link'

// The window background is the desk colour, so a slow first paint does not flash white or black.
const DESK = '#EEF3F6'
const DESK_DARK = '#0F1519'

// Screenshot mode, for checking the interface at exact sizes without a screen grab:
//   LITEBEE_SHOT=out.png LITEBEE_SIZE=1440x900 LITEBEE_QUERY="select=4&t=30" electron .
const SHOT = process.env.LITEBEE_SHOT
const [SHOT_W, SHOT_H] = (process.env.LITEBEE_SIZE ?? '1440x900').split('x').map(Number)
const QUERY = process.env.LITEBEE_QUERY ?? ''

function createWindow(): void {
  const win = new BrowserWindow({
    width: SHOT ? SHOT_W : 1440,
    height: SHOT ? SHOT_H : 900,
    useContentSize: true,
    minWidth: SHOT ? SHOT_W : 1100,
    minHeight: SHOT ? SHOT_H : 700,
    show: false,
    backgroundColor: nativeTheme.shouldUseDarkColors ? DESK_DARK : DESK,
    title: 'Litebee IDE',
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  win.on('ready-to-show', () => win.show())

  // Links in the page open in the system browser, never inside the app window.
  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  if (SHOT) {
    win.webContents.once('did-finish-load', () => {
      setTimeout(async () => {
        const image = await win.webContents.capturePage()
        writeFileSync(SHOT, image.toPNG())
        app.quit()
      }, Number(process.env.LITEBEE_WAIT ?? 1500))
    })
  }

  if (process.env.ELECTRON_RENDERER_URL) {
    void win.loadURL(`${process.env.ELECTRON_RENDERER_URL}${QUERY ? `?${QUERY}` : ''}`)
  } else {
    void win.loadURL(`app://litebee/index.html${QUERY ? `?${QUERY}` : ''}`)
  }
}

const filters = () => [{ name: tr('Шоу на Python'), extensions: ['py'] }]

// the language of the page, so that the dialogs of the system speak it too
ipcMain.handle('app:lang', (_e, lang: string) => setLang(lang === 'en' ? 'en' : 'ru'))

// Files are read and written here, in the main process; the page only gets the text and the path back.
ipcMain.handle('project:open', async () => {
  const parent = BrowserWindow.getFocusedWindow() ?? undefined
  const options: Electron.OpenDialogOptions = { title: tr('Открыть проект'), filters: filters(), properties: ['openFile'] }
  const picked = parent ? await dialog.showOpenDialog(parent, options) : await dialog.showOpenDialog(options)
  if (picked.canceled || !picked.filePaths[0]) return null
  const path = picked.filePaths[0]
  return { path, text: await readFile(path, 'utf8') }
})

ipcMain.handle('project:read', async (_e, path: string) => {
  if (typeof path !== 'string' || !path.toLowerCase().endsWith('.py')) return null
  try {
    return { path, text: await readFile(path, 'utf8') }
  } catch {
    return null
  }
})

ipcMain.handle('project:save', async (_e, args: { text: string; path: string | null; suggested: string }) => {
  let path = args.path
  if (!path) {
    const parent = BrowserWindow.getFocusedWindow() ?? undefined
    const options: Electron.SaveDialogOptions = { title: tr('Сохранить проект'), defaultPath: args.suggested, filters: filters() }
    const picked = parent ? await dialog.showSaveDialog(parent, options) : await dialog.showSaveDialog(options)
    if (picked.canceled || !picked.filePath) return null
    path = picked.filePath
  }
  await writeFile(path, args.text, 'utf8')
  return { path }
})

// The link to the drones lives here; the page polls its state and asks it to start, stop or land.
const link = new Link()
ipcMain.handle('link:adapters', () => adapters())
ipcMain.handle('link:state', () => link.state())
ipcMain.handle('link:start', async (_e, pcIp: string) => {
  if (!adapters().some((a) => a.ip === pcIp)) return link.state()
  await link.start(pcIp)
  return link.state()
})
ipcMain.handle('link:stop', () => {
  link.stop()
  return link.state()
})
ipcMain.handle('link:upload', (_e, args: { ip: string; steps: Step[]; maxHeightCm: number }) =>
  link.upload(args.ip, args.steps, args.maxHeightCm),
)
ipcMain.handle('link:arm', (_e, on: boolean) => link.arm(on))
ipcMain.handle('link:go', async (_e, args: { ips: string[]; maxHeightCm: number }) => {
  const parent = BrowserWindow.getFocusedWindow() ?? undefined
  // The last word is a native dialog, outside the page: nothing in the page can answer it.
  const confirm = async (lines: string[], flies: boolean) => {
    const options: Electron.MessageBoxOptions = {
      type: 'warning',
      title: tr('Старт'),
      message: flies ? tr('Дроны полетят') : tr('Миссия только со светодиодами'),
      detail: lines.join('\n'),
      buttons: [flies ? tr('Взлететь') : tr('Запустить'), tr('Отмена')],
      defaultId: 1,
      cancelId: 1,
    }
    const r = parent ? await dialog.showMessageBox(parent, options) : await dialog.showMessageBox(options)
    return r.response === 0
  }
  return link.launch(args.ips, args.maxHeightCm, confirm)
})
ipcMain.handle('link:forget', () => {
  link.forgetLost()
  return link.state()
})
ipcMain.handle('link:emergency', () => link.emergencyLand())
app.on('before-quit', () => link.stop())

// The built page is served from app://litebee/, not file://: the Python runtime (WebAssembly in a worker) needs fetch.
protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } },
])

app.whenReady().then(() => {
  const root = join(__dirname, '../renderer')
  protocol.handle('app', (request) => {
    const file = normalize(join(root, decodeURIComponent(new URL(request.url).pathname)))
    if (!file.startsWith(root)) return new Response('Not found', { status: 404 })
    return net.fetch(pathToFileURL(file).toString())
  })
  createWindow()
  // On the drone network (192.168.13.x) the link starts by itself, as LiteBee Go does; elsewhere the person picks the adapter.
  const drones = adapters().find((a) => a.ip.startsWith('192.168.13.'))
  if (drones && !SHOT) void link.start(drones.ip)
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
