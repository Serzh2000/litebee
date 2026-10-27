"""Describe a LiteBee Wing formation show in Python and check it offline.

Mirrors the blocks of the LiteBee Go "litebeeWingFormation" extension:
position is a QR-mat cell number (code = col + 12 * row, 40 cm cells), heights
are in cm, step durations in seconds. Nothing here talks to a drone.

Model assumptions (they are guesses, not measured):
  * the start position is not in the project files; a drone is assumed to
    begin under its first target cell, on the ground;
  * landing takes LAND_SECONDS (3 s) in the simulation (in an uploaded mission
    the autoLand step adds no time, as in drone_hop.py);
  * circle: the centre is the midpoint of the two cells, `count` is in half
    turns, and which way "cw" turns on the mat is a guess;
  * every move is a straight line at constant speed.
"""
import sys
from bisect import bisect_left
from dataclasses import dataclass, field
from itertools import combinations
from math import atan2, cos, dist, pi, sin
from typing import List, Optional

from .mission import (CELL_CM, CMD_AUTOLAND, CMD_CALIBRATE, CMD_MOVEXY, CMD_RGB, CMD_TAKEOFF, CMD_MOVEZ,
                      COLOR_BY_INDEX, COLORS, GRID_CELLS, GRID_W, Mission, MissionStep, rgb_data, ticks,
                      xy_data, z_data)

LAND_SECONDS = 3.0  # not in the project files; assumption
MAX_SHOW_STEPS = 10000  # a show with more steps is refused (runaway loop in the show code)


class ShowTooLarge(ValueError):
    """The show has more than MAX_SHOW_STEPS steps."""

    def __init__(self, limit=MAX_SHOW_STEPS):
        super().__init__(f"Шоу содержит больше {limit} шагов. Проверьте циклы в коде")


class UploadUnsupported(Exception):
    """The drone's program contains steps whose wire layout is not verified on a live drone."""


def cell_xy(code):
    """QR cell number -> (x, y) in cm (cell centre order: col, row)."""
    return (code % GRID_W) * CELL_CM, (code // GRID_W) * CELL_CM


def _color(color):
    """Accept a colour name, an index 0-7 (LiteBee Go RGB block) or an (r, g, b) tuple."""
    if isinstance(color, str):
        if color not in COLORS:
            raise ValueError(f"Неизвестный цвет {color!r}. Доступны: {', '.join(COLORS)}")
        return color, COLORS[color]
    if isinstance(color, int):
        if not 0 <= color < len(COLOR_BY_INDEX):
            raise ValueError("Номер цвета должен быть от 0 до 7")
        name = COLOR_BY_INDEX[color]
        return name, COLORS[name]
    r, g, b = (int(v) for v in color)
    if not all(0 <= v <= 255 for v in (r, g, b)):
        raise ValueError("Компоненты цвета должны быть от 0 до 255")
    return f"#{r:02x}{g:02x}{b:02x}", (r, g, b)


def _caller_line():
    """Source line of the user's call into the DSL (first frame outside this module)."""
    f = sys._getframe(1)
    while f and f.f_globals.get("__name__") == __name__:
        f = f.f_back
    return f.f_lineno if f else None


@dataclass
class Step:
    kind: str
    seconds: float
    args: dict = field(default_factory=dict)
    line: Optional[int] = None


class Drone:
    def __init__(self, number):
        self.number = number
        self.steps: List[Step] = []

    def _add(self, kind, seconds, **args):
        if float(seconds) < 0:
            raise ValueError("Время шага не может быть отрицательным")
        if len(self.steps) >= MAX_SHOW_STEPS:
            raise ShowTooLarge()
        self.steps.append(Step(kind, float(seconds), args, _caller_line()))
        return self

    def calibrate(self, seconds):
        return self._add("calibrate", seconds)

    def takeoff(self, z, seconds):
        return self._add("takeoff", seconds, z=float(z))

    def rgb(self, color):
        name, rgb = _color(color)
        return self._add("rgb", 0, color=name, rgb=rgb)

    def rgb_value(self, r, g, b):
        return self.rgb((r, g, b))

    def code(self, cell, seconds):
        return self._add("code", seconds, cell=int(cell))

    def code_s(self, cells, seconds):
        """Move through several cells; `cells` is a list or a '12 23 27' string; time is split evenly."""
        cells = [int(c) for c in (cells.split() if isinstance(cells, str) else cells)]
        if not cells:
            raise ValueError("Список клеток пуст")
        for c in cells:
            self._add("code", float(seconds) / len(cells), cell=c)
        return self

    def code_z(self, cell, z, seconds):
        return self._add("code_z", seconds, cell=int(cell), z=float(z))

    def set_z(self, z, seconds):
        return self._add("set_z", seconds, z=float(z))

    def circle(self, count, cell1, cell2, seconds, rotate="cw"):
        if rotate in (0, 1):
            rotate = "cw" if rotate == 0 else "ccw"
        return self._add("circle", seconds, count=int(count), cell1=int(cell1),
                         cell2=int(cell2), rotate=rotate)

    def circle_z(self, cell1, cell2, dz, seconds, rotate="cw"):
        """Half turn while rising by dz cm."""
        if rotate in (0, 1):
            rotate = "cw" if rotate == 0 else "ccw"
        return self._add("circle_z", seconds, cell1=int(cell1), cell2=int(cell2),
                         dz=float(dz), rotate=rotate)

    def land(self):
        return self._add("land", LAND_SECONDS)

    @property
    def duration(self):
        return sum(s.seconds for s in self.steps)

    def path(self):
        """Piecewise-linear [(t0, t1, (x0,y0,z0), (x1,y1,z1), kind, step_index)] segments."""
        first = next((s for s in self.steps if "cell" in s.args), None)
        x, y = cell_xy(first.args["cell"]) if first else (0.0, 0.0)
        z, t, out = 0.0, 0.0, []
        for idx, s in enumerate(self.steps):
            t1, nx, ny, nz = t + s.seconds, x, y, z
            if s.kind in ("takeoff", "set_z"):
                nz = s.args["z"]
            elif s.kind == "code":
                nx, ny = cell_xy(s.args["cell"])
            elif s.kind == "code_z":
                (nx, ny), nz = cell_xy(s.args["cell"]), s.args["z"]
            elif s.kind == "land":
                nz = 0.0
            elif s.kind in ("circle", "circle_z"):
                # Per the app's own docs: the centre is the midpoint of the two
                # cells and `count` is in half turns, so a drone orbits through
                # its current position. Which way "cw" turns on the mat is a guess.
                (ax, ay), (bx, by) = cell_xy(s.args["cell1"]), cell_xy(s.args["cell2"])
                cx, cy = (ax + bx) / 2, (ay + by) / 2
                r, a_start = dist((x, y), (cx, cy)), atan2(y - cy, x - cx)
                turns = s.args.get("count", 1)
                sweep = (-1 if s.args["rotate"] == "cw" else 1) * pi * turns
                dz = s.args.get("dz", 0.0)
                n = max(8, int(s.seconds * 10))
                for i in range(n):
                    a0, a1 = a_start + sweep * i / n, a_start + sweep * (i + 1) / n
                    out.append((t + s.seconds * i / n, t + s.seconds * (i + 1) / n,
                                (cx + r * cos(a0), cy + r * sin(a0), z + dz * i / n),
                                (cx + r * cos(a1), cy + r * sin(a1), z + dz * (i + 1) / n),
                                s.kind, idx))
                x, y = cx + r * cos(a_start + sweep), cy + r * sin(a_start + sweep)
                z += dz
                t = t1
                continue
            out.append((t, t1, (x, y, z), (nx, ny, nz), s.kind, idx))
            x, y, z, t = nx, ny, nz, t1
        return out

    def position_at(self, t, path=None):
        path = path or self.path()
        return _position(path, [seg[1] for seg in path], t)

    def step_at(self, t):
        """The Step being executed at time t (None for an empty program)."""
        path = self.path()
        if not path:
            return None
        i = bisect_left([seg[1] for seg in path], t)
        return self.steps[path[min(i, len(path) - 1)][5]]

    def color_at(self, t):
        """(name, (r, g, b)) of the LED at time t; the LED is off until the first rgb step."""
        cur = ("black", (0, 0, 0))
        now = 0.0
        for s in self.steps:
            if now > t:
                break
            if s.kind == "rgb":
                cur = (s.args["color"], s.args["rgb"])
            now += s.seconds
        return cur


def _position(path, ends, t):
    if not path:
        return (0, 0, 0)
    i = bisect_left(ends, t)
    if i >= len(path):
        return path[-1][3]
    t0, t1, p0, p1 = path[i][:4]
    k = 0 if t1 == t0 else (t - t0) / (t1 - t0)
    return tuple(a + (b - a) * k for a, b in zip(p0, p1))


class Show:
    def __init__(self, name):
        self.name = name
        self.drones = {}

    def drone(self, number):
        return self.drones.setdefault(number, Drone(number))

    @property
    def duration(self):
        return max((d.duration for d in self.drones.values()), default=0.0)

    @property
    def step_count(self):
        return sum(len(d.steps) for d in self.drones.values())

    def paths(self):
        return {n: d.path() for n, d in self.drones.items()}

    def positions_at(self, t, paths=None):
        paths = paths or self.paths()
        return {n: _position(p, [s[1] for s in p], t) for n, p in paths.items()}

    def closest_approaches(self, step=0.1, top=5):
        """Smallest 3D distance (cm) between each drone pair; worst `top` pairs."""
        paths = self.paths()
        ends = {n: [s[1] for s in p] for n, p in paths.items()}
        end = self.duration
        best = {}
        t = 0.0
        while t <= end:
            pos = {n: _position(paths[n], ends[n], t) for n in paths}
            for a, b in combinations(sorted(pos), 2):
                d = dist(pos[a], pos[b])
                if d < best.get((a, b), (1e9, 0))[0]:
                    best[(a, b)] = (d, t)
            t += step
        return sorted(((d, t, a, b) for (a, b), (d, t) in best.items()))[:top]

    def report(self):
        lines = [f"Шоу {self.name!r}: дронов {len(self.drones)}"]
        for n, d in sorted(self.drones.items()):
            lines.append(f"  дрон {n:>2}: {len(d.steps):>3} шагов, {d.duration:6.1f} с")
        lines.append("  ближайшие пары (см), модель приблизительная:")
        for d, t, a, b in self.closest_approaches():
            lines.append(f"    {a:>2}-{b:<2} {d:6.1f} см на t={t:5.1f} с")
        return "\n".join(lines)


def drone_to_mission(drone: Drone) -> Mission:
    """Compile a drone's program into a mission, using only step layouts proven on live drones.

    `code` (cell move) becomes a moveXY step. Raises UploadUnsupported for code_z, circle and
    circle_z (the wire layout of moveXYZ / circle has not been verified), for a cell outside the
    mat and for more steps than the one-byte step counter of the protocol can number.
    """
    now, steps = 0, []
    for s in drone.steps:
        if s.kind == "calibrate":
            now += ticks(s.seconds)
            steps.append(MissionStep(CMD_CALIBRATE, now, bytes(12)))
        elif s.kind == "takeoff":
            now += ticks(s.seconds)
            steps.append(MissionStep(CMD_TAKEOFF, now, z_data(s.args["z"])))
        elif s.kind == "set_z":
            now += ticks(s.seconds)
            steps.append(MissionStep(CMD_MOVEZ, now, z_data(s.args["z"])))
        elif s.kind == "rgb":
            r, g, b = s.args["rgb"]
            steps.append(MissionStep(CMD_RGB, now, rgb_data(r, g, b)))
        elif s.kind == "code":
            if not 0 <= s.args["cell"] < GRID_CELLS:
                raise UploadUnsupported(f"Клетка {s.args['cell']} (строка {s.line}) вне коврика 0-{GRID_CELLS - 1}")
            now += ticks(s.seconds)
            steps.append(MissionStep(CMD_MOVEXY, now, xy_data(s.args["cell"])))
        elif s.kind == "land":
            steps.append(MissionStep(CMD_AUTOLAND, now, bytes(12)))
        else:
            raise UploadUnsupported(
                f"Шаг {s.kind!r} (строка {s.line}) пока нельзя загрузить: его формат не проверен на живом дроне "
                "(загружаются калибровка, взлёт, высота, посадка, цвет и движение по клеткам code)")
    if not steps:
        raise UploadUnsupported("У дрона нет шагов")
    if len(steps) > 255:
        raise UploadUnsupported(f"У дрона {len(steps)} шагов: в миссию помещается не больше 255")
    return Mission(steps)
