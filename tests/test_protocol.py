import os
import struct
import sys

import pytest

from litebee import protocol as p
from litebee.mission import (CMD_RGB, Mission, MissionStep, hop_mission, rgb_mission, z_data)
from litebee.safety import SafetyError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_TELEMETRY = bytes.fromhex("00 00 00 00 00 00 4b 00 08 00 7f 00 80 84 1a 55 00 00 00 00 6e")


def test_crc_table_head():
    assert [p.crc_table_entry(i) for i in range(4)] == [0, 4489, 8978, 12955]


def test_announce_frame_golden():
    assert p.announce_frame("192.168.13.100").hex() == "fa04000303c0a80d64751c"


def test_other_frames_golden():
    assert p.clear_mission_frame().hex() == "fa010003000121c5"
    assert p.start_frame(30).hex() == "fa05000208011e000000444c"
    assert p.ALL_AUTOLAND.hex() == "fa090002030400000000000000007ff8"
    assert p.ALL_AUTOLAND == p.frame([9, 0, 2, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0])
    assert p.stop_frame() == p.frame([1, 0, 2, 8, 0])
    assert p.pilot_callback_frame() == p.frame([2, 0, 2, 1, 8, 10])
    assert p.heartbeat_frame(7) == p.frame([1, 0, 0, 3, 7])
    assert p.timesync_frame(5) == p.frame([4, 0, 2, 9, 5, 0, 0, 0])


def test_parser_roundtrip_and_garbage():
    f = p.frame([3, 0, 1, 8, 1, 2, 3])
    buf = bytearray(b"\x00\x01" + f[:5])
    assert list(p.parse_frames(buf)) == []
    buf += f[5:] + f
    out = list(p.parse_frames(buf))
    assert out == [p.Frame(1, 8, b"\x01\x02\x03")] * 2
    assert not buf
    bad = bytearray(f[:-1] + bytes([f[-1] ^ 1]))
    assert list(p.parse_frames(bad)) == []


def test_real_telemetry_frame():
    t = p.decode_telemetry(REAL_TELEMETRY)
    assert t.battery_v == 7.5
    assert t.id_bytes.hex(" ") == "80 84 1a 55"
    assert t.running == 0 and t.checksum == 8 and t.clock == 0 and (t.x, t.y, t.z) == (0, 0, 0)
    assert p.decode_telemetry(REAL_TELEMETRY[:19]) is None


def test_telemetry_encode_decode_roundtrip():
    raw = p.encode_telemetry(x=10, y=-20, z=100, volts=7.2, running=1, checksum=50, clock=99)
    assert len(raw) == 21
    t = p.decode_telemetry(raw)
    assert (t.x, t.y, t.z, t.battery_v, t.running, t.checksum, t.clock) == (10, -20, 100, 7.2, 1, 50, 99)
    assert p.decode_telemetry(REAL_TELEMETRY) == p.decode_telemetry(
        p.encode_telemetry(volts=7.5, checksum=8))


def test_rgb_only_mission_golden():
    m = rgb_mission(0, 255, 0)
    assert m.checksum == CMD_RGB == 50
    assert [f.hex() for f in m.frames()] == ["fa1300030201000100000032050002ffff00000000000000213a"]
    assert not m.can_fly


def test_hop_mission_golden():
    m = hop_mission(100, 3)
    assert len(m.steps) == 4 and m.checksum == 8 and m.total_seconds == 13.0
    assert [s.t_end for s in m.steps] == [50, 100, 130, 130]  # cumulative, 0.1 s
    assert m.can_fly and m.max_height_cm == 100 and m.max_hover_s == 3
    assert [f.hex() for f in m.frames()] == [
        "fa130003020400010032000000000000000000000000000058f9",
        "fa1300030204000200640001640000000000000000000000f934",
        "fa1300030204000300820005640000000000000000000000b163",
        "fa13000302040004008200020000000000000000000000007972",
    ]


def test_clear_and_step_layout():
    step = hop_mission(100, 3).steps[1]
    assert step.data[:2] == struct.pack("<H", 100) and step.cmd == 1


@pytest.mark.parametrize("h,hover", [(10, 3), (151, 3), (100, 11), (100, -1)])
def test_hop_builder_refuses_out_of_limits(h, hover):
    with pytest.raises(SafetyError):
        hop_mission(h, hover)


def test_step_time_overflow_rejected():
    with pytest.raises(ValueError):
        MissionStep(1, 70000, z_data(100))
    assert isinstance(Mission(), Mission)


# ---- byte-identity with the original root scripts (read-only imports) ----

@pytest.fixture(scope="module")
def originals():
    sys.path.insert(0, ROOT)
    try:
        import drone_color
        import drone_hop
        import drone_probe
    except ImportError:
        pytest.skip("original scripts not present")
    return drone_probe, drone_color, drone_hop


def test_identical_to_original_scripts(originals):
    dp, dc, dh = originals
    assert p.crc16(b"123456789") == dp.crc16(b"123456789")
    assert p.announce_frame("192.168.13.100") == dp.frame([4, 0, 3, 3, 192, 168, 13, 100])
    frames, expected = dc.rgb_mission(255, 0, 0)
    m = rgb_mission(255, 0, 0)
    assert m.frames() == frames and m.checksum == expected
    for h, hv in [(100, 3), (60, 0), (150, 10), (20, 7.5)]:
        frames, expected, total = dh.build_mission(h, hv)
        m = hop_mission(h, hv)
        assert m.frames() == frames and m.checksum == expected and m.total_seconds == total
    assert p.ALL_AUTOLAND == dh.ALL_AUTOLAND
    assert p.decode_telemetry(REAL_TELEMETRY).as_dict()["drone_id"] == dp.telemetry(REAL_TELEMETRY)["drone_id"]


def test_telemetry_position_fix_and_cell():
    from litebee.protocol import decode_telemetry, encode_telemetry
    none = decode_telemetry(encode_telemetry())                    # fresh drone: x = y = 0
    assert not none.has_fix and none.cell is None
    t = decode_telemetry(encode_telemetry(x=3, y=317))             # round(3/40) + 12 * round(317/40)
    assert t.has_fix and t.cell == 96 and (t.x, t.y) == (3, 317)
    assert decode_telemetry(encode_telemetry(x=40, y=320)).cell == 97
    assert decode_telemetry(encode_telemetry(x=440, y=440)).cell == 143
    assert decode_telemetry(encode_telemetry(x=0, y=1)).cell == 0 and decode_telemetry(encode_telemetry(x=0, y=1)).has_fix
    assert decode_telemetry(encode_telemetry(x=900, y=40)).cell is None      # off the mat, but a fix
    assert decode_telemetry(encode_telemetry(x=-300, y=40)).cell is None
