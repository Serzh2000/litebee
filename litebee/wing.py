"""Fly a LiteBee Wing from Python through the USB remote: calibrate, take off, move by centimetres, land.

Messages are the ones LiteBee Go's `litebeeWing` extension sends (docs/PROTOCOL_SINGLE.md); they go to the remote as
FD FD len payload and the remote relays them to the drone. NONE OF THIS HAS FLOWN BEFORE: the byte layouts come from
reading LiteBee Go, not from a flight. Treat the first flights as experiments.

Safety, all enforced here:
  * the plan is checked before anything is sent (step size, number of steps);
  * before take-off the drone must be linked, flat, with a charged battery and the remote must be streaming data;
  * during the flight any of these lands the drone at once: LAND_NOW file, data silent for 1 s, a tilt over 30 degrees,
    a height over 130 cm, a battery under 6.6 V, Ctrl+C, an error;
  * after take-off the drone is sent down to the hover height (80 cm by default), because the plain take-off climbs
    to about a metre and a half (first flight, 2026-10-28);
  * `allow_commands=True` is needed on the link; the CLI only passes it with --go.
"""
import os
import struct
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from .remote import DataPackage, RemoteError, RemoteLink, to_remote
from .safety import MIN_VOLTS, SafetyError

MSG_CALIBRATE, MSG_TAKEOFF, MSG_LAND, MSG_MODE, MSG_POSITION = 10, 16, 17, 29, 30
MODE_HOLD = 2
SUB_MOVE_XY = 4

MAX_STEP_CM = 50                 # one relative move
MAX_MOVES = 6
MAX_FLAT_TILT_DEG = 10.0         # before take-off the drone must lie level
ABORT_TILT_DEG = 30.0            # first flight: 60 was too soft, the drone reached 45 degrees without an abort
ABORT_VOLTS = 6.6
MIN_HOVER_CM, MAX_HOVER_CM = 30, 120
DEFAULT_HOVER_CM = 80
CEILING_CM = 130                 # above this the flight is aborted (the first take-off climbed to 150 cm)
SILENCE_S = 1.0
DEFAULT_MIN_VOLTS = 7.4          # to start; MIN_VOLTS (7.0) is the floor nobody may lower


def calibrate_msg() -> bytes:
    return bytes([MSG_CALIBRATE])


def takeoff_msg() -> bytes:
    return bytes([MSG_TAKEOFF])


def land_msg() -> bytes:
    return bytes([MSG_LAND])


def hold_msg() -> bytes:
    """Hover where the drone is (mode_control 2)."""
    return bytes([MSG_MODE, MODE_HOLD] + [0] * 8)


def _cm(value, name) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SafetyError(f"{name}: расстояние должно быть целым числом см, получено {value!r}")
    if abs(value) > MAX_STEP_CM:
        raise SafetyError(f"{name}: {value} см больше предела одного шага {MAX_STEP_CM} см")
    return value


def height_msg(z_cm: int) -> bytes:
    """Fly to the height z (cm): LiteBee Go's setHigh, [pos_control, 2, int16 0, int16 0, int16 z]."""
    if isinstance(z_cm, bool) or not isinstance(z_cm, int) or not MIN_HOVER_CM <= z_cm <= MAX_HOVER_CM:
        raise SafetyError(f"Высота зависания должна быть целым от {MIN_HOVER_CM} до {MAX_HOVER_CM} см, получено {z_cm!r}")
    return bytes([MSG_POSITION, 2]) + struct.pack("<hhh", 0, 0, z_cm)


def move_msg(right_cm: int, forward_cm: int) -> bytes:
    """LiteBee Go's setMoveXY, [pos_control, 4, int16 X, int16 Y]. NOT USED: on 2026-10-28 two flights sent it and
    the drone did not move sideways at all (and climbed ~15 cm per command). Kept for the record."""
    return bytes([MSG_POSITION, SUB_MOVE_XY]) + struct.pack("<hh", _cm(right_cm, "вправо"), _cm(forward_cm, "вперёд"))


MSG_VELOCITY = 27
MAX_SPEED_CM_S = 25
DEFAULT_SPEED_CM_S = 15
MAX_MOVE_S = 6.0


def _speed(value, name) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or abs(value) > MAX_SPEED_CM_S:
        raise SafetyError(f"{name}: скорость должна быть целым не больше {MAX_SPEED_CM_S} см/с, получено {value!r}")
    return value & 0xFF                                # two's complement, as JavaScript's Buffer.from does


def velocity_msg(forward_cm_s: int = 0, right_cm_s: int = 0) -> bytes:
    """LiteBee Go's setDir: [vel_control, 2, 0, Y, X, 0]. Y forward (negative = backward), X right (negative = left).
    One message sets the speed until the next one; velocity_msg() stops."""
    return bytes([MSG_VELOCITY, 2, 0, _speed(forward_cm_s, "вперёд"), _speed(right_cm_s, "вправо"), 0])


def plan_move(right_cm: int, forward_cm: int, speed_cm_s: int = DEFAULT_SPEED_CM_S):
    """Turn a displacement into (forward speed, right speed, seconds): constant speed for distance / speed seconds."""
    _cm(right_cm, "вправо"), _cm(forward_cm, "вперёд")
    if not right_cm and not forward_cm:
        raise SafetyError("Сдвиг нулевой")
    if isinstance(speed_cm_s, bool) or not isinstance(speed_cm_s, int) or not 5 <= speed_cm_s <= MAX_SPEED_CM_S:
        raise SafetyError(f"Скорость должна быть целым от 5 до {MAX_SPEED_CM_S} см/с, получено {speed_cm_s!r}")
    dist = (right_cm ** 2 + forward_cm ** 2) ** 0.5
    seconds = dist / speed_cm_s
    if seconds > MAX_MOVE_S:
        raise SafetyError(f"Шаг займёт {seconds:.1f} с, допускается не больше {MAX_MOVE_S:g} с")
    return round(speed_cm_s * forward_cm / dist), round(speed_cm_s * right_cm / dist), seconds


class FlightAbort(Exception):
    pass


@dataclass
class WingTiming:
    calibrate_s: float = 4.0
    takeoff_s: float = 5.0
    height_s: float = 4.0
    settle_s: float = 1.0
    move_s: float = 4.0
    land_s: float = 6.0
    step_s: float = 0.05


DEFAULT_TIMING = WingTiming()


def check_plan(moves: List[Tuple[int, int]]):
    if not moves:
        raise SafetyError("В плане нет ни одного шага движения")
    if len(moves) > MAX_MOVES:
        raise SafetyError(f"В плане {len(moves)} шагов, допускается не больше {MAX_MOVES}")
    for right, forward in moves:
        plan_move(right, forward)                     # validates each number


class WingFlight:
    def __init__(self, link: RemoteLink, *, land_flag: Optional[str] = None, min_volts: float = DEFAULT_MIN_VOLTS,
                 hover_cm: int = DEFAULT_HOVER_CM, speed_cm_s: int = DEFAULT_SPEED_CM_S,
                 timing: Optional[WingTiming] = None, log: Callable[[str], None] = print):
        if min_volts < MIN_VOLTS:
            raise SafetyError(f"Порог батареи нельзя ставить ниже {MIN_VOLTS} В")
        height_msg(hover_cm)                          # validates
        plan_move(0, 10, speed_cm_s)                  # validates the speed
        self.hover_cm = hover_cm
        self.speed_cm_s = speed_cm_s
        self.link = link
        self.land_flag = land_flag
        self.min_volts = min_volts
        self.timing = timing or DEFAULT_TIMING
        self.log = log
        self.airborne = False
        self.landed = False
        self._last_count = 0
        self._last_change = None

    # ---- checks ----------------------------------------------------------------------------------------

    def preflight(self) -> DataPackage:
        """Raise SafetyError unless the drone is linked, flat, charged and the data stream is alive."""
        link = self.link
        if not link.acked and not link.handshake():
            raise SafetyError("Пульт не ответил на приветствие. Закройте LiteBee Go и проверьте кабель")
        v = link.request_version()
        if v is None or not v.fv:
            raise SafetyError("Пульт не видит дрон: версия дрона неизвестна. Привяжите дрон к пульту")
        d = link.request_data()
        if d is None:
            raise SafetyError("Пульт не присылает данные. Переведите его в режим программирования (L4 зелёный)")
        link.run(0.4)
        n0 = link.data_count
        link.run(0.4)
        if link.data_count == n0:
            raise SafetyError("Поток данных остановился")
        d = link.last_data
        if d.is_empty:
            raise SafetyError("Пакет данных нулевой: пульт не видит дрон")
        if d.voltage < self.min_volts:
            raise SafetyError(f"Батарея {d.voltage:.1f} В ниже порога {self.min_volts:.1f} В: зарядите дрон")
        if abs(d.roll_deg) > MAX_FLAT_TILT_DEG or abs(d.pitch_deg) > MAX_FLAT_TILT_DEG:
            raise SafetyError(f"Дрон лежит не ровно (крен {d.roll_deg}°, тангаж {d.pitch_deg}°): положите его ровно")
        if self.land_flag and os.path.exists(self.land_flag):
            raise SafetyError(f"Есть файл {self.land_flag}: удалите его")
        return d

    def _check_in_flight(self):
        link = self.link
        if self.land_flag and os.path.exists(self.land_flag):
            raise FlightAbort("появился файл LAND_NOW")
        now = link._clock()
        if self._last_change is None or link.data_count != self._last_count:
            self._last_count, self._last_change = link.data_count, now
        elif now - self._last_change > SILENCE_S:
            raise FlightAbort("поток данных остановился")
        d = link.last_data
        if d is None:
            return
        if abs(d.roll_deg) > ABORT_TILT_DEG or abs(d.pitch_deg) > ABORT_TILT_DEG:
            raise FlightAbort(f"наклон {d.roll_deg}°/{d.pitch_deg}°: дрон перевернулся или сильно накренился")
        if 0 < d.voltage < ABORT_VOLTS:
            raise FlightAbort(f"батарея упала до {d.voltage:.1f} В")
        if d.pos[2] > CEILING_CM:
            raise FlightAbort(f"высота {d.pos[2]} см выше потолка {CEILING_CM} см")

    # ---- sending ---------------------------------------------------------------------------------------

    def _send(self, name: str, payload: bytes):
        self.log(f"-> {name}")
        self.link.send_message(payload)

    def _wait(self, seconds: float, check: bool = True):
        end = self.link._clock() + seconds
        while self.link._clock() < end:
            self.link.run(self.timing.step_s)
            if check:
                self._check_in_flight()
        self._log_state()

    def _log_state(self):
        d = self.link.last_data
        if d:
            x, y, z = d.pos
            self.log(f"   положение ({x}, {y}, {z}), углы крен {d.roll_deg}° тангаж {d.pitch_deg}° "
                     f"рыскание {d.yaw_deg}°, батарея {d.voltage:.1f} В")

    # ---- the flight ------------------------------------------------------------------------------------

    def land(self, why: str = "по плану"):
        """Land, repeating the command; safe to call twice."""
        if self.landed:
            return
        self.log(f"Посадка ({why})")
        try:
            self._send("стоп (скорость 0)", velocity_msg())
        except RemoteError:
            pass
        for _ in range(3):
            try:
                self._send("посадка", land_msg())
            except RemoteError:
                break
            self._wait(0.2, check=False)
        self._wait(self.timing.land_s, check=False)
        self.landed, self.airborne = True, False

    def fly(self, moves: List[Tuple[int, int]]):
        """Calibrate, take off, hold, make the moves one by one, land. Always lands, also on any failure."""
        check_plan(moves)
        t = self.timing
        self.preflight()
        self.log("Проверки пройдены, дрон связан, лежит ровно")
        try:
            self._send("калибровка", calibrate_msg())
            self._wait(t.calibrate_s, check=False)
            self._send("взлёт", takeoff_msg())
            self.airborne = True
            self._wait(t.takeoff_s)
            self._send(f"высота {self.hover_cm} см", height_msg(self.hover_cm))
            self._wait(t.height_s)
            self._send("зависание", hold_msg())
            self._wait(t.settle_s)
            for i, (right, forward) in enumerate(moves, 1):
                fwd_v, right_v, seconds = plan_move(right, forward, self.speed_cm_s)
                self._send(f"шаг {i}: вправо {right} см, вперёд {forward} см "
                           f"(скорость вперёд {fwd_v}, вправо {right_v} см/с, {seconds:.1f} с)",
                           velocity_msg(fwd_v, right_v))
                self._wait(seconds)
                self._send("стоп", velocity_msg())
                self._wait(t.settle_s)
        except (FlightAbort, KeyboardInterrupt) as e:
            self.log(f"АВАРИЙНАЯ ПОСАДКА: {e or 'прервано'}")
            self.land("аварийная")
            raise
        except Exception as e:
            self.log(f"АВАРИЙНАЯ ПОСАДКА: ошибка {e!r}")
            self.land("ошибка")
            raise
        self.land()
        self.log("Готово")
