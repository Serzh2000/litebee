import { describe, expect, it } from 'vitest'
import {
  ALL_AUTOLAND,
  announceFrame,
  cellFromXY,
  decodeTelemetry,
  hasFix,
  heartbeatFrame,
  parseFrames,
  pilotCallbackFrame,
  timesyncFrame,
} from '@core/protocol'

// Hex strings come from litebee/protocol.py, so the two implementations stay byte-identical.
const hex = (b: Uint8Array) => Buffer.from(b).toString('hex')
const TELEMETRY = 'b0ff780064004b0109037f0080841a55050000006e'
const TELEMETRY_FRAME = 'fa15000108' + TELEMETRY + '68ad'

describe('protocol frames', () => {
  it('builds the frames the same bytes as the Python module', () => {
    expect(hex(announceFrame('192.168.13.100'))).toBe('fa04000303c0a80d64751c')
    expect(hex(timesyncFrame(1234))).toBe('fa04000209d20400000f91')
    expect(hex(heartbeatFrame(7))).toBe('fa01000003071b65')
    expect(hex(pilotCallbackFrame())).toBe('fa02000201080a1602')
    expect(hex(ALL_AUTOLAND)).toBe('fa090002030400000000000000007ff8')
  })

  it('decodes a telemetry frame', () => {
    const { frames, rest } = parseFrames(Buffer.from(TELEMETRY_FRAME, 'hex'))
    expect(rest.length).toBe(0)
    expect(frames).toHaveLength(1)
    const t = decodeTelemetry(frames[0].data)!
    expect(t).toMatchObject({ x: 120, y: -80, z: 100, batteryV: 7.5, running: 1, checksum: 777, droneId: '128132' + '26' + '85' })
    expect(hasFix(t)).toBe(true)
  })

  it('finds frames in noise and waits for the rest of a split frame', () => {
    const whole = Buffer.from(TELEMETRY_FRAME, 'hex')
    const noisy = Buffer.concat([Buffer.from([1, 2, 3]), whole.subarray(0, 10)])
    const first = parseFrames(noisy)
    expect(first.frames).toHaveLength(0)
    const second = parseFrames(Buffer.concat([first.rest, whole.subarray(10), whole]))
    expect(second.frames).toHaveLength(2)
  })

  it('drops a frame with a bad CRC', () => {
    const bad = Buffer.from(TELEMETRY_FRAME, 'hex')
    bad[10] ^= 0xff
    expect(parseFrames(bad).frames).toHaveLength(0)
  })

  it('rounds a position to the mat cell', () => {
    expect(cellFromXY(0, 0)).toBe(0)
    expect(cellFromXY(41, 79)).toBe(1 + 12 * 2)
    expect(cellFromXY(-100, 0)).toBeNull()
    expect(cellFromXY(0, 600)).toBeNull()
  })
})
