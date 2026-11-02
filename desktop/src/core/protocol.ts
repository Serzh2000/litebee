/**
 * LiteBee Wing wire protocol, the part needed to listen to drones: frames, CRC, frame parser, telemetry.
 * A port of litebee/protocol.py (the tests pin the bytes to values taken from it).
 *
 * Frame: 0xFA + [len, 0, group, id, data...] + CRC-16 (low byte first), `len` is the number of data bytes.
 */
export const TCP_PORT = 18001
export const UDP_LOCAL = 6000
export const UDP_REMOTE = 13146

/** CRC-16/MCRF4XX: init 0xFFFF, reflected 0x8408, no final xor, low byte first. */
export function crc16(data: ArrayLike<number>): [number, number] {
  let crc = 0xffff
  for (let i = 0; i < data.length; i++) {
    crc ^= data[i]
    for (let k = 0; k < 8; k++) crc = crc & 1 ? (crc >> 1) ^ 0x8408 : crc >> 1
  }
  return [crc & 0xff, crc >> 8]
}

/** A plain Uint8Array, so the page (which has no Buffer) can build frames too. */
export function frame(payload: number[]): Uint8Array {
  return Uint8Array.from([0xfa, ...payload, ...crc16(payload)])
}

export interface Frame {
  group: number
  id: number
  data: Buffer
}

/** Takes the valid frames out of `buf`; returns them and the bytes that are left (a frame that has not fully arrived). */
export function parseFrames(buf: Buffer): { frames: Frame[]; rest: Buffer } {
  const frames: Frame[] = []
  let b = buf
  for (;;) {
    const start = b.indexOf(0xfa)
    if (start < 0) return { frames, rest: Buffer.alloc(0) }
    b = b.subarray(start)
    if (b.length < 2) return { frames, rest: b }
    const n = b[1]
    if (n >= 128) {
      b = b.subarray(1)
      continue
    }
    const total = 1 + 4 + n + 2
    if (b.length < total) return { frames, rest: b }
    const payload = b.subarray(1, 5 + n)
    const [lo, hi] = crc16(payload)
    if (b[5 + n] === lo && b[6 + n] === hi) {
      frames.push({ group: payload[2], id: payload[3], data: Buffer.from(payload.subarray(4)) })
      b = b.subarray(total)
    } else {
      b = b.subarray(1)
    }
  }
}

/** UDP announcement of the PC address. */
export const announceFrame = (pcIp: string): Uint8Array => frame([4, 0, 3, 3, ...pcIp.split('.').map(Number)])

/** UDP time sync, sent ten times a second: [4,0,2,9, u32 LE tick]. */
export function timesyncFrame(tick: number): Uint8Array {
  const t = Buffer.alloc(4)
  t.writeUInt32LE(tick >>> 0)
  return frame([4, 0, 2, 9, ...t])
}

export const heartbeatFrame = (n: number) => frame([1, 0, 0, 3, n & 255])

/** Start of the uploaded mission at a tick of the PC's time sync: [5,0,2,8, 1, u32 LE tick]. */
export function startFrame(startTick: number): Uint8Array {
  const t = new Uint8Array(4)
  new DataView(t.buffer).setUint32(0, startTick >>> 0, true)
  return frame([5, 0, 2, 8, 1, ...t])
}

export const stopFrame = () => frame([1, 0, 2, 8, 0])

/** Start time rule of LiteBee Go: from the drone's clock if it reports one, else our own tick + 3 s (live drones report 0). */
export const startTick = (droneClock: number, pcTick: number) => (droneClock ? Math.trunc(0.1 * (droneClock + 300)) : pcTick + 30)

/** "Set pilot callback", sent right after a drone connects, as the original app does. */
export const pilotCallbackFrame = () => frame([2, 0, 2, 1, 8, 10])

/** all_autoLand: land every drone. Idempotent, a no-op on the ground. */
export const ALL_AUTOLAND = frame([9, 0, 2, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0])

export const TELEMETRY_GROUP = 1
export const TELEMETRY_ID = 8

export interface Telemetry {
  /** cm on the mat */
  x: number
  y: number
  z: number
  batteryV: number
  /** 1 while a mission is running */
  running: number
  /** checksum of the uploaded mission */
  checksum: number
  droneId: string
  /** the drone's own clock; live drones report 0 */
  clock: number
}

/** Data of a group 1 / id 8 frame (21 bytes on live drones). The first two int16 are (y, x), then z. */
export function decodeTelemetry(data: Buffer): Telemetry | null {
  if (data.length < 20) return null
  return {
    y: data.readInt16LE(0),
    x: data.readInt16LE(2),
    z: data.readInt16LE(4),
    batteryV: data[6] / 10,
    running: data[7],
    checksum: data[8] + 256 * data[9],
    droneId: [...data.subarray(12, 16)].join(''),
    clock: data.readUInt32LE(16),
  }
}

/** A freshly powered drone reports x = y = 0 on the ground: that is no position on the mat. */
export const hasFix = (t: Telemetry) => t.x !== 0 || t.y !== 0

/** Mat cell under a position in cm; null when off the mat. */
export function cellFromXY(x: number, y: number): number | null {
  const col = Math.round(x / 40)
  const row = Math.round(y / 40)
  return col >= 0 && col < 12 && row >= 0 && row < 12 ? col + 12 * row : null
}
