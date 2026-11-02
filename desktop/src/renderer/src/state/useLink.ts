import { tr } from '@core/i18n'
import { decimal } from '../lib/color'
import { useCallback, useEffect, useState } from 'react'

/** Battery thresholds of the original app (litebee/safety.py): no flight below MIN, amber below WARN. */
export const MIN_VOLTS = 7.0
export const WARN_VOLTS = 7.4
const EMPTY_V = 6.0
const FULL_V = 8.4

/** A drone that has said nothing for this long is shown as having lost the link. */
export const SILENT_MS = 3000

export type BatteryLevel = 'ok' | 'warn' | 'low'
export const batteryLevel = (v: number): BatteryLevel => (v < MIN_VOLTS ? 'low' : v < WARN_VOLTS ? 'warn' : 'ok')
export const batteryFraction = (v: number) => Math.min(Math.max((v - EMPTY_V) / (FULL_V - EMPTY_V), 0.05), 1)
export const fmtVolts = (v: number) => `${decimal(v)} ${tr('В')}`
export const isAlive = (d: LiveDrone) => !d.lost && d.silentMs < SILENT_MS

/** `?live=1` shows made-up drones, to look at the interface without a drone at hand. */
const FAKE: LinkState = {
  pcIp: '192.168.13.100',
  error: null,
  loaded: [],
  armed: false,
  flying: false,
  drones: [
    { ip: '192.168.13.104', droneId: '1', batteryV: 7.9, x: 40, y: 40, z: 0, cell: 13, fix: true, running: false, lost: false, silentMs: 80 },
    { ip: '192.168.13.108', droneId: '2', batteryV: 7.3, x: 200, y: 160, z: 0, cell: 5 + 12 * 4, fix: true, running: false, lost: false, silentMs: 60 },
    { ip: '192.168.13.109', droneId: '3', batteryV: 6.8, x: 0, y: 0, z: 0, cell: null, fix: false, running: false, lost: false, silentMs: 90 },
  ],
}
const WANT_FAKE = new URLSearchParams(location.search).get('live') === '1'

/** The link to the drones, as the main process reports it: who is connected, battery, position. */
export function useLink() {
  const bridge = window.litebee?.link
  const [state, setState] = useState<LinkState | null>(WANT_FAKE ? FAKE : null)
  const [adapters, setAdapters] = useState<{ name: string; ip: string }[]>([])

  useEffect(() => {
    if (!bridge || WANT_FAKE) return
    let alive = true
    const poll = () => bridge.state().then((s) => alive && setState(s)).catch(() => undefined)
    void bridge.adapters().then((a) => alive && setAdapters(a))
    poll()
    const id = setInterval(poll, 500)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [bridge])

  const start = useCallback((ip: string) => bridge?.start(ip).then(setState), [bridge])
  const stop = useCallback(() => bridge?.stop().then(setState), [bridge])
  const refresh = useCallback(() => bridge?.state().then(setState), [bridge])
  const arm = useCallback((on: boolean) => bridge?.arm(on).then(refresh), [bridge, refresh])
  const go = useCallback(
    (ips: string[], maxHeightCm: number) => bridge?.go({ ips, maxHeightCm }).then((r) => (refresh(), r)),
    [bridge, refresh],
  )
  const forget = useCallback(() => bridge?.forget().then(setState), [bridge])
  const emergency = useCallback(() => bridge?.emergency() ?? Promise.resolve(0), [bridge])

  const drones = state?.drones ?? []
  return {
    available: Boolean(bridge) || WANT_FAKE,
    state,
    adapters,
    drones,
    /** the drones that are talking to us now, and the ones that fell silent or lost the link (the archive) */
    active: drones.filter(isAlive),
    archive: drones.filter((d) => !isAlive(d)),
    /** at least one drone is talking to us */
    connected: drones.some(isAlive),
    start,
    stop,
    arm,
    go,
    refresh,
    forget,
    emergency,
  }
}

export type Link = ReturnType<typeof useLink>
