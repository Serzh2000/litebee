# Для одной четверти коврика. Два дрона стоят на месте и играют гамму до-мажор на зуммере в
# унисон (docs/firmware/BUZZER_EXTENSION.md), со светодиодом, который меняет цвет на каждой ноте.
# Зуммер нужно подключить к позиционному модулю каждого дрона (U0TX/U0RX). При запуске показа
# ноты играются через mode=27 по тому же каналу, что и формация (litebee/buzzer.py, play_live) --
# для живого дрона нужна команда `python -m litebee buzz-live`, из самого шоу звук не включается.
# Хороший первый пример для зуммера: только свет, звук и ожидание, дроны не летают по коврику.
from litebee_show import Show

show = Show('Гамма до-мажор')

notes = ['C3', 'D3', 'E3', 'F3', 'G3', 'A3', 'B3', 'C4']
colors = ['red', 'yellow', 'green', 'cyan', 'blue', 'purple', 'white', 'red']

for number, cell in ((1, 13), (2, 15)):
    d = show.drone(number)
    d.calibrate(5)
    d.takeoff(80, 5)
    d.code(cell, 1)
    for note, color in zip(notes, colors):
        d.rgb(color)
        d.buzz(note, 1.0)
    d.rgb('black')
    d.land()
