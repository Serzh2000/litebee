"""Upload, verify, start and watch a mission on one drone, with emergency landing.

Port of the flow in drone_hop.py / drone_color.py. Nothing here starts motors
unless `arm=True` / `go=True` is passed explicitly.

Emergency landing (all_autoLand) is sent on any error, on abort (Event or the
LAND_NOW flag file), and when the drone's connection drops. After a start it is
also sent once more as an idempotent safety net.
"""
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import protocol as proto
from .link import DroneConn, Link
from .mission import Mission
from .safety import MIN_VOLTS, SafetyError, check_position, preflight


class MissionRejected(Exception):
    """The drone's checksum does not match the mission we sent."""

    def __init__(self, expected, got):
        super().__init__(f"Дрон не принял миссию: ждали контрольную сумму {expected}, получили {got}")
        self.expected, self.got = expected, got


class Aborted(Exception):
    pass


class ConnectionLost(Exception):
    pass


@dataclass
class Timing:
    """Pauses of the original scripts; tests shorten them."""
    telemetry_wait: float = 1.5     # settle before reading the first telemetry
    after_clear: float = 0.3
    between_steps: float = 0.02
    after_upload: float = 1.2
    poll: float = 0.1
    run_margin: float = 20.0        # seconds beyond the mission length before giving up
    land_wait: float = 2.0


def _wait_telemetry(conn: DroneConn, timing: Timing):
    time.sleep(timing.telemetry_wait)  # let the first telemetry frames arrive
    end = time.time() + 3
    t = conn.snapshot()
    while t is None and time.time() < end:
        time.sleep(0.05)
        t = conn.snapshot()
    return t


def upload_mission(conn: DroneConn, mission: Mission, timing: Timing = Timing(),
                   log: Callable[[str], None] = lambda m: None) -> int:
    """Clear, send all steps and verify the checksum. Returns the checksum the drone reports.
    Raises MissionRejected on a mismatch. Does not start anything."""
    conn.send(proto.clear_mission_frame())  # clear any old mission
    time.sleep(timing.after_clear)
    for f in mission.frames():
        conn.send(f)
        time.sleep(timing.between_steps)
    time.sleep(timing.after_upload)
    t = conn.snapshot()
    got = t.checksum if t else None
    expected = mission.checksum
    log(f"Контрольная сумма дрона {got}, ждали {expected}: {'совпала' if got == expected else 'НЕ совпала'}")
    if got != expected:
        raise MissionRejected(expected, got)
    return got


def start_mission(link: Link, conn: DroneConn, mission: Mission, *, arm: bool,
                  log: Callable[[str], None] = lambda m: None) -> int:
    """Send the start frame. Refuses unless arm=True and (for flying missions) the
    drone's IP is whitelisted. Returns the start tick."""
    if not arm:
        raise SafetyError("Дрон не взведён, старт отменён")
    if mission.can_fly and (not link.whitelist or conn.ip not in link.whitelist):
        raise SafetyError(f"IP {conn.ip} не в белом списке, старт отменён")
    t = conn.snapshot()
    if mission.can_fly:
        check_position(mission, t)      # cell moves: a position fix near the first cell, checked again at start
    tick = proto.start_tick(t.clock if t else 0, link.tick)
    conn.send(proto.start_frame(tick))
    log(f"Старт отправлен (t={tick})")
    return tick


def watch_mission(conn: DroneConn, mission: Mission, *, abort: Optional[threading.Event] = None,
                  land_flag: Optional[str] = None, timing: Timing = Timing(),
                  log: Callable[[str], None] = lambda m: None, time_limit: Optional[float] = None) -> str:
    """Watch a started mission. Returns "finished" or "timeout"; raises Aborted / ConnectionLost."""
    deadline = time.time() + (time_limit if time_limit is not None else mission.total_seconds + timing.run_margin)
    seen_running, last = False, None
    while time.time() < deadline:
        if conn.lost:
            raise ConnectionLost(f"Дрон {conn.ip} потерял связь")
        if (abort is not None and abort.is_set()) or (land_flag and os.path.exists(land_flag)):
            raise Aborted("Прервано оператором")
        t = conn.snapshot()
        if t:
            state = (t.running, t.z, t.battery_v)
            if state != last:
                last = state
                log(f"running={state[0]} z={state[1]} volts={state[2]}")
            seen_running |= bool(t.running)
            if seen_running and not t.running:
                log("Миссия завершена")
                return "finished"
        time.sleep(timing.poll)
    return "timeout"


@dataclass
class FlightResult:
    uploaded: bool = False
    started: bool = False
    outcome: str = ""            # "dry-run" | "finished" | "timeout"
    checksum: Optional[int] = None
    events: list = field(default_factory=list)


def run_mission(link: Link, ip: str, mission: Mission, *, go: bool = False,
                min_volts: float = MIN_VOLTS, max_height_cm: Optional[int] = None,
                hold: Optional[float] = None, abort: Optional[threading.Event] = None,
                land_flag: Optional[str] = None, timing: Timing = Timing(), log: Callable[[str], None] = print) -> FlightResult:
    """Full flow on one connected drone: preflight, upload, verify, (start, watch).

    Without go=True the mission is only uploaded and verified. For LED-only
    missions `hold` is how long to watch before sending the stop frame.
    Any failure after the drone is connected sends the emergency land frame.
    """
    result = FlightResult()
    conn = link.get(ip)
    if conn is None:
        raise ConnectionLost(f"Дрон {ip} не подключён")
    started = False
    try:
        t = _wait_telemetry(conn, timing)
        log(f"Телеметрия: {t.as_dict() if t else None}")
        preflight(mission, ip=ip, whitelist=link.whitelist, volts=t.battery_v if t else None,
                  min_volts=min_volts, max_height_cm=max_height_cm, telemetry=t)
        result.checksum = upload_mission(conn, mission, timing, log)
        result.uploaded = True
        if not go:
            result.outcome = "dry-run"
            log("Миссия загружена и проверена, моторы НЕ запущены (нет --go)")
            return result
        start_mission(link, conn, mission, arm=True, log=log)
        started = result.started = True
        if mission.can_fly:
            result.outcome = watch_mission(conn, mission, abort=abort, land_flag=land_flag,
                                           timing=timing, log=log)
        else:  # LED-only: watch for `hold` seconds, then stop
            watch_mission(conn, mission, abort=abort, land_flag=land_flag, timing=timing, log=log,
                          time_limit=hold if hold is not None else 8)
            conn.send(proto.stop_frame())
            log("Стоп отправлен")
            result.outcome = "finished"
        return result
    except BaseException as e:  # includes KeyboardInterrupt: land first, re-raise after
        log(f"Ошибка: {e!r}. Отправляю аварийную посадку")
        link.emergency_land(ip)
        raise
    finally:
        if started:
            for _ in range(3):  # idempotent safety net: land (no-op if already on the ground)
                try:
                    conn.send(proto.ALL_AUTOLAND)
                except OSError:
                    break
                time.sleep(0.1)
            log("all_autoLand отправлен как страховка")
            time.sleep(timing.land_wait)
