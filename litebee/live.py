"""Immediate ("live") command frames, as LiteBee Go builds them for the Wing extensions.

Source: the Wing extension class in LiteBee Go's gui/lib.min.js (docs/PROTOCOL_SINGLE.md, "Живые команды").
These are NOT mission steps: the drone reacts at once. The app sends them to Wing drones over the USB remote;
nobody in LiteBee Go sends them to an FM drone over Wi-Fi, so whether a formation drone accepts them is NOT
verified. Nothing in this package calls these builders: they only build bytes, they never touch the network.

Frame: 0xFA + [len, 0, group, id, data...] + CRC-16, the same layout as every frame in protocol.py
(`len` counts the data bytes). Signed speeds are one byte each, two's complement, like JavaScript's Buffer.from.
"""
import struct

from .mission import HARD_MAX_HEIGHT_CM, MIN_TAKEOFF_CM
from .protocol import frame
from .safety import SafetyError

GROUP = 2
ID_COMMAND, ID_MODE, ID_POSITION, ID_VELOCITY, ID_YAW = 3, 11, 12, 13, 14

# Immediate command codes inside id 3: [9, 0, 2, 3, code, 0 x 8]
CMD_HOLD, CMD_TAKEOFF, CMD_LAND = 2, 3, 4

# Speed limit of the builders (cm/s). Deliberately low: these frames act at once and are unverified on FM drones.
MAX_LIVE_SPEED_CM_S = 30
MAX_YAW_DEG = 180


def _command(code: int) -> bytes:
    return frame([9, 0, GROUP, ID_COMMAND, code, 0, 0, 0, 0, 0, 0, 0, 0])


def calibrate_frame() -> bytes:
    return frame([2, 0, GROUP, 2, 0, 0])


def takeoff_frame() -> bytes:
    return _command(CMD_TAKEOFF)


def hold_frame() -> bytes:
    """Hover where the drone is ("posHold")."""
    return _command(CMD_HOLD)


def land_frame() -> bytes:
    """Same bytes as protocol.ALL_AUTOLAND."""
    return _command(CMD_LAND)


def _speed(value, name) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != int(value):
        raise SafetyError(f"{name}: скорость должна быть целым числом см/с, получено {value!r}")
    value = int(value)
    if abs(value) > MAX_LIVE_SPEED_CM_S:
        raise SafetyError(f"{name}: {value} см/с больше предела {MAX_LIVE_SPEED_CM_S} см/с")
    return value & 0xFF


def velocity_frame(forward_cm_s=0, right_cm_s=0) -> bytes:
    """"setDir": speed forward (negative = backward) and to the right (negative = left), cm/s.
    One frame sets the speed; send velocity_frame(0, 0) to stop."""
    return frame([5, 0, GROUP, ID_VELOCITY, 2, 0, _speed(forward_cm_s, "вперёд"), _speed(right_cm_s, "вправо"), 0])


def velocity3_frame(forward_cm_s=0, right_cm_s=0, up_cm_s=0) -> bytes:
    """"setVXYZ": forward, right and up speeds (negative = backward, left, down), cm/s."""
    return frame([5, 0, GROUP, ID_VELOCITY, 6, 0, _speed(forward_cm_s, "вперёд"),
                  _speed(right_cm_s, "вправо"), _speed(up_cm_s, "вверх")])


def stop_motion_frame() -> bytes:
    return velocity3_frame(0, 0, 0)


def yaw_frame(degrees: int, clockwise: bool = True) -> bytes:
    """"setYaw": turn the nose by `degrees` (0-180). Direction byte 0 = clockwise, 1 = counter-clockwise."""
    if isinstance(degrees, bool) or not isinstance(degrees, int) or not 0 <= degrees <= MAX_YAW_DEG:
        raise SafetyError(f"Угол поворота должен быть целым от 0 до {MAX_YAW_DEG}, получено {degrees!r}")
    return frame([3, 0, GROUP, ID_YAW, 0 if clockwise else 1, *struct.pack("<H", degrees)])


def height_frame(z_cm: int, max_height_cm: int = HARD_MAX_HEIGHT_CM) -> bytes:
    """"setHigh": fly to the height z (cm)."""
    if isinstance(z_cm, bool) or not isinstance(z_cm, int) or not MIN_TAKEOFF_CM <= z_cm <= max_height_cm:
        raise SafetyError(f"Высота должна быть целым от {MIN_TAKEOFF_CM} до {max_height_cm} см, получено {z_cm!r}")
    return frame([7, 0, GROUP, ID_POSITION, 2, 0, 0, 0, 0, *struct.pack("<h", z_cm)])
