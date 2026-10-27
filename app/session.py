"""Bridges the window and the litebee core: link, per-drone state, upload/start workers.

Nothing here starts motors unless `start()` is called while `armed` is True,
and `armed` is reset after every flight and whenever a drone's link is lost.
"""
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal

from litebee import protocol as proto
from litebee.flight import (Aborted, ConnectionLost, MissionRejected, Timing, start_mission,
                            upload_mission, watch_mission)
from litebee.link import Link
from litebee.mission import DEFAULT_MAX_HEIGHT_CM, Mission, resolve_max_height
from litebee.safety import SafetyError, check_position, preflight

# card states (docs/UI_DESIGN.md)
NO_LINK, READY, LOADED, ARMED, FLYING, LANDING, ERROR = (
    "Нет связи", "Готов", "Миссия загружена", "Взведён", "Летит", "Посадка", "Ошибка")


@dataclass
class DroneView:
    ip: str
    state: str
    volts: Optional[float] = None
    z: Optional[int] = None
    running: bool = False
    x: Optional[int] = None
    y: Optional[int] = None
    has_fix: bool = False             # False for x = y = 0: no position on the mat
    cell: Optional[int] = None        # mat cell under the drone (None without a fix or off the mat)


class FlightController(QObject):
    log = Signal(str)
    changed = Signal()              # states / telemetry / link changed
    armed_changed = Signal(bool)
    busy_changed = Signal(bool)     # an upload or a flight is in progress

    def __init__(self, parent=None, timing: Timing = Timing()):
        super().__init__(parent)
        self.timing = timing
        self.max_height_cm = DEFAULT_MAX_HEIGHT_CM      # active height limit (the window sets it)
        self.link: Optional[Link] = None
        self.armed = False
        self.busy = False
        self.flying = False
        self.abort = threading.Event()
        self.loaded: Dict[str, Mission] = {}      # ip -> mission verified on the drone
        self.errors: Dict[str, str] = {}
        self.landing_until: Dict[str, float] = {}
        self._known = {}

    # ---- link --------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self.link is not None

    def connect_link(self, pc_ip: str, drone_ips, tcp_port: int, udp_port: int):
        """Start the link. Raises OSError when the TCP port is busy, ValueError on bad arguments."""
        self.disconnect_link()
        link = Link(pc_ip, tcp_port=tcp_port, udp_remote_port=udp_port,
                    whitelist=set(drone_ips) or None, announce_targets=list(drone_ips),
                    log=lambda m: self.log.emit(m))
        link.start()
        self.link = link
        self.changed.emit()

    def disconnect_link(self):
        if self.link:
            link, self.link = self.link, None
            link.close()
        self.loaded.clear()
        self._known.clear()
        self._set_armed(False)
        self.changed.emit()

    def drone_ips(self):
        if not self.link:
            return []
        return sorted(self.link.connections())

    def view(self, ip: str) -> DroneView:
        conn = self.link.get(ip) if self.link else None
        if conn is None or conn.lost:
            return DroneView(ip, NO_LINK)
        t = conn.snapshot()
        if ip in self.errors:
            state = ERROR
        elif self.landing_until.get(ip, 0) > time.time():
            state = LANDING
        elif self.flying and t and t.running:
            state = FLYING
        elif self.flying:
            state = FLYING
        elif ip in self.loaded:
            state = ARMED if self.armed else LOADED
        else:
            state = READY
        return DroneView(ip, state, t.battery_v if t else None, t.z if t else None, bool(t and t.running),
                         t.x if t else None, t.y if t else None, bool(t and t.has_fix), t.cell if t else None)

    def _register(self):
        """Remember the live connection objects, so a later loss (or silent replacement) is noticed."""
        if not self.link:
            return
        for ip, c in self.link.connections().items():
            if not c.lost and self._known.get(ip) is not c:
                self._known[ip] = c
                self.log.emit(f"Дрон {ip} в сети")

    def poll(self):
        """Called by a timer: detect lost links (reset arming), register new ones."""
        if not self.link:
            return
        lost = [ip for ip, c in self._known.items() if c.lost]
        for ip in lost:
            del self._known[ip]
            self.log.emit(f"Дрон {ip} потерял связь. Он садится, проверьте питание")
            self.loaded.pop(ip, None)
        if lost and self.armed:
            self._set_armed(False)
        self._register()
        self.changed.emit()

    # ---- arming ------------------------------------------------------------

    def _set_armed(self, value: bool):
        if self.armed != value:
            self.armed = value
            self.armed_changed.emit(value)

    def set_armed(self, value: bool):
        if value:
            self._register()        # so that losing a drone from now on disarms
        self._set_armed(bool(value) and self.connected)

    def _set_busy(self, value):
        self.busy = value
        self.busy_changed.emit(value)

    def set_max_height(self, value) -> int:
        """Set the height limit used by upload and start. SafetyError outside 20-200 cm."""
        self.max_height_cm = resolve_max_height(value)
        return self.max_height_cm

    # ---- upload ------------------------------------------------------------

    def upload(self, ip: str, mission: Mission, min_volts=None):
        """Verify battery, upload and check the checksum in a worker thread."""
        if self.busy:
            return
        self._set_busy(True)
        self.errors.pop(ip, None)
        threading.Thread(target=self._upload_worker, args=(ip, mission), daemon=True).start()

    def _upload_worker(self, ip, mission):
        try:
            conn = self.link.get(ip) if self.link else None
            if conn is None or conn.lost:
                raise ConnectionLost(f"Дрон {ip} не подключён")
            t = conn.snapshot()
            preflight(mission, ip=ip, whitelist=self.link.whitelist, volts=t.battery_v if t else None,
                      max_height_cm=self.max_height_cm, telemetry=t)
            upload_mission(conn, mission, self.timing, lambda m: self.log.emit(m))
            self.loaded[ip] = mission
            self.log.emit(f"Дрон {ip}: миссия загружена, контрольная сумма {mission.checksum} совпала")
        except MissionRejected as e:
            self.errors[ip] = str(e)
            self.log.emit(f"Дрон {ip}: миссия не принята. Ждали контрольную сумму {e.expected}, "
                          f"получили {e.got}. Загрузите ещё раз")
        except SafetyError as e:
            self.errors[ip] = str(e)
            self.log.emit(f"Дрон {ip}: {e}")
        except (ConnectionLost, OSError) as e:
            self.errors[ip] = str(e)
            self.log.emit(f"Дрон {ip} потерял связь во время загрузки. Проверьте питание и повторите")
        finally:
            self._set_busy(False)
            self.changed.emit()

    # ---- start -------------------------------------------------------------

    def start(self, ip: str):
        """Start the loaded mission. Refused unless armed. Runs and watches in a worker thread."""
        if self.busy or self.flying:
            return
        if not self.armed:
            self.log.emit("Дрон не взведён, старт отменён")
            return
        mission = self.loaded.get(ip)
        if mission is None:
            self.log.emit("Миссия не загружена, старт отменён")
            return
        conn = self.link.get(ip) if self.link else None
        try:                        # cell moves: the drone must still have a fix near the first cell
            check_position(mission, conn.snapshot() if conn else None)
        except SafetyError as e:
            self.log.emit(f"Дрон {ip}: {e}")
            return
        if mission.can_fly and mission.max_height_cm > self.max_height_cm:   # limit lowered after the upload
            self.log.emit(f"Высота {mission.max_height_cm} см больше лимита {self.max_height_cm} см. "
                          "Старт отменён, проверьте шоу и загрузите миссию ещё раз")
            return
        self.abort.clear()
        self._set_busy(True)
        self.flying = True
        threading.Thread(target=self._flight_worker, args=(ip, mission), daemon=True).start()
        self.changed.emit()

    def _flight_worker(self, ip, mission):
        conn = self.link.get(ip) if self.link else None
        started = False
        try:
            if conn is None:
                raise ConnectionLost(f"Дрон {ip} не подключён")
            start_mission(self.link, conn, mission, arm=self.armed, log=lambda m: self.log.emit(m))
            started = True
            if mission.can_fly:
                watch_mission(conn, mission, abort=self.abort, timing=self.timing, log=lambda m: self.log.emit(m))
            else:
                watch_mission(conn, mission, abort=self.abort, timing=self.timing, time_limit=8,
                              log=lambda m: self.log.emit(m))
                conn.send(proto.stop_frame())
        except Aborted:
            self.log.emit(f"Дрон {ip}: посадка по команде оператора")
            self._land(ip)
        except ConnectionLost:
            self.errors[ip] = "потеря связи"
            self.log.emit(f"Дрон {ip} потерял связь. Он садится, проверьте питание")
            self._land(ip)
        except SafetyError as e:
            self.errors[ip] = str(e)
            self.log.emit(f"Дрон {ip}: {e}")
            self._land(ip)
        except Exception as e:  # any other failure: land first, then report
            self.errors[ip] = repr(e)
            self.log.emit(f"Дрон {ip}: ошибка {e!r}. Отправляю посадку")
            self._land(ip)
        finally:
            if started:
                self._land(ip, quiet=True)          # idempotent safety net after every started mission
            self.loaded.pop(ip, None)               # re-upload before the next flight
            self.flying = False
            self._set_armed(False)                  # arming never survives a flight
            self._set_busy(False)
            self.changed.emit()

    def _land(self, ip, quiet=False):
        if self.link:
            self.landing_until[ip] = time.time() + 3
            self.link.emergency_land(ip)
        if not quiet:
            self.changed.emit()

    # ---- emergency ---------------------------------------------------------

    def emergency(self):
        """Land everything now. Always safe to call; with no drones it only resets the state."""
        self.abort.set()
        if self.link:
            ips = list(self.link.connections())
            for ip in ips:
                self.landing_until[ip] = time.time() + 3
            link = self.link
            threading.Thread(target=link.emergency_land, daemon=True).start()   # 3 frames per drone, no UI freeze
            self.log.emit(f"Аварийная посадка: кадр посадки отправляется дронам: {len(ips)}")
        else:
            self.log.emit("Аварийная посадка: дронов нет, симуляция остановлена")
        self._set_armed(False)
        self.changed.emit()

    def shutdown(self):
        self.abort.set()
        self.disconnect_link()
