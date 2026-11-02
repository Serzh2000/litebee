"""Generates the gallery of example shows: Python files in shows/gallery/, their JSON in desktop/shows/gallery/ and
the catalog (tags, drones, seconds) the new-project wizard filters.

    python -X utf8 tools/gen_gallery.py

Every show is built through the real Show API and checked with check_show (no error and no warning: drones keep 60 cm
apart even on the ground, no move is faster than 100 cm/s, heights stay under 150 cm). A candidate that fails the
check is thrown away, so everything that is written passes. The result is deterministic (seeded).
"""
import json
import math
import os
import random
import sys
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from litebee.loader import load_show  # noqa: E402
from litebee.safety import check_show  # noqa: E402
from litebee.show import Show  # noqa: E402

OUT_PY = os.path.join(ROOT, "shows", "gallery")
OUT_JSON = os.path.join(ROOT, "desktop", "shows", "gallery")
CATALOG = os.path.join(ROOT, "desktop", "src", "renderer", "src", "data", "catalog.json")

LEVELS = [60, 85, 105, 130, 150]
PALETTE = ["red", "yellow", "green", "cyan", "blue", "purple", "white"]
GRID_W = 12


def dr(n):
    """'1 дрон', '2 дрона', '5 дронов'."""
    word = 'дронов' if n % 100 in range(11, 15) else {1: 'дрон', 2: 'дрона', 3: 'дрона', 4: 'дрона'}.get(n % 10, 'дронов')
    return f"{n} {word}"


def dr_en(n):
    return f"{n} drone" + ("" if n == 1 else "s")


SHAPE_EN = {
    "line": "Line", "column": "Column", "diag": "Diagonal", "anti": "Anti-diagonal", "vee": "Chevron", "arch": "Arch",
    "zigzag": "Zigzag", "stairs": "Stairs", "ring": "Ring", "square": "Frame", "block": "Block", "plus": "Plus", "xcross": "X",
    "diamond": "Diamond", "triangle": "Triangle", "ell": "Letter L", "tee": "Letter T", "twolines": "Two rows",
}
PATTERN_EN = {
    "chase": "Running light", "rainbow": "Rainbow round", "pulse": "Common pulse", "alternate": "Every other one",
    "sweep": "Wave of colour", "counter": "Binary counter", "police": "Flasher", "traffic": "Traffic light",
    "twinkle": "Twinkling", "breathe": "Breathing",
}
PATH_EN = {"Строчками": "row by row", "Столбцами": "column by column", "Рамкой": "round the frame", "Спиралью": "in a spiral", "Диагоналями": "along the diagonals"}


def cell(x, y):
    return x + GRID_W * y


# ---------------------------------------------------------------------------------------------------------------
# shapes on a unit lattice, scaled by the spacing and centred in the area

SHAPE_NAMES = {
    "line": "Линия", "column": "Колонна", "diag": "Диагональ", "anti": "Обратная диагональ", "vee": "Галочка",
    "arch": "Арка", "zigzag": "Зигзаг", "stairs": "Лесенка", "ring": "Кольцо", "square": "Рамка", "block": "Блок",
    "plus": "Плюс", "xcross": "Икс", "diamond": "Ромб", "triangle": "Треугольник", "ell": "Буква Г", "tee": "Буква Т",
    "twolines": "Два ряда",
}


def shape_coords(name, n):
    if name == "line":
        return [(i, 0) for i in range(n)]
    if name == "column":
        return [(0, i) for i in range(n)]
    if name == "diag":
        return [(i, i) for i in range(n)]
    if name == "anti":
        return [(i, n - 1 - i) for i in range(n)]
    if name == "vee":
        return [(i, abs(2 * i - (n - 1)) // 2) for i in range(n)]
    if name == "arch":
        return [(i, (n - 1) // 2 - abs(2 * i - (n - 1)) // 2) for i in range(n)]
    if name == "zigzag":
        return [(i, i % 2) for i in range(n)]
    if name == "stairs":
        return [(i, i // 2) for i in range(n)]
    if name == "ring":
        r = 1 if n <= 4 else 2
        pts = [(round(r * math.cos(2 * math.pi * k / n)), round(r * math.sin(2 * math.pi * k / n))) for k in range(n)]
        return pts if len(set(pts)) == n else None
    if name == "square":
        sizes = {4: (2, 2), 6: (3, 2), 8: (3, 3), 10: (4, 3)}
        if n not in sizes:
            return None
        w, h = sizes[n]
        return [(x, y) for y in range(h) for x in range(w) if x in (0, w - 1) or y in (0, h - 1)]
    if name == "block":
        sizes = {4: (2, 2), 6: (3, 2), 8: (4, 2), 9: (3, 3), 10: (5, 2)}
        if n not in sizes:
            return None
        w, h = sizes[n]
        return [(x, y) for y in range(h) for x in range(w)]
    if name == "plus":
        arms = {5: 1, 9: 2}
        if n not in arms:
            return None
        a = arms[n]
        return [(0, 0)] + [(d * k, 0) for k in range(1, a + 1) for d in (1, -1)] + [(0, d * k) for k in range(1, a + 1) for d in (1, -1)]
    if name == "xcross":
        arms = {5: 1, 9: 2}
        if n not in arms:
            return None
        a = arms[n]
        return [(0, 0)] + [(dx * k, dy * k) for k in range(1, a + 1) for dx in (1, -1) for dy in (1, -1)]
    if name == "diamond":
        if n == 4:
            return [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if n == 8:
            return [(2, 0), (-2, 0), (0, 2), (0, -2), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        return None
    if name == "triangle":
        rows = {3: 2, 6: 3, 10: 4}
        if n not in rows:
            return None
        k = rows[n]
        return [(2 * i + (k - 1 - j), j) for j in range(k) for i in range(k - j)]
    if name == "ell":
        a = (n + 1) // 2
        return [(0, i) for i in range(a)] + [(j, 0) for j in range(1, n - a + 1)]
    if name == "tee":
        w = 3 if n < 7 else 5
        if n <= w:
            return None
        mid = w // 2
        return [(x, 0) for x in range(w)] + [(mid, -j) for j in range(1, n - w + 1)]
    if name == "twolines":
        a = (n + 1) // 2
        return [(i, 0) for i in range(a)] + [(i, 2) for i in range(n - a)]
    return None


def place(name, n, grid, spacing):
    """Cells of a shape for n drones inside a grid x grid area, or None when it does not fit."""
    pts = shape_coords(name, n)
    if not pts or len(set(pts)) != n:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w, h = (max(xs) - min(xs)) * spacing, (max(ys) - min(ys)) * spacing
    if w > grid - 1 or h > grid - 1:
        return None
    x0 = (grid - 1 - w) // 2 - min(xs) * spacing
    y0 = (grid - 1 - h) // 2 - min(ys) * spacing
    return [cell(x0 + p[0] * spacing, y0 + p[1] * spacing) for p in pts]


def slots(grid):
    """Start slots: a lattice two cells apart (80 cm), so that drones on the ground never come near each other."""
    return [cell(x, y) for y in range(0, grid, 2) for x in range(0, grid, 2)]


# ---------------------------------------------------------------------------------------------------------------
# a show is a title, a note and, for each drone, a list of (method, args) calls

class Plan:
    def __init__(self, sid, title, note, area, themes):
        self.sid, self.title, self.note, self.area, self.themes = sid, title, note, area, themes
        self.title_en = self.note_en = ""
        self.drones = []  # [(first cell, takeoff height, colour, ops, end cell)]

    def add(self, start, z, color, ops, end):
        self.drones.append({"start": start, "z": z, "color": color, "ops": ops, "end": end})

    def calls(self, i):
        d = self.drones[i]
        pre = [("calibrate", (5,)), ("takeoff", (d["z"], 5)), ("rgb", (d["color"],)), ("code", (d["start"], 1))]
        post = [("rgb", ("black",)), ("land_on", (d["end"],))]
        return pre + d["ops"] + post

    def build(self):
        show = Show(self.title)
        for i in range(len(self.drones)):
            drone = show.drone(i + 1)
            for method, args in self.calls(i):
                getattr(drone, method)(*args)
        return show

    def source(self):
        where = ("Для всего коврика 12 x 12 клеток." if self.area == "full" else
                 "Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.\n"
                 "# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.")
        lines = [f"# {self.note}", f"# {where}",
                 "# Перед загрузкой каждый дрон стоит на своей первой клетке (на карте она подсвечена), номер подтянется сам.",
                 "from litebee_show import Show", "", f"show = Show('{self.title}')", ""]
        for i in range(len(self.drones)):
            lines.append(f"d = show.drone({i + 1})")
            for method, args in self.calls(i):
                lines.append(f"d.{method}({', '.join(repr(a) for a in args)})")
            lines.append("")
        return "\n".join(lines)


def clean(plan):
    """True when the plan builds and the checks of the app find nothing at all (besides the info lines)."""
    try:
        show = plan.build()
    except Exception:
        return False
    return not [f for f in check_show(show, 60, max_height_cm=150) if f.level != "info"]


def xy(c):
    return (c % GRID_W) * 40, (c // GRID_W) * 40


def travel(a, b):
    (ax, ay), (bx, by) = xy(a), xy(b)
    return math.hypot(ax - bx, ay - by)


def seconds_for(dist, speed):
    return max(2, math.ceil(dist / speed))


COLOR_SCHEMES = ["same", "index", "alt", "column", "row"]


def colors_for(scheme, cells, k):
    """One colour per drone for the k-th formation."""
    n = len(cells)
    if scheme == "same":
        return [PALETTE[k % len(PALETTE)]] * n
    if scheme == "index":
        return [PALETTE[(i + k) % len(PALETTE)] for i in range(n)]
    if scheme == "alt":
        a, b = PALETTE[k % len(PALETTE)], PALETTE[(k + 3) % len(PALETTE)]
        return [a if i % 2 == 0 else b for i in range(n)]
    key = (lambda c: c % GRID_W) if scheme == "column" else (lambda c: c // GRID_W)
    order = sorted(set(key(c) for c in cells))
    return [PALETTE[(order.index(key(c)) + k) % len(PALETTE)] for c in cells]


# ---------------------------------------------------------------------------------------------------------------
# family 1: morph, the drones fly from the lattice into formations and back

def fast_ok(prev, target, heights, steps=12, need=62):
    """Cheap pre-check of one transition: every pair stays `need` cm apart (3D) all the way, drones at constant heights."""
    n = len(prev)
    pa = [xy(c) for c in prev]
    pb = [xy(c) for c in target]
    for s in range(steps + 1):
        f = s / steps
        pts = [(pa[i][0] + (pb[i][0] - pa[i][0]) * f, pa[i][1] + (pb[i][1] - pa[i][1]) * f, heights[i]) for i in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if math.dist(pts[i], pts[j]) < need:
                    return False
    return True


def assign(rng, prev, cells, greedy):
    """Which drone takes which slot of a formation: by nearest-first (short, rarely crossing) or at random."""
    n = len(prev)
    if not greedy:
        order = list(range(n))
        rng.shuffle(order)
        return [cells[order[i]] for i in range(n)]
    free = list(cells)
    result = [None] * n
    drones = list(range(n))
    rng.shuffle(drones)
    for i in drones:
        best = min(free, key=lambda c: travel(prev[i], c) + rng.random() * 30)
        result[i] = best
        free.remove(best)
    return result


def try_morph(sid, rng, area, n, shapes, spacings, scheme, speed, hold, rounds=1, tries=1500):
    grid = 6 if area == "quarter" else 12
    lattice = slots(grid)
    if n > len(lattice):
        return None
    layouts = []
    for name, sp in zip(shapes, spacings):
        cells = place(name, n, grid, sp)
        if cells is None:
            return None
        layouts.append(cells)
    layouts = layouts * rounds
    start = lattice[:n] if area == "quarter" else sorted(rng.sample(lattice, n))
    names = " → ".join(SHAPE_NAMES[s] for s in shapes)
    note = f"{dr(n)} летят из ровной сетки в строи: {names.lower()}" + (f", всё это {rounds} раза" if rounds > 1 else "") + " и возвращаются."
    names_en = " → ".join(SHAPE_EN[s] for s in shapes)
    note_en = f"{dr_en(n)} fly from an even grid into formations: {names_en.lower()}" + (f", all of it {rounds} times" if rounds > 1 else "") + " and return."
    for _ in range(tries):
        heights = [rng.choice(LEVELS) for _ in range(n)]
        if len(set(heights)) < 2:
            continue
        greedy = rng.random() < 0.6
        targets = []
        prev = list(start)
        ok = True
        for cells in layouts:
            target = assign(rng, prev, cells, greedy)
            if not fast_ok(prev, target, heights):
                ok = False
                break
            targets.append(target)
            prev = target
        if not ok or not fast_ok(prev, list(start), heights):
            continue
        targets.append(list(start))
        plan = Plan(sid, names + (" ×%d" % rounds if rounds > 1 else ""), note, area, ["Строи"])
        plan.title_en, plan.note_en = names_en + (" ×%d" % rounds if rounds > 1 else ""), note_en
        per = [[] for _ in range(n)]
        prev = list(start)
        for k, target in enumerate(targets):
            move = seconds_for(max(travel(prev[i], target[i]) for i in range(n)), speed)
            cols = colors_for(scheme, target, k)
            for i in range(n):
                per[i] += [("code", (target[i], move)), ("rgb", (cols[i],)), ("set_z", (heights[i], hold))]
            prev = target
        for i in range(n):
            plan.add(start[i], heights[i], PALETTE[i % len(PALETTE)], per[i], start[i])
        if clean(plan):
            return plan
    return None


# ---------------------------------------------------------------------------------------------------------------
# family 2: a ring turns, the drones step to the neighbour's place

def ring_cells(area):
    if area == "quarter":
        c = [(0, 0), (2, 0), (4, 0), (4, 2), (4, 4), (2, 4), (0, 4), (0, 2)]
    else:
        pts = [(x, 0) for x in range(0, 12, 2)] + [(10, y) for y in range(2, 12, 2)]
        pts += [(x, 10) for x in range(8, -1, -2)] + [(0, y) for y in range(8, 0, -2)]
        c = pts
    return [cell(x, y) for x, y in c]


def try_ring(sid, rng, area, n, step, laps, direction, scheme, move, with_centre):
    ring = ring_cells(area)
    m = len(ring)
    if n > m:
        return None
    gap = m // n
    idx = [i * gap for i in range(n)]
    plan = Plan(sid, "", "", area, ["Кольцо"])
    heights = [90 if i % 2 == 0 else 130 for i in range(n)]
    per = [[] for _ in range(n)]
    sign = 1 if direction == "cw" else -1
    steps = laps * (m // step)
    shift_each = step * sign
    for k in range(1, steps + 1):
        cells = []
        for i in range(n):
            cells.append(ring[(idx[i] + k * shift_each) % m])
        cols = colors_for(scheme, cells, k)
        for i in range(n):
            per[i] += [("code", (cells[i], move)), ("rgb", (cols[i],))]
    for i in range(n):
        end = ring[(idx[i] + steps * shift_each) % m]
        plan.add(ring[idx[i]], heights[i], PALETTE[i % len(PALETTE)], per[i], end)
    if with_centre:
        centre = cell(2, 2) if area == "quarter" else cell(6, 6)
        ops = []
        for k in range(laps * 2):
            ops += [("rgb", (PALETTE[(k + 2) % len(PALETTE)],)), ("set_z", (150, max(4, steps * move // (laps * 2))))]
        plan.add(centre, 150, "white", ops, centre)
    turn = "по часовой стрелке" if direction == "cw" else "против часовой стрелки"
    plan.title = f"Карусель: {dr(n)}, {turn}" + (", шаг через одного" if step == 2 else "")
    plan.title = plan.title.replace(", шаг через одного", " (прыжки)")
    plan.note = f"{dr(n)} по кольцу сдвигаются на {step} {'место' if step == 1 else 'места'} {turn}, {laps} {'круг' if laps == 1 else 'круга'}" + (", в центре висит ещё один" if with_centre else "") + "."
    turn_en = "clockwise" if direction == "cw" else "counter-clockwise"
    plan.title_en = f"Carousel: {dr_en(n)}, {turn_en}" + (" (jumps)" if step == 2 else "")
    plan.note_en = f"{dr_en(n)} shift {step} {'place' if step == 1 else 'places'} around the ring {turn_en}, {laps} {'lap' if laps == 1 else 'laps'}" + (", one more hangs in the centre" if with_centre else "") + "."
    return plan if clean(plan) else None


# ---------------------------------------------------------------------------------------------------------------
# family 2b: two rings turn at once, an outer one and an inner one, in the same or in opposite directions

def inner_ring_cells(area):
    if area == "quarter":  # the eight cells around the centre (2, 2): 40 cm apart, so the rings keep apart by height
        pts = [(1, 1), (2, 1), (3, 1), (3, 2), (3, 3), (2, 3), (1, 3), (1, 2)]
    else:                   # a lattice ring 80 cm apart inside the outer one
        pts = [(4, 4), (6, 4), (8, 4), (8, 6), (8, 8), (6, 8), (4, 8), (4, 6)]
    return [cell(x, y) for x, y in pts]


INNER_SUBSETS = {1: [0], 2: [0, 4], 3: [0, 3, 6], 4: [0, 2, 4, 6]}


def try_double_ring(sid, rng, area, n_out, n_in, o_out, o_in, dir_out, dir_in, step_in, laps, move, scheme):
    """All drones start and land on the lattice two cells apart; in the air they form an outer and an inner ring (the
    rings are kept apart by height) and turn, both the same way or against each other."""
    outer, inner = ring_cells(area), inner_ring_cells(area)
    mo, mi = len(outer), len(inner)
    if n_out > mo or n_in not in INNER_SUBSETS:
        return None
    n = n_out + n_in
    lattice = slots(6 if area == "quarter" else 12)
    if n > len(lattice):
        return None
    out_idx = [(o_out + i * mo // n_out) % mo for i in range(n_out)]
    in_idx = [(o_in + k) % mi for k in INNER_SUBSETS[n_in]]
    ring_pos = [outer[i] for i in out_idx] + [inner[i] for i in in_idx]
    # nearest free lattice slot for each drone, so the first flight is short
    free = list(lattice)
    starts = []
    order = list(range(n))
    rng.shuffle(order)
    chosen = {}
    for i in order:
        best = min(free, key=lambda c: travel(ring_pos[i], c) + rng.random() * 60)
        chosen[i] = best
        free.remove(best)
    starts = [chosen[i] for i in range(n)]
    plan = Plan(sid, "", "", area, ["Кольцо"])
    steps = mo * laps
    so = 1 if dir_out == "ccw" else -1
    si = step_in * (1 if dir_in == "ccw" else -1)
    for i, idx in enumerate(out_idx):
        ops = [("code", (outer[idx], seconds_for(travel(starts[i], outer[idx]), 25))), ("rgb", (PALETTE[i % 7],))]
        for k in range(1, steps + 1):
            c = outer[(idx + so * k) % mo]
            ops += [("code", (c, move)), ("rgb", (PALETTE[(i + k) % 7] if scheme == "index" else colors_for(scheme, [c], k)[0],))]
        last = outer[(idx + so * steps) % mo]
        ops += [("code", (starts[i], seconds_for(travel(last, starts[i]), 25)))]
        plan.add(starts[i], 130 if i % 2 == 0 else 150, PALETTE[i % 7], ops, starts[i])
    for j, idx in enumerate(in_idx):
        h = n_out + j
        ops = [("code", (inner[idx], seconds_for(travel(starts[h], inner[idx]), 25))), ("rgb", (PALETTE[(j + 3) % 7],))]
        for k in range(1, steps + 1):
            c = inner[(idx + si * k) % mi]
            ops += [("code", (c, move)), ("rgb", (PALETTE[(j + k + 3) % 7],))]
        last = inner[(idx + si * steps) % mi]
        ops += [("code", (starts[h], seconds_for(travel(last, starts[h]), 25)))]
        plan.add(starts[h], [60, 85][j % 2], PALETTE[(j + 3) % 7], ops, starts[h])
    turn = {("ccw", "ccw"): "в одну сторону", ("ccw", "cw"): "навстречу друг другу", ("cw", "cw"): "в одну сторону", ("cw", "ccw"): "навстречу друг другу"}[(dir_out, dir_in)]
    fast = ", внутреннее вдвое быстрее" if step_in == 2 else ""
    plan.title = f"Два кольца: {n_out} снаружи и {n_in} внутри, {turn}" + fast
    plan.note = (f"{dr(n)} вылетают с ровной сетки в два кольца: внешнее из {n_out} на высоте 130-150 см, внутреннее из {n_in} на 60-85 см; "
                 f"кольца вращаются {turn}{fast}, {laps} {'круг' if laps == 1 else 'круга' if laps < 5 else 'кругов'}, потом дроны возвращаются на сетку.")
    turn_en = {("ccw", "ccw"): "in one direction", ("ccw", "cw"): "against each other", ("cw", "cw"): "in one direction", ("cw", "ccw"): "against each other"}[(dir_out, dir_in)]
    fast_en = ", the inner one twice as fast" if step_in == 2 else ""
    plan.title_en = f"Two rings: {n_out} outside and {n_in} inside, {turn_en}" + fast_en
    plan.note_en = (f"{dr_en(n)} take off from an even grid into two rings: the outer one of {n_out} at 130-150 cm, the inner one of {n_in} at 60-85 cm; "
                    f"the rings turn {turn_en}{fast_en}, {laps} laps, then the drones return to the grid.")
    return plan if clean(plan) else None


# ---------------------------------------------------------------------------------------------------------------
# family 3: a wave of height runs along a line of drones

def try_wave(sid, rng, area, n, rows, mode, delay, low, high, cycles):
    grid = 6 if area == "quarter" else 12
    lattice_x = list(range(0, grid, 2))
    per_row = math.ceil(n / rows)
    if per_row > len(lattice_x):
        return None
    ys = [1, 4] if area == "quarter" else [2, 8]
    ys = ys[:rows] if rows <= 2 else None
    if ys is None:
        return None
    plan = Plan(sid, "", "", area, ["Волна высоты"])
    placed = []
    for i in range(n):
        r, c = divmod(i, per_row)
        placed.append((lattice_x[c], ys[r], c))
    order = {"right": lambda c, per: c, "left": lambda c, per: per - 1 - c,
             "centre": lambda c, per: abs(2 * c - (per - 1)) // 2, "edges": lambda c, per: (per - 1) // 2 - abs(2 * c - (per - 1)) // 2}[mode]
    rise = 4
    for i, (x, y, c) in enumerate(placed):
        wait = order(c, per_row) * delay
        ops = []
        if wait:
            ops.append(("set_z", (low, wait)))
        for k in range(cycles):
            col_up, col_down = PALETTE[(c + k) % len(PALETTE)], PALETTE[(c + k + 3) % len(PALETTE)]
            ops += [("set_z", (high, rise)), ("rgb", (col_up,)), ("set_z", (high, 1)), ("set_z", (low, rise)), ("rgb", (col_down,))]
        tail = (per_row - 1 - order(c, per_row)) * delay if mode in ("right", "left") else (per_row - 1 - order(c, per_row)) * delay
        if tail:
            ops.append(("set_z", (low, tail)))
        plan.add(cell(x, y), low, PALETTE[c % len(PALETTE)], ops, cell(x, y))
    names = {"right": "слева направо", "left": "справа налево", "centre": "от центра к краям", "edges": "от краёв к центру"}
    plan.title = f"Волна высоты {names[mode]}, {dr(n)}"
    plan.note = f"{dr(n)} стоят в {'один ряд' if rows == 1 else 'два ряда'}, высота {low}-{high} см бежит {names[mode]} с задержкой {delay} с."
    names_en = {"right": "from left to right", "left": "from right to left", "centre": "from the centre to the edges", "edges": "from the edges to the centre"}
    plan.title_en = f"Height wave {names_en[mode]}, {dr_en(n)}"
    plan.note_en = f"{dr_en(n)} stand in {'one row' if rows == 1 else 'two rows'}, the height {low}-{high} cm runs {names_en[mode]} with a delay of {delay} s."
    return plan if clean(plan) else None


# ---------------------------------------------------------------------------------------------------------------
# family 4: light only, the drones hang in place and play a pattern

PATTERNS = ["chase", "rainbow", "pulse", "alternate", "sweep", "counter", "police", "traffic", "twinkle", "breathe"]
PATTERN_NAMES = {
    "chase": "Бегущий огонь", "rainbow": "Радуга по кругу", "pulse": "Общий пульс", "alternate": "Через одного",
    "sweep": "Волна цвета", "counter": "Двоичный счётчик", "police": "Мигалка", "traffic": "Светофор",
    "twinkle": "Мерцание", "breathe": "Дыхание",
}


def light_ops(pattern, i, n, rng_seed):
    """Calls of drone i for a pattern: colours with waits at the same height (a hold is a set_z on the height)."""
    rnd = random.Random(rng_seed * 100 + i)
    ops = []
    beat = 1
    if pattern == "chase":
        for lap in range(3):
            for k in range(n):
                ops += [("rgb", (PALETTE[lap % 7] if k == i else "black",)), ("hold", (beat,))]
    elif pattern == "rainbow":
        for k in range(14):
            ops += [("rgb", (PALETTE[(i + k) % 7],)), ("hold", (beat,))]
    elif pattern == "pulse":
        for k in range(6):
            ops += [("rgb", (PALETTE[k % 7],)), ("hold", (2,)), ("rgb", ("black",)), ("hold", (1,))]
    elif pattern == "alternate":
        for k in range(12):
            on = (k + i) % 2 == 0
            ops += [("rgb", (PALETTE[(k // 2) % 7] if on else "black",)), ("hold", (beat,))]
    elif pattern == "sweep":
        for k in range(n + 6):
            ops += [("rgb", (PALETTE[(k - i) % 7] if 0 <= k - i < 7 else "black",)), ("hold", (beat,))]
    elif pattern == "counter":
        for value in range(2 ** min(n, 4)):
            ops += [("rgb", ("green" if (value >> (i % 4)) & 1 else "black",)), ("hold", (1,))]
    elif pattern == "police":
        for k in range(12):
            first = i % 2 == 0
            ops += [("rgb", (("red" if (k % 2 == 0) == first else "blue"),)), ("hold", (1,))]
    elif pattern == "traffic":
        for k in range(4):
            for colour, secs in (("green", 3), ("yellow", 1), ("red", 3)):
                ops += [("rgb", (colour if (i + k) % 2 == 0 else "black",)), ("hold", (secs,))]
    elif pattern == "twinkle":
        for k in range(16):
            ops += [("rgb", (rnd.choice(PALETTE + ["black", "black"]),)), ("hold", (1,))]
    elif pattern == "breathe":
        for k in range(4):
            for colour in ("blue", "cyan", "white", "cyan"):
                ops += [("rgb", (colour,)), ("hold", (1,))]
    return ops


def try_light(sid, rng, area, n, pattern, seed):
    grid = 6 if area == "quarter" else 12
    lattice = slots(grid)
    if n > len(lattice):
        return None
    cells = lattice[:n] if area == "quarter" else sorted(rng.sample(lattice, n))
    plan = Plan(sid, "", "", area, ["Игры света"])
    heights = [90 if i % 2 == 0 else 125 for i in range(n)]
    for i in range(n):
        z = heights[i]
        # a beat of two seconds (not one) keeps a drone under the 255 steps the protocol takes
        base = [(m, (a[0] * 2,)) if m == "hold" else (m, a) for m, a in light_ops(pattern, i, n, seed)]
        length = sum(a[0] for m, a in base if m == "hold") or 1
        reps = min(14, max(1, math.ceil(160 / length)), max(1, 200 // len(base)))
        ops = [("set_z", (z, a[0])) if m == "hold" else (m, a) for m, a in base * reps]
        plan.add(cells[i], z, "black", ops, cells[i])
    plan.title = f"{PATTERN_NAMES[pattern]}, {dr(n)}"
    plan.note = f"Только свет: {dr(n)} висят на местах, узор «{PATTERN_NAMES[pattern].lower()}»."
    plan.title_en = f"{PATTERN_EN[pattern]}, {dr_en(n)}"
    plan.note_en = f"Light only: {dr_en(n)} hang in place, the pattern “{PATTERN_EN[pattern].lower()}”."
    return plan if clean(plan) else None


# ---------------------------------------------------------------------------------------------------------------
# family 5: a snake of drones follows a path through the lattice

def lattice_paths(grid):
    m = grid // 2
    rows = [[(x, y) for x in (range(m) if y % 2 == 0 else range(m - 1, -1, -1))] for y in range(m)]
    snake = [p for r in rows for p in r]
    cols = [[(x, y) for y in (range(m) if x % 2 == 0 else range(m - 1, -1, -1))] for x in range(m)]
    snake_v = [p for r in cols for p in r]
    ring = [(x, 0) for x in range(m)] + [(m - 1, y) for y in range(1, m)] + [(x, m - 1) for x in range(m - 2, -1, -1)] + [(0, y) for y in range(m - 2, 0, -1)]
    spiral = []
    top, bottom, left, right = 0, m - 1, 0, m - 1
    while top <= bottom and left <= right:
        spiral += [(x, top) for x in range(left, right + 1)]
        spiral += [(right, y) for y in range(top + 1, bottom + 1)]
        if top < bottom:
            spiral += [(x, bottom) for x in range(right - 1, left - 1, -1)]
        if left < right:
            spiral += [(left, y) for y in range(bottom - 1, top, -1)]
        top, bottom, left, right = top + 1, bottom - 1, left + 1, right - 1
    diag = []
    for s in range(2 * m - 1):
        cells = [(x, s - x) for x in range(m) if 0 <= s - x < m]
        diag += cells if s % 2 == 0 else cells[::-1]
    return {"Строчками": snake, "Столбцами": snake_v, "Рамкой": ring, "Спиралью": spiral, "Диагоналями": diag}


def try_snake(sid, rng, area, n, path_name, reverse):
    grid = 6 if area == "quarter" else 12
    path = lattice_paths(grid)[path_name]
    if reverse:
        path = path[::-1]
    if n + 2 > len(path):
        return None
    plan = Plan(sid, "", "", area, ["Змейка"])
    move = 4
    total = len(path) - n
    heights = [90 if i % 2 == 0 else 130 for i in range(n)]
    for i in range(n):
        # drone i is the i-th from the head; it starts n-1-i places behind the head. To the end of the path, then back.
        ops = []
        for k in range(1, total + 1):
            x, y = path[n - 1 - i + k]
            ops += [("code", (cell(2 * x, 2 * y), move)), ("rgb", (PALETTE[(i + k) % 7],))]
        for k in range(1, total + 1):
            x, y = path[n - 1 - i + total - k]
            ops += [("code", (cell(2 * x, 2 * y), move)), ("rgb", (PALETTE[(i + k + 3) % 7],))]
        sx, sy = path[n - 1 - i]
        plan.add(cell(2 * sx, 2 * sy), heights[i], PALETTE[i % 7], ops * 2, cell(2 * sx, 2 * sy))
    plan.title = f"Змейка {path_name.lower()}, {dr(n)}" + (" (с конца)" if reverse else "")
    plan.note = f"{dr(n)} цепочкой ползут по сетке {path_name.lower()} до конца пути и обратно, дважды: каждый занимает место того, кто впереди."
    plan.title_en = f"Snake {PATH_EN[path_name]}, {dr_en(n)}" + (" (from the end)" if reverse else "")
    plan.note_en = f"{dr_en(n)} crawl in a chain over the grid {PATH_EN[path_name]} to the end of the path and back, twice: each takes the place of the one in front."
    return plan if clean(plan) else None


# ---------------------------------------------------------------------------------------------------------------
# family 6: swaps, groups trade places at different heights

def try_swap(sid, rng, area, n, mode):
    grid = 6 if area == "quarter" else 12
    lattice = slots(grid)
    m = grid // 2
    pairs = []
    if mode == "rows":  # the first row and the last row
        a = [cell(2 * x, 0) for x in range(m)]
        b = [cell(2 * x, grid - 2) for x in range(m)]
        pairs = list(zip(a, b))
    elif mode == "columns":
        a = [cell(0, 2 * y) for y in range(m)]
        b = [cell(grid - 2, 2 * y) for y in range(m)]
        pairs = list(zip(a, b))
    elif mode == "diagonals":
        pairs = [(cell(0, 0), cell(grid - 2, grid - 2)), (cell(grid - 2, 0), cell(0, grid - 2))]
    elif mode == "mirror":
        left = [(x, y) for y in range(m) for x in range(m // 2)]
        pairs = [(cell(2 * x, 2 * y), cell(2 * (m - 1 - x), 2 * y)) for x, y in left]
    elif mode == "centre":
        centre = (m // 2, m // 2)
        edge = [(x, y) for y in range(m) for x in range(m) if (x, y) != centre and (x in (0, m - 1) or y in (0, m - 1))]
        pairs = [(cell(2 * centre[0], 2 * centre[1]), cell(2 * edge[0][0], 2 * edge[0][1]))]
    if not pairs:
        return None
    pairs = pairs[: n // 2]
    if len(pairs) * 2 != n:
        return None
    plan = Plan(sid, "", "", area, ["Обмен местами"])
    for k, (a, b) in enumerate(pairs):
        low, high = (80, 150) if k % 2 == 0 else (60, 130)
        ca, cb = PALETTE[k % 7], PALETTE[(k + 3) % 7]
        dist = travel(a, b)
        move = seconds_for(dist, 25)
        trip_a = [("code", (b, move)), ("rgb", ("white",)), ("set_z", (low, 4)), ("code", (a, move)), ("rgb", (ca,)), ("set_z", (low, 4))]
        trip_b = [("code", (a, move)), ("rgb", ("white",)), ("set_z", (high, 4)), ("code", (b, move)), ("rgb", (cb,)), ("set_z", (high, 4))]
        plan.add(a, low, ca, trip_a * 6, a)
        plan.add(b, high, cb, trip_b * 6, b)
    names = {"rows": "ряды", "columns": "колонны", "diagonals": "углы по диагонали", "mirror": "зеркальные пары", "centre": "центр и край"}
    plan.title = f"Обмен: {names[mode]}, {dr(n)}"
    plan.note = f"{dr(n)} парами шесть раз меняются местами ({names[mode]}) на разной высоте и возвращаются."
    names_en = {"rows": "rows", "columns": "columns", "diagonals": "corners on the diagonal", "mirror": "mirror pairs", "centre": "centre and edge"}
    plan.title_en = f"Swap: {names_en[mode]}, {dr_en(n)}"
    plan.note_en = f"{dr_en(n)} swap places in pairs six times ({names_en[mode]}) at different heights and return."
    return plan if clean(plan) else None


# ---------------------------------------------------------------------------------------------------------------
# family 7: circle steps around a centre (the direction of circles is a guess of the simulator; not flown yet)

def try_circle(sid, rng, area, layout, count, seconds, second):
    if area == "quarter":
        c1, c2 = cell(2, 2), cell(3, 3)
        spots = {"two": [(1, 1), (4, 4)], "four": [(1, 1), (4, 1), (4, 4), (1, 4)], "cross": [(1, 1), (4, 4), (4, 1), (1, 4)]}
    else:
        c1, c2 = cell(5, 5), cell(6, 6)
        spots = {"two": [(1, 1), (10, 10)], "four": [(1, 1), (10, 1), (10, 10), (1, 10)], "cross": [(1, 1), (10, 10), (10, 1), (1, 10)],
                 "six": [(1, 1), (10, 10), (10, 1), (1, 10), (5, 0), (6, 11)]}
    if layout not in spots:
        return None
    pts = spots[layout]
    (ax, ay), (bx, by) = ((c1 % GRID_W, c1 // GRID_W), (c2 % GRID_W, c2 // GRID_W))
    plan = Plan(sid, "", "", area, ["Круги"])
    total_half = count * (2 if second else 1)
    for i, (x, y) in enumerate(pts):
        opposite = layout == "cross" and i >= 2
        rot, rot2 = ("ccw", "cw") if opposite else ("cw", "ccw")
        z = 70 if layout != "cross" or i < 2 else 140
        start = cell(x, y)
        ops = [("circle", (count, c1, c2, seconds, rot))]
        if second:
            ops += [("rgb", (PALETTE[(i + 3) % 7],)), ("circle", (count, c1, c2, seconds, rot2))]
        ops = ops + [("rgb", (PALETTE[(i + 5) % 7],))] + ops
        end = start if (total_half * 2) % 2 == 0 else cell(ax + bx - x, ay + by - y)
        plan.add(start, z if layout == "cross" else 100, PALETTE[i % 7], ops, end)
    word = {"two": "два дрона напротив друг друга", "four": "четыре дрона по углам", "cross": "две пары навстречу на разной высоте", "six": "шесть дронов по кругу"}[layout]
    halves = {1: "полоборота", 2: "оборот", 3: "полтора оборота", 4: "два оборота"}[count]
    plan.title = f"Круг: {word}, {halves}" + (" и обратно" if second else "")
    plan.note = f"Шаги circle вокруг центра: {word}, {halves}" + (", потом столько же в другую сторону" if second else "") + ". На дроне шаг circle длится count × время, а симулятор считает время за весь круг."
    word_en = {"two": "two drones opposite each other", "four": "four drones at the corners", "cross": "two pairs against each other at different heights", "six": "six drones round a circle"}[layout]
    halves_en = {1: "half a turn", 2: "one turn", 3: "one and a half turns", 4: "two turns"}[count]
    plan.title_en = f"Circle: {word_en}, {halves_en}" + (" and back" if second else "")
    plan.note_en = f"circle steps around the centre: {word_en}, {halves_en}" + (", then the same the other way" if second else "") + ". On the drone a circle step lasts count × time, while the simulator counts the time for the whole circle."
    return plan if clean(plan) else None


def tags_of(show):
    kinds = {s.kind for d in show.drones.values() for s in d.steps}
    moves = False
    for d in show.drones.values():
        last = None
        for s in d.steps:
            if s.kind in ("code", "code_z"):
                if last is not None and s.args["cell"] != last:
                    moves = True
                last = s.args["cell"]
    circles = bool(kinds & {"circle", "circle_z"})
    heights = [s.args["z"] for d in show.drones.values() for s in d.steps if s.kind in ("takeoff", "set_z", "code_z") and s.args["z"] > 35]
    tags = ["Перемещения" if (moves or circles) else "Только свет"]
    if circles:
        tags.append("Круги circle")
    if heights and max(heights) - min(heights) >= 50:
        tags.append("Разная высота")
    if not kinds & {"circle_z", "code_z"}:
        tags.append("Проверенные шаги")
    return tags


def real_seconds(show):
    """How long the longest drone flies on a real drone: a circle step lasts count x its time there (the simulator
    counts it once), and landing adds nothing."""
    best = 0.0
    for d in show.drones.values():
        total = 0.0
        for step in d.steps:
            if step.kind == "circle":
                total += step.seconds * step.args["count"]
            elif step.kind != "land":
                total += step.seconds
        best = max(best, total)
    return best


def generate():
    rng = random.Random(20260)
    plans = []
    used_titles = set()
    titles_seen = {}

    def accept(plan):
        if plan is None or max(len(d.steps) for d in plan.build().drones.values()) > 250 or real_seconds(plan.build()) > 300:   # more than five minutes is more than a battery of the Wing is good for
            return False
        # the same show twice (same moves, same colours) is dropped; the same title with other moves gets a number
        signature = (plan.area, repr(plan.drones))
        if signature in used_titles:
            return False
        used_titles.add(signature)
        key = (plan.area, plan.title, len(plan.drones))
        seen = titles_seen.get(key, 0)
        titles_seen[key] = seen + 1
        if seen:
            plan.title += f" (вариант {seen + 1})"
            plan.title_en += f" (variant {seen + 1})"
        plans.append(plan)
        return True

    counters = {}

    def sid(family, area, n):
        key = (family, area, n)
        counters[key] = counters.get(key, 0) + 1
        return f"{family}_{area[0]}{n}_{counters[key]:02d}"

    # morph: pick formation sequences that fit
    shape_pool = ["line", "column", "diag", "anti", "vee", "arch", "zigzag", "stairs", "ring", "square", "block", "plus", "xcross",
                  "diamond", "triangle", "ell", "tee", "twolines"]
    targets = [("quarter", n) for n in (2, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8)] * 6 + [("full", n) for n in (2, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10)] * 5
    attempts = 0
    for area, n in targets:
        for _ in range(60):
            attempts += 1
            k = rng.choice([3, 3, 4, 4, 5])
            shapes = [rng.choice(shape_pool) for _ in range(k)]
            if len(set(shapes)) < k:
                continue
            spacings = [rng.choice([1, 1, 2]) if area == "quarter" else rng.choice([1, 2, 2]) for _ in shapes]
            scheme = rng.choice(COLOR_SCHEMES)
            speed = rng.choice([15, 20, 25])
            hold = rng.choice([5, 6, 8])
            rounds = rng.choice([2, 2, 3])
            plan = try_morph(sid("morph", area, n), rng, area, n, shapes, spacings, scheme, speed, hold, rounds)
            if plan and accept(plan):
                break

    # rings
    for area, n, step, laps, direction, move, centre in [
        ("quarter", 4, 1, 6, "cw", 4, False), ("quarter", 4, 2, 6, "ccw", 4, False), ("quarter", 5, 1, 6, "ccw", 4, True),
        ("quarter", 6, 1, 6, "cw", 4, False), ("quarter", 6, 2, 6, "ccw", 4, True), ("quarter", 7, 1, 5, "cw", 4, False),
        ("quarter", 8, 1, 5, "ccw", 4, False), ("quarter", 8, 2, 6, "cw", 4, False), ("quarter", 3, 1, 6, "cw", 4, False),
        ("full", 6, 1, 2, "cw", 4, False), ("full", 8, 1, 2, "ccw", 4, True), ("full", 10, 1, 2, "cw", 4, False),
        ("full", 10, 2, 4, "ccw", 4, False), ("full", 5, 2, 4, "cw", 4, False)]:
        for scheme in COLOR_SCHEMES:
            plan = try_ring(sid("ring", area, n), rng, area, n, step, laps, direction, scheme, move, centre)
            if plan and accept(plan):
                break

    # two rings: an outer one and an inner one (the quarter of the mat gets seven drones this way)
    ring_jobs = [("quarter", 4, 3)] * 4 + [("quarter", 3, 4)] * 3 + [("quarter", 5, 2)] * 3 + [("quarter", 6, 1)] * 2 + [
        ("quarter", 4, 4), ("quarter", 5, 3), ("quarter", 6, 2), ("quarter", 4, 2), ("quarter", 3, 3), ("quarter", 3, 2), ("quarter", 5, 1),
        ("full", 6, 4), ("full", 7, 3), ("full", 8, 2), ("full", 5, 3), ("full", 6, 3), ("full", 4, 3), ("full", 6, 2)]
    for area, n_out, n_in in ring_jobs:
        done = False
        for _ in range(400):
            o_out, o_in = rng.randrange(8 if area == "quarter" else 20), rng.randrange(8)
            dir_out, dir_in = rng.choice(["ccw", "cw"]), rng.choice(["ccw", "cw"])
            step_in = rng.choice([1, 2]) if area == "quarter" else 2
            laps = rng.choice([4, 5]) if area == "quarter" else 2
            plan = try_double_ring("tmp", rng, area, n_out, n_in, o_out, o_in, dir_out, dir_in, step_in, laps, 4, rng.choice(COLOR_SCHEMES))
            if plan and accept(plan):
                break

    # waves
    for area, n, rows, mode, delay, low, high, cycles in [
        ("quarter", 3, 1, "right", 2, 60, 150, 12), ("quarter", 3, 1, "centre", 2, 60, 140, 12), ("quarter", 4, 2, "right", 2, 60, 150, 12),
        ("quarter", 6, 2, "left", 2, 70, 150, 12), ("quarter", 6, 2, "centre", 2, 60, 150, 12), ("quarter", 5, 2, "edges", 2, 60, 150, 12),
        ("quarter", 6, 2, "right", 3, 60, 130, 10), ("full", 6, 1, "right", 2, 60, 150, 12), ("full", 6, 1, "centre", 2, 60, 150, 12),
        ("full", 10, 2, "right", 2, 60, 150, 12), ("full", 10, 2, "centre", 2, 60, 140, 12), ("full", 8, 2, "left", 3, 70, 150, 10),
        ("full", 9, 2, "edges", 2, 60, 150, 12), ("full", 4, 1, "left", 3, 60, 130, 14)]:
        accept(try_wave(sid("wave", area, n), rng, area, n, rows, mode, delay, low, high, cycles))

    # light
    light_targets = []
    for p_i, pattern in enumerate(PATTERNS):
        light_targets += [("quarter", 4 + (p_i % 3) * 2, pattern), ("full", 6 + (p_i % 3) * 2, pattern)]
    light_targets += [("quarter", 3, "chase"), ("quarter", 8, "rainbow"), ("full", 10, "counter"), ("quarter", 4, "counter")]
    for area, n, pattern in light_targets:
        accept(try_light(sid("light", area, n), rng, area, n, pattern, len(plans) + 1))

    # snakes
    for area, n, path_name, reverse in [
        ("quarter", 3, "Строчками", False), ("quarter", 3, "Столбцами", False), ("quarter", 4, "Строчками", True), ("quarter", 3, "Рамкой", False),
        ("quarter", 4, "Спиралью", False), ("quarter", 3, "Диагоналями", False), ("quarter", 5, "Строчками", False),
        ("full", 4, "Строчками", False), ("full", 5, "Спиралью", False), ("full", 6, "Рамкой", False), ("full", 5, "Диагоналями", False),
        ("full", 8, "Строчками", True), ("full", 10, "Спиралью", False), ("full", 6, "Столбцами", False)]:
        accept(try_snake(sid("snake", area, n), rng, area, n, path_name, reverse))

    # swaps
    for area, n, mode in [("quarter", 6, "rows"), ("quarter", 6, "columns"), ("quarter", 2, "diagonals"), ("quarter", 4, "mirror"),
                          ("full", 12, "rows"), ("full", 6, "rows"), ("full", 6, "columns"), ("full", 4, "diagonals"),
                          ("full", 4, "mirror"), ("full", 6, "mirror"), ("quarter", 2, "centre"), ("full", 2, "centre")]:
        accept(try_swap(sid("swap", area, n), rng, area, n, mode))
    for area, layout, count, seconds, second in [
        ("quarter", "two", 2, 16, True), ("quarter", "two", 4, 24, False), ("quarter", "four", 2, 16, True), ("quarter", "four", 3, 22, True),
        ("quarter", "cross", 2, 16, True), ("quarter", "cross", 4, 24, False), ("quarter", "four", 4, 24, False),
        ("full", "two", 2, 22, True), ("full", "four", 3, 26, True), ("full", "four", 2, 20, True), ("full", "cross", 2, 22, True),
        ("full", "six", 2, 22, True)]:
        accept(try_circle("tmp", rng, area, layout, count, seconds, second))

    # real ids: family, area, number of drones, a running number (the search above made many throw-away candidates)
    final = {}
    for plan in plans:
        family = "circle" if plan.themes == ["Круги"] else {"Строи": "morph", "Кольцо": "ring", "Волна высоты": "wave", "Игры света": "light",
                                                          "Змейка": "snake", "Обмен местами": "swap"}[plan.themes[0]]
        if plan.title.startswith("Два кольца"):
            family = "rings2"
        key = (family, plan.area, len(plan.drones))
        final[key] = final.get(key, 0) + 1
        plan.sid = f"{family}_{plan.area[0]}{len(plan.drones)}_{final[key]:02d}"
    return plans


def main():
    os.makedirs(OUT_PY, exist_ok=True)
    os.makedirs(OUT_JSON, exist_ok=True)
    for folder in (OUT_PY, OUT_JSON):
        for name in os.listdir(folder):
            os.remove(os.path.join(folder, name))
    plans = [p for p in generate() if len(p.drones) <= 10]
    catalog = []
    pairs = []
    for plan in plans:
        path = os.path.join(OUT_PY, f"{plan.sid}.py")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(plan.source())
        show = load_show(path)  # the file as written must load, and must still be clean
        bad = [f for f in check_show(show, 60, max_height_cm=150) if f.level != "info"]
        if bad:
            raise SystemExit(f"{plan.sid}: {bad[0]}")
        data = {"name": show.name, "drones": {str(n): [{"kind": s.kind, "seconds": s.seconds, "args": s.args, "line": s.line}
                                                       for s in d.steps] for n, d in sorted(show.drones.items())}}
        with open(os.path.join(OUT_JSON, f"{plan.sid}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        pairs.append((plan.title, plan.title_en))
        pairs.append((plan.note, plan.note_en))
        catalog.append({"id": plan.sid, "title": plan.title, "note": plan.note, "area": plan.area, "drones": len(show.drones),
                        "seconds": round(show.duration), "themes": plan.themes, "tags": tags_of(show)})
    # the shows made by hand keep their titles in the app; the catalog gives their numbers and tags
    classic_themes = {
        "quarter_traffic": "Игры света", "quarter_baton": "Игры света", "quarter_pair_dialog": "Игры света", "full_rainbow": "Игры света",
        "quarter_wave": "Волна высоты", "quarter_ladder": "Волна высоты", "full_wave": "Волна высоты", "quarter_pair_elevator": "Волна высоты",
        "quarter_six_wave": "Волна высоты", "quarter_circle": "Круги", "quarter_twin": "Круги", "quarter_spiral": "Круги", "full_rings": "Круги",
        "quarter_swap": "Обмен местами", "quarter_pair_cross": "Обмен местами", "quarter_pair_leapfrog": "Обмен местами",
        "quarter_six_swap": "Обмен местами", "quarter_pair_follow": "Змейка", "quarter_pair_orbit": "Кольцо", "quarter_five_cross": "Кольцо",
        "quarter_seven_hex": "Кольцо", "quarter_eight_carousel": "Кольцо", "my_dream": "Из LiteBee Go", "my_people_my_country_5": "Из LiteBee Go",
    }
    classic_en = {
        "quarter_traffic": ("Светофор", "Traffic light", "3 дрона, только свет", "3 drones, light only"),
        "quarter_square": ("Квадрат", "Square", "4 дрона, по углам", "4 drones, at the corners"),
        "quarter_expand": ("Раскрытие", "Unfolding", "4 дрона, в углы и назад", "4 drones, to the corners and back"),
        "quarter_swap": ("Обмен местами", "Swapping places", "4 дрона, разная высота", "4 drones, different heights"),
        "quarter_wave": ("Волна высоты", "Height wave", "4 дрона", "4 drones"),
        "quarter_circle": ("Круг", "Circle", "4 дрона, circle", "4 drones, circle"),
        "quarter_twin": ("Двойная звезда", "Double star", "2 дрона, circle в обе стороны", "2 drones, circle both ways"),
        "quarter_ladder": ("Лесенка", "Stairs", "3 дрона, высота 80–140", "3 drones, height 80–140"),
        "quarter_frame": ("Строй по рамке", "Frame formation", "3 дрона, строем", "3 drones, in formation"),
        "quarter_spiral": ("Спираль", "Spiral", "2 дрона, вверх по кругу", "2 drones, up in a circle"),
        "quarter_baton": ("Эстафета света", "Light relay", "4 дрона, свет и высота", "4 drones, light and height"),
        "quarter_shuttle": ("Челнок", "Shuttle", "3 дрона, от края до края", "3 drones, from edge to edge"),
        "quarter_triangle": ("Треугольник", "Triangle", "3 дрона, по вершинам", "3 drones, to the vertices"),
        "quarter_hops": ("Прыжки по очереди", "Hops in turn", "4 дрона", "4 drones"),
        "full_rainbow": ("Радуга", "Rainbow", "6 дронов, только свет", "6 drones, light only"),
        "full_corners": ("Углы к центру", "Corners to the centre", "4 дрона", "4 drones"),
        "full_march": ("Марш двух рядов", "March of two rows", "10 дронов", "10 drones"),
        "full_wave": ("Волна по коврику", "Wave across the mat", "10 дронов", "10 drones"),
        "full_rings": ("Два кольца", "Two rings", "8 дронов, circle", "8 drones, circle"),
        "my_dream": ("My Dream", "My Dream", "ваше шоу, 10 дронов", "your show, 10 drones"),
        "my_people_my_country_5": ("My People, My Country (5)", "My People, My Country (5)", "ваше шоу, 10 дронов", "your show, 10 drones"),
        "quarter_pair_cross": ("Разминуться", "Passing each other", "2 дрона, по диагоналям на разной высоте", "2 drones, along the diagonals at different heights"),
        "quarter_pair_mirror": ("Зеркало", "Mirror", "2 дрона, противоположные углы", "2 drones, opposite corners"),
        "quarter_pair_follow": ("Догонялки", "Tag", "2 дрона, один за другим", "2 drones, one after the other"),
        "quarter_pair_elevator": ("Лифт", "Elevator", "2 дрона, высота в противофазе, только свет и высота", "2 drones, heights in antiphase, light and height only"),
        "quarter_pair_orbit": ("Облёт", "Fly-round", "2 дрона, кольцо вокруг зависшего", "2 drones, a ring round the hovering one"),
        "quarter_pair_zigzag": ("Зигзаг", "Zigzag", "2 дрона, две половины коврика", "2 drones, two halves of the mat"),
        "quarter_pair_dialog": ("Диалог света", "Dialogue of light", "2 дрона, только свет", "2 drones, light only"),
        "quarter_pair_leapfrog": ("Чехарда", "Leapfrog", "2 дрона, по очереди над друг другом", "2 drones, over each other in turn"),
        "quarter_five_cross": ("Пятёрка: хоровод", "Five: round dance", "5 дронов, обход квадрата и центр", "5 drones, round the square and the centre"),
        "quarter_six_swap": ("Шестёрка: ряды меняются", "Six: rows swap", "6 дронов, два ряда", "6 drones, two rows"),
        "quarter_six_wave": ("Шестёрка: волна", "Six: wave", "6 дронов, бегущая волна высоты", "6 drones, a running wave of height"),
        "quarter_seven_hex": ("Семёрка: шестиугольник", "Seven: hexagon", "7 дронов, кольцо и центр", "7 drones, a ring and the centre"),
        "quarter_eight_carousel": ("Восьмёрка: карусель", "Eight: carousel", "8 дронов, бегущие цвета", "8 drones, running colours"),
        "quarter_eight_pulse": ("Восьмёрка: пульс", "Eight: pulse", "8 дронов, сжатие и разжатие", "8 drones, squeezing and releasing"),
    }
    classic = []
    shows_dir = os.path.join(ROOT, "shows")
    for name in sorted(os.listdir(shows_dir)):
        if not name.endswith(".py"):
            continue
        show = load_show(os.path.join(shows_dir, name))
        stem = name[:-3]
        if stem in classic_en:
            t_ru, t_en, n_ru, n_en = classic_en[stem]
            pairs += [(t_ru, t_en), (n_ru, n_en), (show.name, t_en)]
        classic.append({"id": stem, "area": "quarter" if stem.startswith("quarter_") else "full", "drones": len(show.drones),
                        "seconds": round(show.duration), "themes": [classic_themes.get(stem, "Строи")], "tags": tags_of(show)})
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump({"gallery": catalog, "classic": classic}, f, ensure_ascii=False, indent=1)
    seen_pairs, lines = set(), []
    for ru, en in pairs:
        if ru and en and ru not in seen_pairs and ru != en:
            seen_pairs.add(ru)
            lines.append(f"  [{json.dumps(ru, ensure_ascii=False)}, {json.dumps(en, ensure_ascii=False)}],")
    with open(os.path.join(ROOT, "desktop", "src", "core", "i18n", "en.catalog.ts"), "w", encoding="utf-8", newline="\n") as f:
        f.write("/** English titles and notes of the examples. Written by tools/gen_gallery.py, do not edit by hand. */\n")
        f.write("export const EN_CATALOG: [ru: string, en: string][] = [\n" + "\n".join(lines) + "\n]\n")
    by = {}
    for c in catalog:
        by[c["id"].split("_")[0]] = by.get(c["id"].split("_")[0], 0) + 1
    print(len(catalog), "shows", by)


if __name__ == "__main__":
    main()
