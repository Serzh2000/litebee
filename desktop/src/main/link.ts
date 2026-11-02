import { createSocket, type Socket } from 'node:dgram'
import { createServer, type Server, type Socket as TcpSocket } from 'node:net'
import { networkInterfaces } from 'node:os'
import {
  clearMissionFrame,
  compileDrone,
  firstMoveCell,
  type Mission,
  missionCanFly,
  missionChecksum,
  missionFrames,
  missionMaxHeight,
  missionSeconds,
  UploadUnsupported,
  unprovenSteps,
  uploadProblems,
} from '../core/mission'
import type { Step } from '../core/show'
import {
  ALL_AUTOLAND,
  announceFrame,
  cellFromXY,
  decodeTelemetry,
  hasFix,
  heartbeatFrame,
  parseFrames,
  pilotCallbackFrame,
  startFrame,
  startTick,
  stopFrame,
  TCP_PORT,
  TELEMETRY_GROUP,
  TELEMETRY_ID,
  timesyncFrame,
  UDP_LOCAL,
  UDP_REMOTE,
  type Telemetry,
} from '../core/protocol'

/** What the page gets: one record per drone that has connected, the latest numbers it reported. */
export interface LiveDrone {
  ip: string
  droneId: string
  batteryV: number
  x: number
  y: number
  z: number
  /** mat cell under the drone; null without a position fix or off the mat */
  cell: number | null
  fix: boolean
  running: boolean
  /** the TCP connection is closed */
  lost: boolean
  /** ms since the last telemetry */
  silentMs: number
}

export interface LinkState {
  /** the PC address we listen on; null while the link is off */
  pcIp: string | null
  error: string | null
  drones: LiveDrone[]
  /** IPs that hold an uploaded mission */
  loaded: string[]
  armed: boolean
  flying: boolean
}

interface Conn {
  ip: string
  sock: TcpSocket
  telemetry: Telemetry | null
  lastRx: number
  lost: boolean
  beat: ReturnType<typeof setInterval>
}

export interface UploadResult {
  ok: boolean
  /** Russian text for the person: what happened, or why it did not go */
  message: string
}

export interface Adapter {
  name: string
  ip: string
}

/** IPv4 addresses of this PC that could be on the drones' network. The drone network (192.168.13.x) comes first. */
export function adapters(): Adapter[] {
  const out: Adapter[] = []
  for (const [name, list] of Object.entries(networkInterfaces())) {
    for (const a of list ?? []) if (a.family === 'IPv4' && !a.internal) out.push({ name, ip: a.address })
  }
  return out.sort((p, q) => Number(q.ip.startsWith('192.168.13.')) - Number(p.ip.startsWith('192.168.13.')))
}

/**
 * Listens to drones the way LiteBee Go does: announces the PC address by UDP (once a second) with a time sync (ten
 * times a second), accepts the drone's TCP connection, answers with the pilot callback, then heartbeats every 50 ms and
 * keeps the latest telemetry of each drone. The only frame it ever sends besides those is the emergency landing.
 */
export class Link {
  private pcIp: string | null = null
  private error: string | null = null
  private server: Server | null = null
  private udp: Socket | null = null
  private ticker: ReturnType<typeof setInterval> | null = null
  private tick = 0
  private conns = new Map<string, Conn>()
  /** the mission that is on board each drone, as it was uploaded */
  private loaded = new Map<string, Mission>()
  private armed = false
  private flying = false
  private abort = false

  async start(pcIp: string): Promise<void> {
    this.stop()
    this.error = null
    const server = createServer((sock) => this.accept(sock))
    try {
      await new Promise<void>((ok, fail) => {
        server.once('error', fail)
        server.listen(TCP_PORT, pcIp, () => ok())
      })
    } catch (e) {
      const busy = (e as NodeJS.ErrnoException).code === 'EADDRINUSE'
      this.error = busy
        ? `Порт ${TCP_PORT} занят: закройте старое приложение Litebee или LiteBee Go`
        : `Не удалось слушать ${pcIp}: ${(e as Error).message}`
      server.close()
      return
    }
    this.server = server
    this.pcIp = pcIp
    server.on('error', () => undefined)

    const udp = createSocket('udp4')
    udp.on('error', () => undefined)
    // Sending does not need port 6000; when something else holds it, any port will do.
    const bind = (port: number) => new Promise<void>((ok, fail) => udp.once('error', fail).bind(port, pcIp, ok))
    try {
      await bind(UDP_LOCAL)
    } catch {
      await bind(0).catch(() => undefined)
    }
    try {
      udp.setBroadcast(true)
    } catch {
      /* no broadcast: the drones will not find us, the page shows nobody connected */
    }
    this.udp = udp
    const bcast = `${pcIp.split('.').slice(0, 3).join('.')}.255`
    const announce = announceFrame(pcIp)
    this.tick = 0
    let n = 0
    this.ticker = setInterval(() => {
      if (n++ % 10 === 0) udp.send(announce, UDP_REMOTE, bcast, () => undefined)
      this.tick += 1
      udp.send(timesyncFrame(this.tick), UDP_REMOTE, bcast, () => undefined)
    }, 100)
  }

  stop(): void {
    if (this.ticker) clearInterval(this.ticker)
    this.ticker = null
    try {
      this.udp?.close()
    } catch {
      /* already closed */
    }
    this.udp = null
    for (const c of this.conns.values()) this.drop(c)
    this.conns.clear()
    this.server?.close()
    this.server = null
    this.pcIp = null
    this.loaded.clear()
    this.armed = false
    this.abort = true
  }

  private drop(c: Conn): void {
    c.lost = true
    clearInterval(c.beat)
    c.sock.destroy()
  }

  private accept(sock: TcpSocket): void {
    const ip = (sock.remoteAddress ?? '').replace(/^::ffff:/, '')
    this.conns.get(ip) && this.drop(this.conns.get(ip)!)
    let beat = 0
    const c: Conn = {
      ip,
      sock,
      telemetry: null,
      lastRx: 0,
      lost: false,
      beat: setInterval(() => sock.write(heartbeatFrame(beat++ % 256), () => undefined), 50),
    }
    this.conns.set(ip, c)
    sock.on('error', () => undefined)
    sock.on('close', () => {
      c.lost = true
      clearInterval(c.beat)
      // a drone that went away holds nothing we can vouch for, and arming does not survive a loss
      if (this.conns.get(ip) === c) {
        this.loaded.delete(ip)
        this.armed = false
      }
    })
    sock.write(pilotCallbackFrame())
    let buf: Buffer = Buffer.alloc(0)
    sock.on('data', (chunk: Buffer) => {
      const parsed = parseFrames(Buffer.concat([buf, chunk]))
      buf = parsed.rest
      for (const f of parsed.frames) {
        if (f.group !== TELEMETRY_GROUP || f.id !== TELEMETRY_ID) continue
        const t = decodeTelemetry(f.data)
        if (t) {
          c.telemetry = t
          c.lastRx = Date.now()
        }
      }
    })
  }

  /**
   * Put the program of one show drone on board: compile it, run the safety rules against the drone's own latest
   * telemetry (battery, standing place), clear the old mission, send the steps and compare the checksum the drone
   * reports. Nothing is started: the motors do not spin.
   */
  async upload(ip: string, steps: Step[], maxHeightCm: number): Promise<UploadResult> {
    this.loaded.delete(ip)
    this.armed = false
    if (this.flying) return { ok: false, message: 'Идёт полёт: загрузка недоступна' }
    const c = this.conns.get(ip)
    if (!c || c.lost || !c.telemetry || Date.now() - c.lastRx > 3000) return { ok: false, message: `Дрон ${ip} не на связи` }
    let mission
    try {
      mission = compileDrone(steps)
    } catch (e) {
      if (e instanceof UploadUnsupported) return { ok: false, message: e.message }
      throw e
    }
    const t = c.telemetry
    const problems = uploadProblems(mission, { batteryV: t.batteryV, x: t.x, y: t.y }, maxHeightCm)
    if (problems.length) return { ok: false, message: problems.join('; ') }

    const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))
    const send = (b: Uint8Array) =>
      new Promise<void>((ok, fail) => c.sock.write(b, (err) => (err ? fail(err) : ok())))
    try {
      await send(clearMissionFrame())
      await wait(300)
      for (const f of missionFrames(mission)) {
        await send(f)
        await wait(20)
      }
      await wait(1200)
    } catch {
      return { ok: false, message: `Дрон ${ip} потерял связь во время загрузки. Проверьте питание и повторите` }
    }
    const got = c.telemetry?.checksum
    const expected = missionChecksum(mission)
    if (got === expected) this.loaded.set(ip, mission)
    return got === expected
      ? { ok: true, message: `Дрон ${ip}: миссия загружена, контрольная сумма ${expected} совпала` }
      : { ok: false, message: `Дрон ${ip}: миссия не принята. Ждали контрольную сумму ${expected}, получили ${got}. Загрузите ещё раз` }
  }

  /** Arm: only with a mission on board a drone that is on the link. Disarming is always possible. */
  arm(on: boolean): boolean {
    const alive = (ip: string) => this.conns.get(ip) && !this.conns.get(ip)!.lost
    if (!on) this.armed = false
    else if (!this.flying && [...this.loaded.keys()].some(alive)) this.armed = true
    return this.armed
  }

  /**
   * Start the missions that are on board. Every rule is checked again against the drones' latest telemetry, nothing
   * starts unless all drones pass, and `confirm` (a native dialog) must say yes. After the start each drone is watched
   * until its mission ends; a lost link, an abort or any error lands it, and a landing frame follows every mission.
   */
  async launch(
    ips: string[],
    maxHeightCm: number,
    confirm: (lines: string[], flies: boolean) => Promise<boolean>,
  ): Promise<UploadResult> {
    if (this.flying) return { ok: false, message: 'Полёт уже идёт' }
    if (!this.armed) return { ok: false, message: 'Дрон не взведён, старт отменён' }
    const targets = ips.filter((ip) => this.loaded.has(ip) && this.conns.get(ip) && !this.conns.get(ip)!.lost)
    if (targets.length === 0) return { ok: false, message: 'Миссия не загружена, старт отменён' }

    const lines: string[] = []
    let flies = false
    for (const ip of targets) {
      const m = this.loaded.get(ip)!
      const t = this.conns.get(ip)!.telemetry
      if (!t) return { ok: false, message: `Дрон ${ip}: нет телеметрии, старт отменён` }
      const problems = uploadProblems(m, { batteryV: t.batteryV, x: t.x, y: t.y }, maxHeightCm)
      if (problems.length) return { ok: false, message: `Дрон ${ip}: ${problems.join('; ')}` }
      flies ||= missionCanFly(m)
      const first = firstMoveCell(m)
      const cell = hasFix(t) ? cellFromXY(t.x, t.y) : null
      const unproven = unprovenSteps(m)
      if (unproven.length) lines.push(`Дрон ${ip}: ВНИМАНИЕ, не проверены на живом дроне шаги ${unproven.join(', ')}. Будьте готовы к аварийной посадке (Esc)`)
      lines.push(
        `Дрон ${ip}: контрольная сумма ${missionChecksum(m)} совпала, высота до ${missionMaxHeight(m)} см (лимит ${maxHeightCm} см), ` +
          `~${missionSeconds(m).toFixed(0)} с` +
          (first !== null ? `, стоит на ${cell !== null ? `клетке ${cell}` : 'неизвестной клетке'}, первое движение к клетке ${first}` : ''),
      )
    }
    if (!(await confirm(lines, flies))) return { ok: false, message: 'Старт отменён' }
    if (!this.armed || this.flying) return { ok: false, message: 'Старт отменён: состояние изменилось' }

    this.abort = false
    this.flying = true
    const pcTick = this.tick
    const started: string[] = []
    for (const ip of targets) {
      const c = this.conns.get(ip)!
      try {
        await new Promise<void>((ok, fail) =>
          c.sock.write(startFrame(startTick(c.telemetry?.clock ?? 0, pcTick)), (e) => (e ? fail(e) : ok())),
        )
        started.push(ip)
      } catch {
        this.land(ip)
      }
    }
    if (started.length === 0) {
      this.flying = false
      this.armed = false
      return { ok: false, message: 'Не удалось отправить старт: связь потеряна' }
    }
    let left = started.length
    for (const ip of started) {
      void this.watch(ip, this.loaded.get(ip)!).finally(() => {
        this.loaded.delete(ip) // load again before the next flight
        if (--left === 0) {
          this.flying = false
          this.armed = false // arming never survives a flight
        }
      })
    }
    return { ok: true, message: `Старт отправлен дронов: ${started.length}` }
  }

  /** Send all_autoLand to one drone, three times (idempotent, a no-op on the ground). */
  private land(ip: string): void {
    const c = this.conns.get(ip)
    if (!c || c.lost) return
    for (let i = 0; i < 3; i++) setTimeout(() => !c.lost && c.sock.write(ALL_AUTOLAND, () => undefined), i * 100)
  }

  private async watch(ip: string, m: Mission): Promise<void> {
    const c = this.conns.get(ip)
    if (!c) return
    const flies = missionCanFly(m)
    const deadline = Date.now() + (flies ? missionSeconds(m) + 20 : 8) * 1000
    let seenRunning = false
    try {
      while (Date.now() < deadline) {
        if (c.lost || this.abort) return
        if (c.telemetry) {
          const running = c.telemetry.running === 1
          seenRunning ||= running
          if (seenRunning && !running) break
        }
        await new Promise((r) => setTimeout(r, 100))
      }
      if (!flies && !c.lost) c.sock.write(stopFrame(), () => undefined)
    } finally {
      this.land(ip) // after every started mission, and after a loss, an abort or an error: land
    }
  }

  /** Forget the drones whose connection is closed (the archive of the page), so only the ones that came back stay. */
  forgetLost(): void {
    if (this.flying) return
    for (const [ip, c] of this.conns) {
      if (c.lost) {
        this.conns.delete(ip)
        this.loaded.delete(ip)
      }
    }
  }

  /** Land every connected drone. Idempotent, safe on the ground. Returns how many drones the frame went to. */
  emergencyLand(): number {
    this.abort = true
    this.armed = false
    let sent = 0
    for (const c of this.conns.values()) {
      if (c.lost) continue
      for (let i = 0; i < 3; i++) setTimeout(() => !c.lost && c.sock.write(ALL_AUTOLAND, () => undefined), i * 100)
      sent++
    }
    return sent
  }

  state(): LinkState {
    const now = Date.now()
    const drones = [...this.conns.values()]
      .filter((c) => c.telemetry)
      .map((c): LiveDrone => {
        const t = c.telemetry!
        const fix = hasFix(t)
        return {
          ip: c.ip,
          droneId: t.droneId,
          batteryV: t.batteryV,
          x: t.x,
          y: t.y,
          z: t.z,
          cell: fix ? cellFromXY(t.x, t.y) : null,
          fix,
          running: t.running === 1,
          lost: c.lost,
          silentMs: now - c.lastRx,
        }
      })
      .sort((p, q) => p.ip.localeCompare(q.ip, undefined, { numeric: true }))
    return { pcIp: this.pcIp, error: this.error, drones, loaded: [...this.loaded.keys()], armed: this.armed, flying: this.flying }
  }
}
