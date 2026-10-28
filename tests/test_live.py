"""Live (non-mission) frames: exact bytes from LiteBee Go's own code, ranges, CRC. Nothing here uses a socket."""
import pytest

from litebee import live, protocol as p
from litebee.safety import SafetyError


def payload(fr: bytes) -> list:
    """The [len, 0, group, id, data...] part of a frame, after checking 0xFA and the CRC."""
    assert fr[0] == 0xFA
    assert fr[-2:] == p.crc16(fr[1:-2])
    return list(fr[1:-2])


def test_frames_equal_the_arrays_in_litebee_go():
    assert payload(live.calibrate_frame()) == [2, 0, 2, 2, 0, 0]
    assert payload(live.takeoff_frame()) == [9, 0, 2, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0]
    assert payload(live.hold_frame()) == [9, 0, 2, 3, 2, 0, 0, 0, 0, 0, 0, 0, 0]
    assert payload(live.land_frame()) == [9, 0, 2, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0]
    assert live.land_frame() == p.ALL_AUTOLAND                      # the emergency frame we already use


def test_velocity_signs_follow_the_app():
    assert payload(live.velocity_frame(20, 0)) == [5, 0, 2, 13, 2, 0, 20, 0, 0]          # forward
    assert payload(live.velocity_frame(0, 20)) == [5, 0, 2, 13, 2, 0, 0, 20, 0]          # right
    assert payload(live.velocity_frame(-20, 0))[6] == 236                                  # backward: -20 as a byte
    assert payload(live.velocity_frame(0, -10))[7] == 246                                  # left
    assert payload(live.velocity_frame()) == [5, 0, 2, 13, 2, 0, 0, 0, 0]                  # stop
    assert payload(live.velocity3_frame(10, -10, 5)) == [5, 0, 2, 13, 6, 0, 10, 246, 5]
    assert live.stop_motion_frame() == live.velocity3_frame(0, 0, 0)


def test_yaw_and_height_layout():
    assert payload(live.yaw_frame(90)) == [3, 0, 2, 14, 0, 90, 0]
    assert payload(live.yaw_frame(180, clockwise=False)) == [3, 0, 2, 14, 1, 180, 0]
    assert payload(live.height_frame(110)) == [7, 0, 2, 12, 2, 0, 0, 0, 0, 110, 0]
    assert payload(live.height_frame(150))[-2:] == [150, 0]


def test_length_byte_counts_the_data():
    for fr in (live.calibrate_frame(), live.takeoff_frame(), live.velocity_frame(5, 5), live.yaw_frame(10),
               live.height_frame(60)):
        body = payload(fr)
        assert body[0] == len(body) - 4 and body[1] == 0


def test_parser_reads_the_frames_back():
    buf = bytearray(live.velocity_frame(12, -3) + live.yaw_frame(45))
    got = list(p.parse_frames(buf))
    assert got == [p.Frame(2, 13, bytes([2, 0, 12, 253, 0])), p.Frame(2, 14, bytes([0, 45, 0]))]


@pytest.mark.parametrize("args", [(31, 0), (0, -31), (100, 100), (1.5, 0), (True, 0), ("10", 0), (None, 0)])
def test_speed_is_limited_to_30_cm_s_and_must_be_an_integer(args):
    with pytest.raises(SafetyError):
        live.velocity_frame(*args)
    live.velocity_frame(30, -30)                                                           # the limit itself passes


def test_vertical_speed_limit():
    with pytest.raises(SafetyError):
        live.velocity3_frame(0, 0, 31)


@pytest.mark.parametrize("deg", [-1, 181, 90.5, "90", True, None])
def test_yaw_range(deg):
    with pytest.raises(SafetyError):
        live.yaw_frame(deg)


@pytest.mark.parametrize("z", [19, 201, 100.5, "100", True])
def test_height_range(z):
    with pytest.raises(SafetyError):
        live.height_frame(z)
    with pytest.raises(SafetyError):
        live.height_frame(160, max_height_cm=150)                                          # the caller's limit wins
    live.height_frame(20)
    live.height_frame(200)


def test_module_never_opens_a_socket():
    import inspect
    src = inspect.getsource(live)
    assert "socket" not in src.replace("never touch the network", "") and "send(" not in src
