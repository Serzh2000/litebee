/// <reference types="vite/client" />

declare module '*.css'

interface LiveDrone {
  ip: string
  droneId: string
  batteryV: number
  x: number
  y: number
  z: number
  cell: number | null
  fix: boolean
  running: boolean
  lost: boolean
  silentMs: number
}

interface LinkState {
  pcIp: string | null
  error: string | null
  drones: LiveDrone[]
  /** IPs that hold an uploaded mission */
  loaded: string[]
  armed: boolean
  flying: boolean
}

interface Window {
  /** Added by src/preload/index.ts; absent when the page is opened in a plain browser. */
  litebee?: {
    platform: string
    openProject: () => Promise<{ path: string; text: string } | null>
    setLang: (lang: string) => Promise<void>
    readProject: (path: string) => Promise<{ path: string; text: string } | null>
    saveProject: (args: { text: string; path: string | null; suggested: string }) => Promise<{ path: string } | null>
    link: {
      adapters: () => Promise<{ name: string; ip: string }[]>
      state: () => Promise<LinkState>
      start: (pcIp: string) => Promise<LinkState>
      stop: () => Promise<LinkState>
      upload: (args: { ip: string; steps: unknown[]; maxHeightCm: number }) => Promise<{ ok: boolean; message: string }>
      arm: (on: boolean) => Promise<boolean>
      go: (args: { ips: string[]; maxHeightCm: number }) => Promise<{ ok: boolean; message: string }>
      forget: () => Promise<LinkState>
      emergency: () => Promise<number>
    }
  }
}
