"""Mission step packing, as LiteBee Go packs formation steps.

Times are CUMULATIVE, in 0.1 s units, u16 little endian; heights are cm, u16.
One step frame: payload [19,0,3,2] + [total,0,index,0,t_lo,t_hi,cmd] + 12 data
bytes. The drone reports a checksum (telemetry bytes 8-9) that must equal the
sum of the cmd bytes of the steps we sent.

Only step layouts proven on live drones are packed (calibrate, takeOff, moveZ,
autoLand, RGB, moveXY). moveXYZ / circle ids are known but their data layout
is NOT verified, so they are never packed.

moveXY (verified on live drones): data = u16 LE row_cm, u16 LE col_cm, 8 zero bytes,
absolute mat coordinates (cell = col + 12 * row, 40 cm cells); the first value is
the row axis (y), the second the column axis (x). t_end is the cumulative END time.
"""
import struct
from dataclasses import dataclass, field
from typing import List

from .protocol import frame

CMD_CALIBRATE, CMD_TAKEOFF, CMD_AUTOLAND = 0, 1, 2
CMD_MOVEXY, CMD_MOVEZ, CMD_MOVEXYZ, CMD_CIRCLE, CMD_RGB = 3, 5, 10, 12, 50

PROVEN_CMDS = frozenset({CMD_CALIBRATE, CMD_TAKEOFF, CMD_AUTOLAND, CMD_MOVEZ, CMD_RGB, CMD_MOVEXY, CMD_CIRCLE})

CELL_CM, GRID_W = 40, 12                 # QR mat: 12 x 12 cells of 40 cm, cell = col + 12 * row
GRID_CELLS = GRID_W * GRID_W
CMD_NAMES = {CMD_CALIBRATE: "calibrate", CMD_TAKEOFF: "takeOff", CMD_AUTOLAND: "autoLand",
             CMD_MOVEXY: "moveXY", CMD_MOVEZ: "moveZ", CMD_MOVEXYZ: "moveXYZ",
             CMD_CIRCLE: "circle", CMD_RGB: "RGB"}

COLORS = {"black": (0, 0, 0), "red": (255, 0, 0), "green": (0, 255, 0), "yellow": (255, 255, 0),
          "blue": (0, 0, 255), "purple": (255, 0, 255), "cyan": (0, 255, 255), "white": (255, 255, 255)}
COLOR_BY_INDEX = ["black", "red", "green", "yellow", "blue", "purple", "cyan", "white"]  # RGB block 0-7

# Hard limits for anything that can fly (mirrored by safety.py).
# MAX_HEIGHT_CM is the DEFAULT height limit; the user may set another one between
# MIN_TAKEOFF_CM (floor) and HARD_MAX_HEIGHT_CM (ceiling) with resolve_max_height().
# The ceiling is a constant: nothing in the UI or the CLI can exceed it.
MAX_HEIGHT_CM, MAX_HOVER_S, MIN_TAKEOFF_CM = 150, 10, 20
DEFAULT_MAX_HEIGHT_CM = MAX_HEIGHT_CM
HARD_MAX_HEIGHT_CM = 200


def resolve_max_height(value=None) -> int:
    """The active height limit in cm: the default for None, else `value` if it is a whole
    number in [MIN_TAKEOFF_CM, HARD_MAX_HEIGHT_CM]. Raises SafetyError otherwise."""
    if value is None:
        return DEFAULT_MAX_HEIGHT_CM
    try:
        ok = not isinstance(value, bool) and float(value) == int(value)
    except (TypeError, ValueError, OverflowError):
        ok = False
    if not ok or not MIN_TAKEOFF_CM <= int(value) <= HARD_MAX_HEIGHT_CM:
        from .safety import SafetyError
        raise SafetyError(f"Лимит высоты {value} см вне допустимых пределов "
                          f"({MIN_TAKEOFF_CM}-{HARD_MAX_HEIGHT_CM} см)")
    return int(value)


@dataclass
class MissionStep:
    cmd: int
    t_end: int            # cumulative end time, 0.1 s units
    data: bytes           # 12 data bytes

    def __post_init__(self):
        self.data = bytes(self.data)
        if len(self.data) != 12:
            raise ValueError("step data must be 12 bytes")
        if not 0 <= self.t_end <= 0xFFFF:
            raise ValueError("cumulative time does not fit u16 (max 6553.5 s)")

    @property
    def height_cm(self):
        """Target height for takeOff/moveZ steps, else None."""
        if self.cmd in (CMD_TAKEOFF, CMD_MOVEZ):
            return struct.unpack_from("<H", self.data, 0)[0]
        return None

    @property
    def xy_cm(self):
        """(x, y) target of a moveXY step in cm on the mat, else None."""
        if self.cmd == CMD_MOVEXY:
            y, x = struct.unpack_from("<HH", self.data, 0)
            return x, y
        return None

    @property
    def cell(self):
        """Mat cell of a moveXY step, or None when it is not one or the target is not a cell centre."""
        xy = self.xy_cm
        if xy is None or xy[0] % CELL_CM or xy[1] % CELL_CM:
            return None
        col, row = xy[0] // CELL_CM, xy[1] // CELL_CM
        return col + GRID_W * row if col < GRID_W and row < GRID_W else None


@dataclass
class Mission:
    steps: List[MissionStep] = field(default_factory=list)

    def frames(self) -> List[bytes]:
        total = len(self.steps)
        out = []
        for i, s in enumerate(self.steps, 1):
            step = [total, 0, i, 0, s.t_end & 255, s.t_end >> 8, s.cmd, *s.data]
            assert len(step) == 19
            out.append(frame([19, 0, 3, 2, *step]))
        return out

    @property
    def checksum(self) -> int:
        """Value the drone must report back (sum of cmd bytes, u16)."""
        return sum(s.cmd for s in self.steps) & 0xFFFF

    @property
    def total_seconds(self) -> float:
        return (self.steps[-1].t_end if self.steps else 0) / 10

    @property
    def cmds(self):
        return {s.cmd for s in self.steps}

    @property
    def moves(self) -> List[MissionStep]:
        """The moveXY steps (cell moves) in order."""
        return [s for s in self.steps if s.cmd == CMD_MOVEXY]

    @property
    def has_moves(self) -> bool:
        return bool(self.moves)

    @property
    def first_move_xy(self):
        """(x, y) cm of the first moveXY step, else None."""
        return self.moves[0].xy_cm if self.moves else None

    @property
    def can_fly(self) -> bool:
        """Anything other than pure LED steps may spin the motors."""
        return bool(self.steps) and self.cmds != {CMD_RGB}

    @property
    def max_height_cm(self) -> int:
        return max((s.height_cm or 0 for s in self.steps), default=0)

    @property
    def max_hover_s(self) -> float:
        """Longest moveZ step that keeps the current height (a hover)."""
        longest, z, prev_t = 0.0, 0, 0
        for s in self.steps:
            dur = (s.t_end - prev_t) / 10
            if s.cmd == CMD_MOVEZ and s.height_cm == z:
                longest = max(longest, dur)
            if s.height_cm is not None:
                z = s.height_cm
            elif s.cmd == CMD_AUTOLAND:
                z = 0
            prev_t = s.t_end
        return longest


def ticks(seconds: float) -> int:
    return int(round(seconds * 10))


def z_data(height_cm) -> bytes:
    return struct.pack("<H", int(height_cm)) + bytes(10)


def xy_data(cell) -> bytes:
    """moveXY step data for a mat cell (0..143): <HH row_cm, col_cm> + 8 zero bytes."""
    if isinstance(cell, bool) or int(cell) != cell or not 0 <= cell < GRID_CELLS:
        raise ValueError(f"Клетка {cell} вне коврика 0-{GRID_CELLS - 1}")
    row, col = divmod(int(cell), GRID_W)
    return struct.pack("<HH", CELL_CM * row, CELL_CM * col) + bytes(8)


def cell_from_xy(x, y):
    """Cell under a position in cm (round(x/40) + 12 * round(y/40)), None when off the mat."""
    col, row = round(x / CELL_CM), round(y / CELL_CM)
    return col + GRID_W * row if 0 <= col < GRID_W and 0 <= row < GRID_W else None


def rgb_data(r, g, b) -> bytes:
    """RGB step data; note the wire order is g, r, b."""
    return bytes([5, 0, 2, 255, g, r, b, 0, 0, 0, 0, 0])


def rgb_mission(r, g, b) -> Mission:
    """The single-RGB-step mission of drone_color.py (checksum 50)."""
    return Mission([MissionStep(CMD_RGB, 0, rgb_data(r, g, b))])


def hop_mission(height_cm, hover_s, calibrate_s=5, takeoff_s=5, max_height_cm=None) -> Mission:
    """calibrate -> takeOff -> moveZ (hover) -> autoLand, as drone_hop.py.

    `max_height_cm` is the active height limit (default 150, never above the 200 cm ceiling)."""
    limit = resolve_max_height(max_height_cm)
    if not (MIN_TAKEOFF_CM <= height_cm <= limit and 0 <= hover_s <= MAX_HOVER_S):
        from .safety import SafetyError
        raise SafetyError(f"Высота {height_cm} см или зависание {hover_s} с вне лимитов "
                          f"({MIN_TAKEOFF_CM}-{limit} см, зависание до {MAX_HOVER_S} с)")
    now, steps = 0, []
    for cmd, secs, data in (
        (CMD_CALIBRATE, calibrate_s, bytes(12)),
        (CMD_TAKEOFF, takeoff_s, z_data(height_cm)),
        (CMD_MOVEZ, hover_s, z_data(height_cm)),
        (CMD_AUTOLAND, 0, bytes(12)),
    ):
        now += ticks(secs)
        steps.append(MissionStep(cmd, now, data))
    return Mission(steps)
