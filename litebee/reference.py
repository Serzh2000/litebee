"""Function reference of the show DSL: the single source of truth for the IDE help.

Everything the IDE shows about the DSL (the "Справочник" panel, editor tooltips and completion
hints) is read from here. Entries describe the real methods of `litebee.show.Show` and
`litebee.show.Drone`; tests/test_reference.py fails when a public method has no entry, when an
entry names a method that does not exist, when a signature differs from the code, and when a
status contradicts `mission.PROVEN_CMDS` or what `drone_to_mission` really accepts.

Facts here are the facts of docs/DESIGN.md: only what was proven on live drones is called
proven. Nothing in this module talks to a drone.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from .mission import (CELL_CM, CMD_AUTOLAND, CMD_CALIBRATE, CMD_CIRCLE, CMD_MOVEXY, CMD_MOVEXYZ, CMD_MOVEZ,
                      CMD_RGB, CMD_TAKEOFF, COLORS, DEFAULT_MAX_HEIGHT_CM, GRID_CELLS, GRID_W,
                      HARD_MAX_HEIGHT_CM, MAX_HOVER_S, MIN_TAKEOFF_CM)
from .safety import MAX_LEG_SPEED_CM_S, MAX_START_DISTANCE_CM, MIN_APPROACH_CM, MIN_VOLTS, WARN_VOLTS

STATUS_VERIFIED = "проверено на дроне"
STATUS_SIM = "только симулятор"
STATUS_HELPER = "служебная функция"       # not a drone command: nothing is sent to a drone
STATUS_ABSENT = "нет в IDE"               # a formation command with no DSL function (commands table only)
STATUS_ICON = {STATUS_VERIFIED: "✓", STATUS_SIM: "△", STATUS_HELPER: "•", STATUS_ABSENT: "–"}
STATUS_HINT = {
    STATUS_VERIFIED: "Шаг выполнялся на живых дронах, IDE умеет его загружать",
    STATUS_SIM: "Работает в симуляции. Формат шага на проводе не проверен, IDE отказывается его загружать",
    STATUS_HELPER: "Не команда дрона: нужна для описания шоу и отчёта симулятора",
    STATUS_ABSENT: "В IDE нет такой функции, формат шага не проверен",
}

# Formation command ids (LiteBee Go list) -> (name, DSL functions, status).
# Ids 4, 6-9, 11 and 51 have no DSL function: their wire layout is unknown.
COMMANDS = (
    (CMD_CALIBRATE, "calibrate", ("calibrate",), STATUS_VERIFIED),
    (CMD_TAKEOFF, "takeOff", ("takeoff",), STATUS_VERIFIED),
    (CMD_AUTOLAND, "autoLand", ("land",), STATUS_VERIFIED),
    (CMD_MOVEXY, "moveXY", ("code", "code_s"), STATUS_VERIFIED),
    (4, "speed", (), STATUS_ABSENT),
    (CMD_MOVEZ, "moveZ", ("set_z",), STATUS_VERIFIED),
    (6, "yaw", (), STATUS_ABSENT),
    (7, "local360", (), STATUS_ABSENT),
    (8, "flip", (), STATUS_ABSENT),
    (9, "jump", (), STATUS_ABSENT),
    (CMD_MOVEXYZ, "moveXYZ", ("code_z",), STATUS_SIM),
    (11, "atti", (), STATUS_ABSENT),
    (CMD_CIRCLE, "circle", ("circle",), STATUS_SIM),
    (13, "circleAlt", ("circle_z",), STATUS_SIM),
    (CMD_RGB, "RGB", ("rgb", "rgb_value"), STATUS_VERIFIED),
    (51, "int", (), STATUS_ABSENT),
)
CMD_ID_BY_NAME = {name: cid for cid, name, _, _ in COMMANDS}

TOPICS = (
    ("basics", "Основы"),
    ("show", "Шоу"),
    ("motion", "Движение"),
    ("light", "Свет"),
    ("sim", "Симулятор и отчёт"),
)
TOPIC_TITLE = dict(TOPICS)


@dataclass(frozen=True)
class Param:
    name: str
    unit: str          # "см", "с", "клетка 0..143", "цвет", ...
    text: str


@dataclass(frozen=True)
class Entry:
    """One method (or property, or class) of the DSL."""
    owner: str                      # "Show" or "Drone"
    name: str                       # attribute name; equals owner for the class itself
    kind: str                       # "class" | "method" | "property"
    signature: str                  # as in code, without self: takeoff(z, seconds)
    summary: str                    # one line, Russian
    topic: str                      # id from TOPICS
    status: str
    params: Tuple[Param, ...] = ()
    example: str = ""
    context: str = "drone"          # what the example assumes: "drone" (d), "show" (show) or "full" (nothing)
    notes: Tuple[str, ...] = ()
    command: Optional[str] = None   # formation command name, e.g. "moveXY"
    dsl: bool = True                # False for simulator helpers (not meant for show authors)
    official: Optional[str] = None  # LiteBee Go function, e.g. "litebeeWingFormation_takeOff"
    article: bool = False

    @property
    def key(self):
        return f"{self.owner}.{self.name}"

    @property
    def label(self):
        """What the list shows: the bare name for show commands, owner-qualified otherwise."""
        if self.name == self.owner:
            return self.name
        return self.name if self.owner == "Drone" and self.dsl else f"{self.owner}.{self.name}"

    @property
    def cmd_id(self):
        return CMD_ID_BY_NAME.get(self.command) if self.command else None

    @property
    def command_text(self):
        return f"{self.command} ({self.cmd_id})" if self.command else ""

    @property
    def icon(self):
        return STATUS_ICON[self.status]


@dataclass(frozen=True)
class Section:
    heading: str
    lines: tuple = ()
    style: str = "p"                # "p" paragraphs | "ul" bullets | "ol" numbered | "table"
    header: tuple = ()              # column titles of a table


@dataclass(frozen=True)
class Article:
    """A topic page: no code behind it, text only (plus an optional runnable example)."""
    key: str
    title: str
    summary: str
    topic: str
    sections: Tuple[Section, ...]
    example: str = ""
    context: str = "full"
    article: bool = True

    @property
    def label(self):
        return self.title

    @property
    def name(self):
        return self.title

    @property
    def status(self):
        return None

    @property
    def icon(self):
        return ""


def _volts(v):
    return f"{v:.1f}".replace(".", ",")


def _p(*names_units_texts):
    return tuple(Param(*t) for t in names_units_texts)


_CELL = "клетка 0..%d" % (GRID_CELLS - 1)
_CELL_NOTE = f"Клетка = столбец + {GRID_W} × строка, например 97 = столбец 1, строка 8 (подробнее в «Коврик и координаты»)"

ENTRIES = (
    # ---- Show -------------------------------------------------------------------------------
    Entry("Show", "Show", "class", "Show(name)",
          "Создаёт шоу: набор дронов, у каждого своя программа", "show", STATUS_HELPER,
          params=_p(("name", "текст", "Имя шоу, попадает в отчёт проверки")),
          example=("from litebee import Show\n\nshow = Show('Мой полёт')\nd = show.drone(1)\n"
                   "d.calibrate(5)\nd.takeoff(100, 5)\nd.land()\n"),
          context="full",
          notes=("Файл шоу обязан создать переменную show = Show('имя'): IDE берёт шоу из неё",
                 "Старые файлы с from litebee_show import Show тоже работают",
                 "Код шоу выполняется в отдельном процессе не дольше 5 с, шагов не больше 10000")),
    Entry("Show", "drone", "method", "drone(number)",
          "Возвращает дрона с этим номером, при первом обращении создаёт его", "show", STATUS_HELPER,
          params=_p(("number", "номер", "Номер дрона. В LiteBee Go номера от 1 до 16")),
          example="d = show.drone(1)\nd.rgb('green')\n", context="show",
          notes=("Повторный вызов с тем же номером возвращает того же дрона",
                 "Методы дрона можно соединять в цепочку: каждый возвращает самого дрона",
                 "Загружается в дрон один дрон за раз: несколько дронов не проверялись на живых")),

    # ---- motion -----------------------------------------------------------------------------
    Entry("Drone", "calibrate", "method", "calibrate(seconds)",
          "Калибровка дрона перед взлётом", "motion", STATUS_VERIFIED,
          params=_p(("seconds", "с", "Длительность шага. В примерах LiteBee Go — 5 с")),
          example="d.calibrate(5)\n", command="calibrate", official="litebeeWingFormation_calibration",
          notes=("Обычно первый шаг программы дрона",
                 "Калибровка не даёт позицию по коврику: перед движением по клеткам нужен короткий взлёт "
                 "(см. «Рабочая последовательность»)")),
    Entry("Drone", "takeoff", "method", "takeoff(z, seconds)",
          "Взлёт на высоту z", "motion", STATUS_VERIFIED,
          params=_p(("z", "см", f"Высота над полом. Не больше лимита высоты ({DEFAULT_MAX_HEIGHT_CM} см по "
                                f"умолчанию, потолок {HARD_MAX_HEIGHT_CM} см)"),
                    ("seconds", "с", "Время на подъём")),
          example="d.takeoff(100, 5)\n", command="takeOff", official="litebeeWingFormation_takeOff",
          notes=("Позиция по коврику появляется в полёте примерно на 30 см и остаётся после посадки",
                 "В симуляции подъём идёт по прямой с постоянной скоростью")),
    Entry("Drone", "land", "method", "land()",
          "Посадка", "motion", STATUS_VERIFIED,
          example="d.takeoff(100, 5)\nd.land()\n", command="autoLand", official="litebeeWingFormation_autoLand",
          notes=("В симуляции посадка занимает 3 с. В загруженной миссии шаг не добавляет времени: "
                 "после него дрон садится сам",
                 "Это шаг шоу. Аварийная посадка всех дронов — кнопка в окне и клавиша Esc, "
                 "а не функция шоу")),
    Entry("Drone", "set_z", "method", "set_z(z, seconds)",
          "Перейти на высоту z. На той же высоте это зависание", "motion", STATUS_VERIFIED,
          params=_p(("z", "см", f"Новая высота. Не больше лимита высоты ({DEFAULT_MAX_HEIGHT_CM} см по умолчанию)"),
                    ("seconds", "с", "Время шага")),
          example="d.set_z(120, 3)   # подняться до 120 см\nd.set_z(120, 2)   # повисеть 2 с\n",
          command="moveZ", official="litebeeWingFormation_setZ",
          notes=(f"Зависание (set_z на текущей высоте) не дольше {MAX_HOVER_S} с, иначе проверка откажет",)),
    Entry("Drone", "code", "method", "code(cell, seconds)",
          "Лететь к клетке коврика по прямой", "motion", STATUS_VERIFIED,
          params=_p(("cell", _CELL, "Номер клетки: столбец + 12 × строка"),
                    ("seconds", "с", "Время перехода")),
          example="d.code(97, 4)   # к клетке 97 за 4 с\n", command="moveXY",
          official="litebeeWingFormation_code",
          notes=(_CELL_NOTE,
                 "Движение абсолютное: дрон летит к клетке откуда бы ни стартовал. Поэтому до загрузки ему нужна "
                 "позиция по коврику, а стоять он должен не дальше "
                 f"{MAX_START_DISTANCE_CM:.0f} см от первой клетки движения",
                 "Точность около ±10-15 см, перелёт до ~20 см",
                 f"Средняя скорость выше {MAX_LEG_SPEED_CM_S:.0f} см/с даёт предупреждение: дрон может перелететь клетку",
                 "В симуляции высота не меняется")),
    Entry("Drone", "code_s", "method", "code_s(cells, seconds)",
          "Пролететь несколько клеток подряд", "motion", STATUS_VERIFIED,
          params=_p(("cells", _CELL, "Список [12, 23, 27] или строка '12 23 27'"),
                    ("seconds", "с", "Время на весь путь: делится поровну между клетками")),
          example="d.code_s('12 23 27', 6)   # по 2 с на каждую клетку\n", command="moveXY",
          official="litebeeWingFormation_codeS",
          notes=("Раскладывается на шаги code, поэтому статус и ограничения как у code",
                 "Пустой список даёт ошибку")),
    Entry("Drone", "code_z", "method", "code_z(cell, z, seconds)",
          "Лететь к клетке и одновременно на высоту z", "motion", STATUS_SIM,
          params=_p(("cell", _CELL, "Номер клетки"),
                    ("z", "см", "Высота в конце шага (итоговая, не прирост)"),
                    ("seconds", "с", "Время шага")),
          example="d.code_z(66, 120, 10)\n", command="moveXYZ", official="litebeeWingFormation_codeZ",
          notes=("Загрузка в дрон отказывает: формат шага на проводе не проверен",
                 "В симуляции z — итоговая высота. Шоу из LiteBee Go чередуют 130 и 80 см, значит это не прирост",
                 "Формулировка официального описания («升高的高度») двусмысленна")),
    Entry("Drone", "circle", "method", "circle(count, cell1, cell2, seconds, rotate='cw')",
          "Круг вокруг середины между двумя клетками", "motion", STATUS_SIM,
          params=_p(("count", "полукругов", "Сколько полукругов. 2 полукруга — полный круг, дрон вернётся на место"),
                    ("cell1", _CELL, "Первая клетка: вместе со второй задаёт центр"),
                    ("cell2", _CELL, "Вторая клетка. Центр — середина отрезка между клетками"),
                    ("seconds", "с", "Время на весь круг"),
                    ("rotate", "'cw' | 'ccw'", "Направление. Допустимы и числа: 0 — по часовой, 1 — против")),
          example="d.circle(2, 66, 77, 15)   # полный круг за 15 с\n", command="circle",
          official="litebeeWingFormation_circle",
          notes=("Загрузка в дрон отказывает: формат шага на проводе не проверен",
                 "Радиус — расстояние от текущей позиции дрона до центра",
                 "Куда на коврике поворачивает 'cw', в симуляции угадано")),
    Entry("Drone", "circle_z", "method", "circle_z(cell1, cell2, dz, seconds, rotate='cw')",
          "Полкруга с подъёмом на dz", "motion", STATUS_SIM,
          params=_p(("cell1", _CELL, "Первая клетка центра"),
                    ("cell2", _CELL, "Вторая клетка центра"),
                    ("dz", "см", "На сколько подняться за полкруга (прирост)"),
                    ("seconds", "с", "Время шага"),
                    ("rotate", "'cw' | 'ccw'", "Направление, как у circle")),
          example="d.circle_z(66, 77, 50, 15)\n", command="circleAlt", official="litebeeWingFormation_circleZ",
          notes=("Загрузка в дрон отказывает: формат шага на проводе не проверен",
                 "Всегда ровно полкруга",
                 "Итоговая высота не должна превысить лимит высоты")),

    # ---- light ------------------------------------------------------------------------------
    Entry("Drone", "rgb", "method", "rgb(color)",
          "Цвет светодиода", "light", STATUS_VERIFIED,
          params=_p(("color", "цвет", "Имя: " + ", ".join(COLORS) + "; номер 0..7 в том же порядке; "
                                       "или тройка (r, g, b) со значениями 0..255")),
          example="d.rgb('green')\nd.rgb(4)            # синий\nd.rgb((255, 128, 0))\n", command="RGB",
          official="litebeeWingFormation_RGB",
          notes=("Шаг без длительности: цвет меняется в этот момент и держится до следующего rgb",
                 "До первого rgb светодиод в симуляции выключен",
                 "Работает без взлёта: проверить цвет можно на столе. На живых дронах проверены 8 имён цветов",
                 "Неизвестное имя даёт ошибку и список допустимых")),
    Entry("Drone", "rgb_value", "method", "rgb_value(r, g, b)",
          "Цвет светодиода по яркости каналов", "light", STATUS_VERIFIED,
          params=_p(("r", "0..255", "Красный"), ("g", "0..255", "Зелёный"), ("b", "0..255", "Синий")),
          example="d.rgb_value(255, 128, 0)\n", command="RGB", official="litebeeWingFormation_RGBValue",
          notes=("То же, что rgb((r, g, b)): тот же шаг RGB. На живых дронах проверены только 8 именованных цветов",
                 "Значение вне 0..255 даёт ошибку")),

    # ---- simulator helpers ------------------------------------------------------------------
    Entry("Show", "duration", "property", "duration",
          "Длительность шоу, с: у самого долгого дрона", "sim", STATUS_HELPER, dsl=False,
          example="print(show.duration)\n", context="show"),
    Entry("Show", "step_count", "property", "step_count",
          "Число шагов всех дронов вместе", "sim", STATUS_HELPER, dsl=False,
          example="print(show.step_count)\n", context="show",
          notes=("Больше 10000 шагов IDE отклоняет",)),
    Entry("Show", "paths", "method", "paths()",
          "Траектории всех дронов: словарь номер → отрезки (t0, t1, p0, p1, вид, шаг)", "sim", STATUS_HELPER,
          dsl=False, example="d = show.drone(1)\nd.takeoff(100, 5)\nprint(show.paths()[1][0])\n", context="show",
          notes=("Точки — (x, y, z) в см. Модель приблизительная: старт под первой клеткой, прямые с постоянной скоростью",)),
    Entry("Show", "positions_at", "method", "positions_at(t, paths=None)",
          "Позиции всех дронов в момент t", "sim", STATUS_HELPER,
          params=_p(("t", "с", "Время от начала шоу"), ("paths", "—", "Готовые траектории из paths(), необязательно")),
          dsl=False, example="print(show.positions_at(3.0))\n", context="show"),
    Entry("Show", "closest_approaches", "method", "closest_approaches(step=0.1, top=5)",
          "Самые близкие сближения пар дронов", "sim", STATUS_HELPER,
          params=_p(("step", "с", "Шаг по времени при поиске"), ("top", "число", "Сколько худших пар вернуть")),
          dsl=False, example="print(show.closest_approaches())\n", context="show",
          notes=(f"Возвращает (расстояние в см, время в с, дрон, дрон). Порог предупреждения в проверке — "
                 f"{MIN_APPROACH_CM:.0f} см",)),
    Entry("Show", "report", "method", "report()",
          "Текстовый отчёт: дроны, шаги, время, ближайшие пары", "sim", STATUS_HELPER, dsl=False,
          example="print(show.report())\n", context="show",
          notes=("То же, что показывает вкладка «Отчёт»",)),
    Entry("Drone", "duration", "property", "duration",
          "Длительность программы дрона, с", "sim", STATUS_HELPER, dsl=False,
          example="print(d.duration)\n", notes=("Сумма времён всех шагов дрона",)),
    Entry("Drone", "path", "method", "path()",
          "Траектория дрона: отрезки (t0, t1, p0, p1, вид, номер шага)", "sim", STATUS_HELPER, dsl=False,
          example="d.takeoff(100, 5)\nprint(d.path())\n"),
    Entry("Drone", "position_at", "method", "position_at(t, path=None)",
          "Позиция (x, y, z) дрона в момент t", "sim", STATUS_HELPER,
          params=_p(("t", "с", "Время от начала программы дрона"), ("path", "—", "Готовая траектория, необязательно")),
          dsl=False, example="d.takeoff(100, 5)\nprint(d.position_at(2.5))\n"),
    Entry("Drone", "step_at", "method", "step_at(t)",
          "Шаг, который дрон выполняет в момент t", "sim", STATUS_HELPER,
          params=_p(("t", "с", "Время от начала программы дрона"),), dsl=False,
          example="d.takeoff(100, 5)\nprint(d.step_at(2.5))\n",
          notes=("Для пустой программы возвращает None",)),
    Entry("Drone", "color_at", "method", "color_at(t)",
          "Цвет светодиода (имя, (r, g, b)) в момент t", "sim", STATUS_HELPER,
          params=_p(("t", "с", "Время от начала программы дрона"),), dsl=False,
          example="d.rgb('red')\nprint(d.color_at(1.0))\n",
          notes=("До первого rgb светодиод выключен: ('black', (0, 0, 0))",)),
)

_HOP_EXAMPLE = ("from litebee import Show\n\nshow = Show('Короткий взлёт')\nd = show.drone(1)\n"
                "d.calibrate(5)\nd.takeoff(50, 5)   # 50 см: дрон получает позицию по коврику\nd.land()\n")


def _commands_table():
    rows = []
    for cid, name, funcs, status in COMMANDS:
        rows.append((str(cid), name, ", ".join(funcs) if funcs else "—", f"{STATUS_ICON[status]} {status}"))
    return tuple(rows)


ARTICLES = (
    Article(
        "mat", "Коврик и координаты",
        "Клетки коврика, оси, позиция дрона и точность", "basics",
        (
            Section("Клетки", (
                f"Коврик — сетка {GRID_W}×{GRID_W} клеток по {CELL_CM} см, всего {GRID_CELLS} клетки (номера 0..{GRID_CELLS - 1}).",
                f"Номер клетки = столбец + {GRID_W} × строка. Например, клетка 97: столбец 1, строка 8.",
                "Номера растут вправо (столбец, ось x) и вверх (строка, ось y).",
                f"Центр клетки: x = {CELL_CM} × столбец, y = {CELL_CM} × строка, в см. Клетка 97: x = 40, y = 320.",
            )),
            Section("Как это видит дрон", (
                f"Шаг движения хранит абсолютные координаты коврика в см. Первое значение — строка (ось y), "
                f"второе — столбец (ось x); IDE упаковывает это сама.",
                "Дрон двигается к клетке откуда бы ни стартовал, а не на столько-то клеток от себя.",
            ), "ul"),
            Section("Позиция", (
                "Только что включённый дрон сообщает x = y = 0 на земле. Это значит «позиции нет», а не «клетка 0».",
                "Позиция появляется в полёте примерно на 30 см и остаётся после посадки. Одна калибровка позицию не даёт.",
                "Без позиции дрон прерывает миссию с движением по клеткам через ~3 с, не взлетев.",
            ), "ul"),
            Section("Точность, время, высота", (
                "Точность по коврику около ±10-15 см, перелёт до ~20 см.",
                "Высоты — в сантиметрах.",
                "Время шага в шоу — длительность этого шага в секундах. В загруженной миссии хранится накопленное "
                "время конца шага в долях 0,1 с: IDE считает его сама.",
            ), "ul"),
        ),
        example="d.code(97, 4)   # клетка 97: столбец 1, строка 8\n", context="drone",
    ),
    Article(
        "safety", "Безопасность",
        "Лимиты высоты и батареи, позиция, расстояния, аварийная посадка", "basics",
        (
            Section("Лимиты, которые проверяет IDE", (
                f"Высота: по умолчанию не больше {DEFAULT_MAX_HEIGHT_CM} см. Поле «Лимит высоты» на панели инструментов "
                f"меняет лимит от {MIN_TAKEOFF_CM} до {HARD_MAX_HEIGHT_CM} см; выше {HARD_MAX_HEIGHT_CM} см нельзя ни "
                "в окне, ни из командной строки. После смены лимита нажмите «Проверить» ещё раз.",
                f"Зависание (set_z на той же высоте) не дольше {MAX_HOVER_S} с.",
                f"Батарея: старт запрещён ниже {_volts(MIN_VOLTS)} В, порог нельзя снизить. Ниже {_volts(WARN_VOLTS)} В карточка "
                "дрона янтарная.",
                f"Сближение дронов меньше {MIN_APPROACH_CM:.0f} см даёт предупреждение.",
                f"Скорость перехода code и code_z выше {MAX_LEG_SPEED_CM_S:.0f} см/с (средняя) даёт предупреждение: "
                "дрон может перелететь клетку.",
                "Загружаются только шаги, проверенные на живых дронах. Остальные работают лишь в симуляции.",
            ), "ul"),
            Section("Позиция перед движением по клеткам", (
                "Дрону нужна позиция по коврику. Сначала короткий взлёт на 50 см (см. «Рабочая последовательность»), "
                "потом загрузка миссии.",
                f"Дрон должен стоять не дальше {MAX_START_DISTANCE_CM:.0f} см от первой клетки движения: его движение "
                "абсолютное, неверная стартовая клетка отправила бы его через весь коврик.",
                "Без позиции или при большом расстоянии «Загрузить» и «Старт» неактивны, подсказка говорит, что делать.",
            ), "ul"),
            Section("Аварийная посадка", (
                "Красная кнопка «Аварийная посадка» всегда внизу справа. Клавиша Esc садит дроны, пока дрон взведён или летит.",
                "При ошибке и потере связи окно само отправляет посадку и пишет в журнал, что произошло.",
                "Полёт возможен только дронам из белого списка IP, после «Проверить» и «Взвести».",
            ), "ul"),
        ),
    ),
    Article(
        "workflow", "Рабочая последовательность",
        "От свежей батареи до полёта по клеткам", "basics",
        (
            Section("Шаги", (
                f"Свежая батарея: старт запрещён ниже {_volts(MIN_VOLTS)} В.",
                f"Поставьте дрон на коврик рядом с первой клеткой движения в шоу (не дальше {MAX_START_DISTANCE_CM:.0f} см, "
                "лучше на ней).",
                "Короткий взлёт на 50 см, чтобы дрон получил позицию: пример ниже или команда hop с высотой 50. "
                "Позиция остаётся после посадки.",
                "Убедитесь, что в карточке дрона появилась «Клетка N» и это нужная клетка.",
                "Нажмите «Проверить», «Загрузить», отметьте «Взвести», нажмите «Старт».",
                "Не переносите дрон между загрузкой и стартом: позиция проверяется при старте ещё раз.",
            ), "ol"),
            Section("Помните", (
                "Одна калибровка позиции не даёт: без неё дрон прервёт миссию с движением по клеткам через ~3 с.",
                "Точность около ±10-15 см, перелёт до ~20 см: не планируйте проходы с зазором меньше.",
                "Одновременно загружается и стартует один дрон.",
            ), "ul"),
        ),
        example=_HOP_EXAMPLE,
    ),
    Article(
        "commands", "Команды формации",
        "Какая функция IDE какой команде LiteBee Go соответствует и что проверено", "basics",
        (
            Section("Таблица", _commands_table(), "table", header=("№", "Команда", "Функции IDE", "Статус")),
            Section("Что значит статус", (
                f"{STATUS_ICON[STATUS_VERIFIED]} {STATUS_VERIFIED} — шаг выполнялся на живых дронах, IDE его загружает.",
                f"{STATUS_ICON[STATUS_SIM]} {STATUS_SIM} — работает в симуляции, загрузка отказывает: формат шага на "
                "проводе не проверен.",
                f"{STATUS_ICON[STATUS_ABSENT]} {STATUS_ABSENT} — команда есть в списке формации, функции в IDE нет.",
            ), "ul"),
        ),
    ),
)

ITEMS = tuple(ENTRIES) + tuple(ARTICLES)


def items():
    """Everything the panel lists, in display order: articles first, then entries by topic."""
    out = []
    for tid, _ in TOPICS:
        out += [a for a in ARTICLES if a.topic == tid]
        out += [e for e in ENTRIES if e.topic == tid]
    return out


def entries_dict():
    """{(owner, name): Entry}"""
    return {(e.owner, e.name): e for e in ENTRIES}


def get(key):
    """The Entry or Article with this key ("Drone.takeoff", "mat"), or None."""
    for it in ITEMS:
        if it.key == key:
            return it
    return None


def find(name):
    """Entries a bare name can mean: takeoff -> [Drone.takeoff]; duration -> [Show.duration, Drone.duration].
    Show commands (dsl=True) come first."""
    hits = [e for e in ENTRIES if e.name == name]
    return sorted(hits, key=lambda e: not e.dsl)


def drone_commands():
    """Entries of the drone methods a show author writes (takeoff, code, rgb, ...)."""
    return [e for e in ENTRIES if e.owner == "Drone" and e.dsl]


def _norm(text):
    return text.lower().replace("ё", "е")


def search(query):
    """Items whose name or one-line summary contains every word of `query` (case and ё/е ignored).
    The formation command name (moveXY) also counts. An empty query returns everything."""
    words = _norm(query).split()
    if not words:
        return items()
    out = []
    for it in items():
        hay = _norm(f"{it.label} {it.summary} " + (it.command or "" if isinstance(it, Entry) else ""))
        if all(w in hay for w in words):
            out.append(it)
    return out


def hint_html(entry, colors):
    """Rich text for an editor tooltip. `colors` maps token names to '#rrggbb' (the theme tokens)."""
    c = colors
    lines = [f"<b>{entry.signature}</b>", entry.summary]
    for p in entry.params:
        lines.append(f"<span style='color:{c['text2']}'>{p.name}</span> — {p.unit}")
    lines.append(f"{entry.icon} {entry.status}")
    return "<br>".join(lines)
