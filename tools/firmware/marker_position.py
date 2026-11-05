"""Положение дрона по маркеру ковра: восстановление из двух прошивок производителя.

Это ВОССТАНОВЛЕНИЕ по дизассемблеру, а не исходный код производителя.

Источники:
  * ARM: Wing_V1.2.8 FM_V1.1.2.img, файл img_app/pilot/pilot (функции 0x344c0, 0x1ff0c..0x202a0);
  * RISC-V: LiteBee Go, resources/cache/melis30_1.5.elf (версия 1.5, «тестовая»), файл
    projects/v853s-e907-perf1-board/src/flight/hal/hal_apriltag.c, функции apriltag_process и
    apriltag_get_id_pos. Там есть имена и DWARF, поэтому этот источник точнее.

Логика в обеих одна: ядро полёта получает готовые id маркера и смещение от камеры и считает положение.
Столбец = id % 12, строка = id // 12, шаг клетки 40 см (подтверждено в обеих прошивках).

Различаются только числовые константы масштаба (см. CONSTS).
"""
from __future__ import annotations

from dataclasses import dataclass

# Константы ветки по умолчанию («большой» маркер, клетка 40 см).
CONSTS = {
    # имя версии: (масштаб смещения, коэффициент высоты, коэффициент высоты малых маркеров)
    "pilot_arm_1.2.8": dict(scale=8.333, z=10.2, z_small=2.7),
    "melis_1.5": dict(scale=8.0, z=13.0, z_small=3.5),
}
PITCH = 40.0            # шаг большой клетки
SMALL_PITCH = 5.0       # шаг «малых» маркеров
SMALL_SCALE = 2.083
SCALE_17_20 = 4.0       # масштаб для id 17..20 в обеих прошивках, коэффициент высоты 5
Z_17_20 = 5.0
CENTI = 0.01
Z_UNIT = 1e-4
MAX_ID = 288            # pilot ARM: id >= 288 отбрасывается
SMALL_MIN_ID = 100      # id > 99 может быть малым маркером

# Малые маркеры: два набора по 9 id (блоки 3x3 клеток), для них apriltag_get_id_pos возвращает
# фиксированные значения (0.5, 0.05) и (0.5, 0.2). Прочитано по байтам стека; блок сравнения лежит
# в команде расширения T-Head, которую capstone не разбирает, поэтому смысл ПО СТРУКТУРЕ, не проверен.
SMALL_SET_A = (108, 109, 110, 120, 121, 122, 132, 133, 134)
SMALL_SET_B = (111, 112, 113, 123, 124, 125, 135, 136, 137)
SMALL_FIXED = {"A": (0.5, 0.05), "B": (0.5, 0.2)}


@dataclass
class Frame:
    """Поля кадра позиционного модуля (struct по адресу gp-0x408 в melis, 0x78178 в pilot ARM)."""
    id: int      # +0x0E (melis); -1, если маркер не виден
    dx: int      # +0x10: смещение камеры от центра маркера, ось столбца
    dy: int      # +0x12: смещение камеры от центра маркера, ось строки
    dz: int      # +0x14: расстояние до маркера (высота), нужно > 100
    yaw_raw: int  # +0x16: курс, десятые доли градуса со смещением 1800 (в melis)
    flag: int    # +0x18: 1 если маркер виден


def yaw_deg(f: Frame) -> float:
    """Курс в градусах: (сырое - 1800) * 0.1 (melis apriltag_process 0x47c35fb0). В pilot ARM смещения нет."""
    return (f.yaw_raw - 1800) * 0.1


def cell_of(id_: int) -> tuple[int, int]:
    """(строка, столбец) по id: частное и остаток от деления на 12."""
    return id_ // 12, id_ % 12


def marker_position(f: Frame, version: str = "melis_1.5", small: bool = False) -> tuple[float, float, float] | None:
    """(по строке, по столбцу, z) в единицах прошивки (по проверке: метры), None если кадр не принят.

    small: режим малых маркеров. В прошивке он включается сам: id > 99, расстояние > 100, и отношение
    медианы последних трёх расстояний к текущему в окне (1, 9) после умножения на 1e4. Здесь его надо
    указать вручную, потому что медиану нужно считать по потоку кадров.
    """
    if f.flag == 0 or f.id < 0 or f.id >= MAX_ID or f.dz <= 100:
        return None
    k = CONSTS[version]
    row, col = cell_of(f.id)
    if small and f.id >= SMALL_MIN_ID:
        scale, pitch, zk = SMALL_SCALE, SMALL_PITCH, k["z_small"]
    elif 17 <= f.id <= 20:
        scale, pitch, zk = SCALE_17_20, PITCH, Z_17_20
    else:
        scale, pitch, zk = k["scale"], PITCH, k["z"]
    y = (f.dx * CENTI * scale + col * pitch) * CENTI
    x = (f.dy * CENTI * scale + row * pitch) * CENTI
    z = f.dz * zk * Z_UNIT
    return x, y, z


def id_only_position(id_: int) -> tuple[float, float]:
    """Положение центра клетки: apriltag_get_id_pos для большого маркера (melis 0x47c363ae)."""
    row, col = cell_of(id_)
    return row * PITCH * CENTI, col * PITCH * CENTI


if __name__ == "__main__":
    # клетка 13: строка 1, столбец 1 -> (0.4, 0.4) м
    print(id_only_position(13))
    print(marker_position(Frame(id=13, dx=0, dy=0, dz=150, yaw_raw=1800, flag=1)))
