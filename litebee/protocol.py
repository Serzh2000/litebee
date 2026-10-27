"""LiteBee Wing wire protocol: frames, CRC, frame parser, telemetry decode.

Ported from drone_probe.py / drone_color.py / drone_hop.py. Wire behaviour is
byte-identical to those scripts (tests compare against them).

Frame: 0xFA + [len, 0, group, id, data...] + CRC-16 (low byte first), where
`len` is the number of data bytes.
"""
import struct
from typing import Iterator, NamedTuple, Optional

# Real-use defaults. The package never binds/sends to these in loopback mode.
TCP_PORT, UDP_LOCAL, UDP_REMOTE = 18001, 6000, 13146
REAL_PORTS = frozenset({TCP_PORT, UDP_LOCAL, UDP_REMOTE})

CRC_TABLE_HEAD = [0, 4489, 8978, 12955]  # first entries of the table in LiteBee Go


def crc16(data) -> bytes:
    """CRC-16/MCRF4XX: init 0xFFFF, reflected 0x8408, no final xor, low byte first."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return bytes((crc & 0xFF, crc >> 8))


def crc_table_entry(i: int) -> int:
    crc = i
    for _ in range(8):
        crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc


assert [crc_table_entry(i) for i in range(4)] == CRC_TABLE_HEAD, "CRC variant does not match the app"


def frame(payload) -> bytes:
    """payload = [len, 0, group, id, *data] -> 0xFA + payload + crc."""
    return bytes([0xFA]) + bytes(payload) + crc16(bytes(payload))


class Frame(NamedTuple):
    group: int
    id: int
    data: bytes


def parse_frames(buf: bytearray) -> Iterator[Frame]:
    """Yield a Frame for each valid frame in buf; leave the remainder in buf."""
    while True:
        start = buf.find(0xFA)
        if start < 0:
            buf.clear()
            return
        del buf[:start]
        if len(buf) < 2:
            return
        n = buf[1]
        if n >= 128:
            del buf[0]
            continue
        total = 1 + 4 + n + 2
        if len(buf) < total:
            return
        payload = bytes(buf[1:5 + n])
        if crc16(payload) == bytes(buf[5 + n:total]):
            del buf[:total]
            yield Frame(payload[2], payload[3], payload[4:])
        else:
            del buf[0]


# ---- frame builders -------------------------------------------------------

def announce_frame(pc_ip: str) -> bytes:
    """UDP announcement of the PC address: [4,0,3,3, ip x4]."""
    return frame([4, 0, 3, 3, *map(int, pc_ip.split("."))])


def timesync_frame(tick: int) -> bytes:
    """UDP time sync, sent 10x a second: [4,0,2,9, u32 LE tick]."""
    return frame([4, 0, 2, 9, *struct.pack("<I", tick)])


def heartbeat_frame(n: int) -> bytes:
    return frame([1, 0, 0, 3, n % 256])


def pilot_callback_frame() -> bytes:
    """"Set pilot callback", sent by the app right after the drone connects."""
    return frame([2, 0, 2, 1, 8, 10])


def clear_mission_frame() -> bytes:
    return frame([1, 0, 3, 0, 1])


def start_frame(start_tick: int) -> bytes:
    return frame([5, 0, 2, 8, 1, *struct.pack("<I", start_tick)])


def stop_frame() -> bytes:
    return frame([1, 0, 2, 8, 0])


# all_autoLand: land every drone. Idempotent; a no-op on the ground.
ALL_AUTOLAND = frame([9, 0, 2, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0])


def start_tick(drone_clock: int, pc_tick: int) -> int:
    """Start time rule of LiteBee Go, kept exactly as in drone_color/drone_hop:
    from the drone's clock if it reports one, else our own tick counter + 3 s.
    (Live drones report clock 0, so the second branch is the proven one.)"""
    return int(0.1 * (drone_clock + 300)) if drone_clock else pc_tick + 30


# ---- telemetry ------------------------------------------------------------

class Telemetry(NamedTuple):
    x: int
    y: int
    z: int
    battery_v: float
    running: int
    checksum: int       # mission checksum the drone computed (bytes 8-9, LE)
    drone_id: str
    id_bytes: bytes
    clock: int
    raw: bytes

    @property
    def has_fix(self) -> bool:
        """A freshly powered drone reports x = y = 0 on the ground: that is NO position on the mat."""
        return bool(self.x or self.y)

    @property
    def cell(self):
        """Mat cell under the drone, round(x/40) + 12 * round(y/40); None without a fix or off the mat."""
        from .mission import cell_from_xy      # local: mission imports this module
        return cell_from_xy(self.x, self.y) if self.has_fix else None

    def as_dict(self):
        d = self._asdict()
        d.pop("raw")
        d["id_bytes"] = self.id_bytes.hex(" ")
        return d


TELEMETRY_GROUP, TELEMETRY_ID = 1, 8


def decode_telemetry(data: bytes) -> Optional[Telemetry]:
    """Decode the data bytes of a group 1 / id 8 frame (21 bytes on live drones).

    The first two int16 are (y, x), as in drone_probe/drone_hop; then z.
    """
    if len(data) < 20:
        return None
    y, x, z = struct.unpack_from("<3h", data, 0)
    return Telemetry(x=x, y=y, z=z, battery_v=data[6] / 10, running=data[7],
                     checksum=data[8] + 256 * data[9],
                     drone_id="".join(map(str, data[12:16])), id_bytes=bytes(data[12:16]),
                     clock=struct.unpack_from("<I", data, 16)[0], raw=bytes(data))


def encode_telemetry(*, x=0, y=0, z=0, volts=7.5, running=0, checksum=0,
                     id_bytes=(0x80, 0x84, 0x1A, 0x55), clock=0) -> bytes:
    """Inverse of decode_telemetry (21 data bytes); used by the fake drone."""
    data = bytearray(struct.pack("<3h", y, x, z))
    data += bytes([int(round(volts * 10)) & 255, running & 255])
    data += struct.pack("<H", checksum & 0xFFFF)
    data += bytes([0x7F, 0x00])
    data += bytes(id_bytes)
    data += struct.pack("<I", clock)
    data += bytes([0x6E])
    return bytes(data)
