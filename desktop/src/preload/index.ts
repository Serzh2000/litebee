import { contextBridge, ipcRenderer } from 'electron'

// The renderer reaches the machine only through this object.
contextBridge.exposeInMainWorld('litebee', {
  platform: process.platform,
  openProject: () => ipcRenderer.invoke('project:open'),
  setLang: (lang: string) => ipcRenderer.invoke('app:lang', lang),
  readProject: (path: string) => ipcRenderer.invoke('project:read', path),
  saveProject: (args: { text: string; path: string | null; suggested: string }) => ipcRenderer.invoke('project:save', args),
  link: {
    adapters: () => ipcRenderer.invoke('link:adapters'),
    state: () => ipcRenderer.invoke('link:state'),
    start: (pcIp: string) => ipcRenderer.invoke('link:start', pcIp),
    stop: () => ipcRenderer.invoke('link:stop'),
    upload: (args: unknown) => ipcRenderer.invoke('link:upload', args),
    arm: (on: boolean) => ipcRenderer.invoke('link:arm', on),
    go: (args: { ips: string[]; maxHeightCm: number }) => ipcRenderer.invoke('link:go', args),
    forget: () => ipcRenderer.invoke('link:forget'),
    emergency: () => ipcRenderer.invoke('link:emergency'),
  },
})
