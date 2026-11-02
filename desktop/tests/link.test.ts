import { connect } from 'node:net'
import { afterEach, describe, expect, it } from 'vitest'
import { Link } from '../src/main/link'
import type { Step } from '../src/core/show'
import square from '../shows/quarter_square.json'
import { frame, parseFrames, TCP_PORT } from '../src/core/protocol'

// A fake drone on the loopback address: nothing leaves this PC.
const telemetry = (x: number, y: number, z: number, volts: number, running = 0, checksum = 0) => {
  const d = Buffer.alloc(21)
  d.writeInt16LE(y, 0)
  d.writeInt16LE(x, 2)
  d.writeInt16LE(z, 4)
  d[6] = Math.round(volts * 10)
  d[7] = running
  d.writeUInt16LE(checksum, 8)
  d.set([0x80, 0x84, 0x1a, 0x55], 12)
  return frame([21, 0, 1, 8, ...d])
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

describe('Link', () => {
  const link = new Link()
  afterEach(() => link.stop())

  it('answers a drone with the callback and heartbeats, and reports its telemetry', async () => {
    await link.start('127.0.0.1')
    expect(link.state().error).toBeNull()

    const drone = connect(TCP_PORT, '127.0.0.1')
    const got: { group: number; id: number }[] = []
    let buf: Buffer = Buffer.alloc(0)
    drone.on('data', (c: Buffer) => {
      const p = parseFrames(Buffer.concat([buf, c]))
      buf = p.rest
      got.push(...p.frames)
    })
    await new Promise((r) => drone.once('connect', r))
    drone.write(telemetry(120, 80, 100, 7.5))
    await wait(250)

    expect(got[0]).toMatchObject({ group: 2, id: 1 }) // pilot callback first
    expect(got.some((f) => f.group === 0 && f.id === 3)).toBe(true) // then heartbeats

    const [d] = link.state().drones
    expect(d).toMatchObject({ ip: '127.0.0.1', batteryV: 7.5, x: 120, y: 80, z: 100, cell: 3 + 12 * 2, fix: true, lost: false })
    drone.destroy()
  })

  it('sends all_autoLand to connected drones on emergency', async () => {
    await link.start('127.0.0.1')
    const drone = connect(TCP_PORT, '127.0.0.1')
    const seen: number[] = []
    drone.on('data', (c: Buffer) => parseFrames(c).frames.forEach((f) => seen.push(f.group * 256 + f.id)))
    await new Promise((r) => drone.once('connect', r))
    drone.write(telemetry(0, 0, 0, 7.9))
    await wait(100)
    expect(link.emergencyLand()).toBe(1)
    await wait(350)
    expect(seen.filter((k) => k === 2 * 256 + 3).length).toBeGreaterThanOrEqual(1)
    drone.destroy()
  })

  it('uploads, arms and starts a mission, watches it end and lands the drone after it', async () => {
    await link.start('127.0.0.1')
    const drone = connect(TCP_PORT, '127.0.0.1')
    const seen: number[] = []
    drone.on('data', (c: Buffer) => parseFrames(c).frames.forEach((f) => seen.push(f.group * 256 + f.id)))
    await new Promise((r) => drone.once('connect', r))
    // the drone stands on cell 13 with a good battery and reports the checksum of the mission we are about to send (118)
    drone.write(telemetry(40, 40, 0, 7.9, 0, 118))
    await wait(150)

    const steps = (square.drones as Record<string, unknown>)['1'] as Step[]
    const up = await link.upload('127.0.0.1', steps, 150)
    expect(up).toMatchObject({ ok: true })
    expect(link.state().loaded).toEqual(['127.0.0.1'])

    expect(await link.launch(['127.0.0.1'], 150, async () => true)).toMatchObject({ ok: false }) // not armed
    expect(link.arm(true)).toBe(true)
    expect(await link.launch(['127.0.0.1'], 150, async () => false)).toMatchObject({ ok: false, message: 'Старт отменён' })
    expect(link.state().flying).toBe(false)

    expect(await link.launch(['127.0.0.1'], 150, async () => true)).toMatchObject({ ok: true })
    expect(link.state().flying).toBe(true)
    await wait(100)
    expect(seen).toContain(2 * 256 + 8) // the start frame
    drone.write(telemetry(40, 40, 100, 7.8, 1, 118)) // running
    await wait(250)
    drone.write(telemetry(40, 40, 0, 7.8, 0, 118)) // finished
    await wait(500)
    expect(link.state()).toMatchObject({ flying: false, armed: false, loaded: [] })
    expect(seen).toContain(2 * 256 + 3) // all_autoLand after the mission
    drone.destroy()
  })

  it('refuses to start when the battery has dropped, and land on an emergency in flight', async () => {
    await link.start('127.0.0.1')
    const drone = connect(TCP_PORT, '127.0.0.1')
    const seen: number[] = []
    drone.on('data', (c: Buffer) => parseFrames(c).frames.forEach((f) => seen.push(f.group * 256 + f.id)))
    await new Promise((r) => drone.once('connect', r))
    drone.write(telemetry(40, 40, 0, 7.9, 0, 118))
    await wait(150)
    const steps = (square.drones as Record<string, unknown>)['1'] as Step[]
    await link.upload('127.0.0.1', steps, 150)
    link.arm(true)
    drone.write(telemetry(40, 40, 0, 6.5, 0, 118))
    await wait(150)
    expect((await link.launch(['127.0.0.1'], 150, async () => true)).message).toMatch(/Батарея/)

    drone.write(telemetry(40, 40, 0, 7.9, 0, 118))
    await wait(150)
    expect(await link.launch(['127.0.0.1'], 150, async () => true)).toMatchObject({ ok: true })
    link.emergencyLand()
    await wait(500)
    expect(seen.filter((k) => k === 2 * 256 + 3).length).toBeGreaterThanOrEqual(1)
    expect(link.state()).toMatchObject({ flying: false, armed: false })
    drone.destroy()
  })

  it('keeps a drone that went away until the archive is cleared', async () => {
    await link.start('127.0.0.1')
    const drone = connect(TCP_PORT, '127.0.0.1')
    await new Promise((r) => drone.once('connect', r))
    drone.write(telemetry(40, 40, 0, 7.9))
    await wait(150)
    expect(link.state().drones).toHaveLength(1)
    drone.destroy()
    await wait(150)
    expect(link.state().drones[0]).toMatchObject({ lost: true })
    link.forgetLost()
    expect(link.state().drones).toHaveLength(0)
  })
})
