"""Describe a LiteBee Wing formation show in Python and check it offline.

Mirrors the blocks of the LiteBee Go "litebeeWingFormation" extension:
position is a QR-mat cell number (code = col + 12 * row, 40 cm cells), heights
are in cm, step durations in seconds. Nothing here talks to a drone.
"""
from dataclasses import dataclass, field
from itertools import combinations
from math import atan2, cos, dist, pi, sin

CELL_CM = 40
GRID_W = 12
LAND_SECONDS = 3.0  # not in the project files; assumption


def cell_xy(code):
    """QR cell number -> (x, y) in cm (cell centre order: col, row)."""
    return (code % GRID_W) * CELL_CM, (code // GRID_W) * CELL_CM


@dataclass
class Step:
    kind: str
    seconds: float
    args: dict = field(default_factory=dict)


class Drone:
    def __init__(self, number):
        self.number = number
        self.steps = []

    def _add(self, kind, seconds, **args):
        self.steps.append(Step(kind, float(seconds), args))
        return self

    def calibrate(self, seconds):
        return self._add("calibrate", seconds)

    def takeoff(self, z, seconds):
        return self._add("takeoff", seconds, z=float(z))

    def rgb(self, color):
        return self._add("rgb", 0, color=color)

    def code(self, cell, seconds):
        return self._add("code", seconds, cell=int(cell))

    def code_z(self, cell, z, seconds):
        return self._add("code_z", seconds, cell=int(cell), z=float(z))

    def set_z(self, z, seconds):
        return self._add("set_z", seconds, z=float(z))

    def circle(self, count, cell1, cell2, seconds, rotate="cw"):
        return self._add("circle", seconds, count=int(count), cell1=int(cell1),
                         cell2=int(cell2), rotate=rotate)

    def land(self):
        return self._add("land", LAND_SECONDS)

    @property
    def duration(self):
        return sum(s.seconds for s in self.steps)

    def path(self):
        """Piecewise-linear [(t0, t1, (x0,y0,z0), (x1,y1,z1), kind)] segments.

        Start position is unknown in the project files, so the drone is
        assumed to begin under its first target cell.
        """
        first = next((s for s in self.steps if "cell" in s.args), None)
        x, y = cell_xy(first.args["cell"]) if first else (0.0, 0.0)
        z, t, out = 0.0, 0.0, []
        for s in self.steps:
            t1, nx, ny, nz = t + s.seconds, x, y, z
            if s.kind in ("takeoff", "set_z"):
                nz = s.args["z"]
            elif s.kind == "code":
                nx, ny = cell_xy(s.args["cell"])
            elif s.kind == "code_z":
                (nx, ny), nz = cell_xy(s.args["cell"]), s.args["z"]
            elif s.kind == "land":
                nz = 0.0
            elif s.kind == "circle":
                # Per the app's own docs: the centre is the midpoint of the two
                # cells and `count` is in half turns, so a drone orbits through
                # its current position. Which way "cw" turns on the mat is a guess.
                (ax, ay), (bx, by) = cell_xy(s.args["cell1"]), cell_xy(s.args["cell2"])
                cx, cy = (ax + bx) / 2, (ay + by) / 2
                r, a_start = dist((x, y), (cx, cy)), atan2(y - cy, x - cx)
                sweep = (-1 if s.args["rotate"] == "cw" else 1) * pi * s.args["count"]
                n = max(8, int(s.seconds * 10))
                for i in range(n):
                    a0, a1 = a_start + sweep * i / n, a_start + sweep * (i + 1) / n
                    out.append((t + s.seconds * i / n, t + s.seconds * (i + 1) / n,
                                (cx + r * cos(a0), cy + r * sin(a0), z),
                                (cx + r * cos(a1), cy + r * sin(a1), z), "circle"))
                x, y = cx + r * cos(a_start + sweep), cy + r * sin(a_start + sweep)
                t = t1
                continue
            out.append((t, t1, (x, y, z), (nx, ny, nz), s.kind))
            x, y, z, t = nx, ny, nz, t1
        return out

    def position_at(self, t, path=None):
        path = path or self.path()
        for t0, t1, p0, p1, _ in path:
            if t0 <= t <= t1:
                k = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                return tuple(a + (b - a) * k for a, b in zip(p0, p1))
        return path[-1][3] if path else (0, 0, 0)


class Show:
    def __init__(self, name):
        self.name = name
        self.drones = {}

    def drone(self, number):
        return self.drones.setdefault(number, Drone(number))

    def closest_approaches(self, step=0.1, top=5):
        """Smallest 3D distance (cm) between each drone pair; worst `top` pairs."""
        paths = {n: d.path() for n, d in self.drones.items()}
        end = max(d.duration for d in self.drones.values())
        best = {}
        t = 0.0
        while t <= end:
            pos = {n: self.drones[n].position_at(t, paths[n]) for n in self.drones}
            for a, b in combinations(sorted(pos), 2):
                d = dist(pos[a], pos[b])
                if d < best.get((a, b), (1e9, 0))[0]:
                    best[(a, b)] = (d, t)
            t += step
        return sorted(((d, t, a, b) for (a, b), (d, t) in best.items()))[:top]

    def report(self):
        lines = [f"Show {self.name!r}: {len(self.drones)} drones"]
        for n, d in sorted(self.drones.items()):
            lines.append(f"  drone {n:>2}: {len(d.steps):>3} steps, {d.duration:6.1f} s")
        lines.append("  closest pairs (cm), model assumptions apply:")
        for d, t, a, b in self.closest_approaches():
            lines.append(f"    {a:>2}-{b:<2} {d:6.1f} cm at t={t:5.1f} s")
        return "\n".join(lines)
