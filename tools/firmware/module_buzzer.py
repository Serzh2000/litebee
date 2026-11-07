"""Играет мелодию на зуммере, подключённом к разъёму U0TX/U0RX/5V/GND камеры-модуля (V831).

Запускается НА МОДУЛЕ (Python 3.8 из MaixPy3), модуль подключён к компьютеру по USB (ADB):
    adb push tools/firmware/module_buzzer.py /tmp/module_buzzer.py
    adb shell python3 /tmp/module_buzzer.py "C3:10 D3:10 E3:10 C3:10 R:5 G3:20"

Нота:длительность, длительность в единицах по 0.05 с, R это пауза. Таблица нот как в LiteBee Go (B0 ... DS8, диез: CS3).
Кадр ноты: AD FA 01 нота длительность сумма. Формат проверен на слух 2026-11-07, docs/firmware/BUZZER_EXTENSION.md.
Порт /dev/ttyS0 уже настроен штатной программой (115200 8N1), мы только пишем в него.
Самодостаточный файл: не импортирует litebee.
"""
import os
import sys
import time

SEMI = ["C", "CS", "D", "DS", "E", "F", "FS", "G", "GS", "A", "AS", "B"]
NAMES = ["B0"] + [n + str(o) for o in range(1, 9) for n in SEMI][:-8]
UNIT = 0.05


def frame(note, dur):
    body = bytes([0x01, note, dur])
    return bytes([0xAD, 0xFA]) + body + bytes([sum(body) & 0xFF])


def main(text):
    fd = os.open("/dev/ttyS0", os.O_WRONLY | os.O_NOCTTY)
    try:
        for token in text.split():
            name, _, d = token.partition(":")
            dur = int(d)
            if name.upper() in ("R", "-"):
                time.sleep(dur * UNIT)
                continue
            os.write(fd, frame(NAMES.index(name.upper()), dur))
            time.sleep(dur * UNIT + 0.05)
    finally:
        os.close(fd)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Использование: module_buzzer.py \"C3:10 E3:10 G3:20\"")
    main(sys.argv[1])
