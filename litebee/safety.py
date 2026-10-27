"""Limits and checks before anything can fly. User-facing messages are Russian."""
from dataclasses import dataclass
from math import dist
from typing import Iterable, List, Optional

from .mission import (CELL_CM, CMD_NAMES, DEFAULT_MAX_HEIGHT_CM, GRID_W, HARD_MAX_HEIGHT_CM,  # noqa: F401
                      MAX_HEIGHT_CM, MAX_HOVER_S, MIN_TAKEOFF_CM, PROVEN_CMDS, Mission, cell_from_xy,
                      resolve_max_height)
from .protocol import ALL_AUTOLAND  # noqa: F401  (re-exported: the emergency frame)

MIN_VOLTS = 7.0          # refuse to fly below this
WARN_VOLTS = 7.4         # UI shows amber below this
MIN_APPROACH_CM = 60.0   # default closest-approach threshold for shows
MAX_START_DISTANCE_CM = 200.0   # a cell-move mission is refused if the drone stands farther than this
                                # from the first cell it must move to (its own motion is absolute)
MAX_LEG_SPEED_CM_S = 100.0      # a cell move faster than this (average) gets a warning
# Position accuracy seen in flight: about +-10-15 cm, overshoot up to ~20 cm. A leg shorter than that
# is not a problem for the checks (no warning, it just may not be visible in the real flight).

NO_FIX_MESSAGE = ("У дрона нет позиции по коврику. Поставьте его на коврик и сделайте короткий взлёт "
                  "на 50 см, затем повторите")


class SafetyError(Exception):
    """A safety rule forbids the requested action."""


@dataclass
class Finding:
    level: str            # "error" | "warn" | "info"
    message: str
    drone: Optional[int] = None
    t: Optional[float] = None
    line: Optional[int] = None   # source line, when known

    def __str__(self):
        tag = {"error": "ОШИБКА", "warn": "ВНИМАНИЕ", "info": "ИНФО"}[self.level]
        return f"[{tag}] {self.message}"


def check_mission(mission: Mission, max_height_cm: Optional[int] = None) -> List[Finding]:
    """Static limits of a mission that can fly (battery is checked at preflight).

    `max_height_cm` is the active height limit (default 150; SafetyError if outside 20-200).
    Raising it never skips the hover limit or the proven-steps check."""
    limit = resolve_max_height(max_height_cm)
    out = []
    if not mission.can_fly:
        return out
    if mission.max_height_cm > limit:
        out.append(Finding("error", f"Высота {mission.max_height_cm} см больше лимита {limit} см"))
    if mission.max_hover_s > MAX_HOVER_S:
        out.append(Finding("error", f"Зависание {mission.max_hover_s:g} с больше лимита {MAX_HOVER_S} с"))
    for s in mission.steps:
        if s.cmd not in PROVEN_CMDS:
            out.append(Finding("error", f"Шаг {CMD_NAMES.get(s.cmd, s.cmd)} не проверен на живом дроне"))
        elif s.xy_cm is not None and s.cell is None:
            out.append(Finding("error", f"Шаг moveXY: точка {s.xy_cm[0]}, {s.xy_cm[1]} см не лежит на клетке коврика"))
    return out


def position_problem(first_cell: int, x: int, y: int, max_distance_cm: float = MAX_START_DISTANCE_CM) -> Optional[str]:
    """Why a drone at (x, y) cm may not run a mission whose first cell move goes to `first_cell`; else None.

    Without a fix (x = y = 0) the drone does not execute a moveXY mission at all. The drone's own
    motion is absolute, so a wrong starting cell sends it across the mat."""
    if not (x or y):
        return NO_FIX_MESSAGE
    tx, ty = (first_cell % GRID_W) * CELL_CM, (first_cell // GRID_W) * CELL_CM
    d = dist((x, y), (tx, ty))
    if d <= max_distance_cm:
        return None
    cur = cell_from_xy(x, y)
    where = f"на клетке {cur}" if cur is not None else "вне коврика"
    return (f"Дрон стоит {where}, а шоу ждёт его на клетке {first_cell}: расстояние {d:.0f} см больше "
            f"{max_distance_cm:.0f} см. Переставьте дрон ближе к клетке {first_cell} и повторите")


def check_position(mission: Mission, telemetry, max_distance_cm: float = MAX_START_DISTANCE_CM) -> None:
    """Raise SafetyError unless the telemetry shows a position fix near the mission's first cell move.
    Missions without cell moves need no position."""
    xy = mission.first_move_xy
    if xy is None:
        return
    if telemetry is None:
        raise SafetyError("Нет телеметрии: позиция дрона неизвестна, полёт отменён")
    first_cell = (xy[0] // CELL_CM) + GRID_W * (xy[1] // CELL_CM)
    why = position_problem(first_cell, telemetry.x, telemetry.y, max_distance_cm)
    if why:
        raise SafetyError(why)


def check_battery(volts: Optional[float], min_volts: float = MIN_VOLTS):
    if min_volts < MIN_VOLTS:
        raise SafetyError(f"Порог батареи нельзя ставить ниже {MIN_VOLTS} В")
    if volts is None:
        raise SafetyError("Нет телеметрии: заряд батареи неизвестен, полёт отменён")
    if volts < min_volts:
        raise SafetyError(f"Батарея {volts:.1f} В ниже {min_volts:.1f} В, полёт отменён")


def preflight(mission: Mission, *, ip: str, whitelist: Optional[Iterable[str]], volts: Optional[float],
              min_volts: float = MIN_VOLTS, max_height_cm: Optional[int] = None, telemetry=None) -> None:
    """Raise SafetyError unless the mission may be sent to the drone at `ip`.

    `telemetry` (the drone's latest Telemetry) is needed for missions with cell moves: the drone
    must have a position fix and stand near the first cell it moves to."""
    if mission.can_fly:
        if not whitelist:
            raise SafetyError("Полёт возможен только с белым списком IP")
        if ip not in set(whitelist):
            raise SafetyError(f"IP {ip} не в белом списке")
        errors = [f for f in check_mission(mission, max_height_cm) if f.level == "error"]
        if errors:
            raise SafetyError("; ".join(f.message for f in errors))
        check_battery(volts, min_volts)
        check_position(mission, telemetry)


def check_show(show, min_distance_cm: float = MIN_APPROACH_CM, top: int = 5,
               max_height_cm: Optional[int] = None) -> List[Finding]:
    """Findings from the simulator: mat bounds, heights, closest approaches, uploadability.

    `max_height_cm` is the active height limit (default 150; SafetyError if outside 20-200)."""
    from .show import GRID_W, UploadUnsupported, drone_to_mission  # local: show imports mission
    limit = resolve_max_height(max_height_cm)
    out: List[Finding] = []
    if not show.drones:
        return [Finding("warn", "В шоу нет ни одного дрона")]
    for n, d in sorted(show.drones.items()):
        for s in d.steps:
            cells = [s.args[k] for k in ("cell", "cell1", "cell2") if k in s.args]
            for c in cells:
                if not 0 <= c < GRID_W * GRID_W:
                    out.append(Finding("error", f"Дрон {n}: клетка {c} вне коврика 0-{GRID_W * GRID_W - 1}",
                                       drone=n, line=s.line))
        path = d.path()
        zmax = max((max(p[2][2], p[3][2]) for p in path), default=0)
        if zmax > limit:
            seg = next(p for p in path if max(p[2][2], p[3][2]) > limit)
            out.append(Finding("error", f"Дрон {n}: высота {zmax:g} см больше лимита {limit} см, "
                               "полёт будет отклонён", drone=n, t=seg[0], line=d.steps[seg[5]].line))
        for t0, t1, p0, p1, kind, idx in path:
            if kind not in ("code", "code_z"):
                continue
            leg_cm, leg_s = dist(p0, p1), t1 - t0
            speed = leg_cm / leg_s if leg_s > 0 else (float("inf") if leg_cm > 0 else 0.0)
            if speed > MAX_LEG_SPEED_CM_S:
                step = d.steps[idx]
                took = f"за {leg_s:g} с" if leg_s > 0 else "мгновенно"
                out.append(Finding("warn", f"Дрон {n}: переход на клетку {step.args['cell']} {took} ({leg_cm:.0f} см, "
                                   + (f"{speed:.0f} см/с" if leg_s > 0 else "без времени")
                                   + f") быстрее порога {MAX_LEG_SPEED_CM_S:.0f} см/с: дрон может перелететь клетку",
                                   drone=n, t=t0, line=step.line))
        try:
            drone_to_mission(d)
        except UploadUnsupported as e:
            out.append(Finding("info", f"Дрон {n}: загрузка в дрон недоступна. {e}", drone=n))
        else:
            first = next((s for s in d.steps if s.kind == "code"), None)
            if first is not None:
                out.append(Finding("info", f"Дрон {n}: шаги движения по клеткам. Перед загрузкой поставьте дрон на "
                                   f"клетку {first.args['cell']} (не дальше {MAX_START_DISTANCE_CM:.0f} см) и сделайте "
                                   "короткий взлёт на 50 см: без позиции по коврику дрон не выполнит миссию",
                                   drone=n, line=first.line))
    for dist_cm, t, a, b in show.closest_approaches(top=top):
        if dist_cm < min_distance_cm:
            step = show.drones[a].step_at(t)
            out.append(Finding("warn", f"Дроны {a} и {b} сближаются до {dist_cm:.0f} см на {t:.1f} с "
                               f"(порог {min_distance_cm:.0f} см)", drone=a, t=t,
                               line=step.line if step else None))
    return out
