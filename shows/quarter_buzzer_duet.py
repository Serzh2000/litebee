# Для одной четверти коврика. Два дрона стоят рядом и по очереди играют ноты: первый низкие,
# второй высокие, вразнобой -- "перекличка" зуммеров. То же примечание про звук, что и в
# quarter_buzzer_scale.py: из самого показа звук не идёт, нужен `python -m litebee buzz-live`.
from litebee_show import Show

show = Show('Перекличка зуммеров')

a = show.drone(1)
a.calibrate(5)
a.takeoff(80, 5)
a.code(13, 1)

b = show.drone(2)
b.calibrate(5)
b.takeoff(100, 5)
b.code(15, 1)

pairs = [('C3', 'C4'), ('E3', 'E4'), ('G3', 'G4'), ('C3', 'C4')]
for low, high in pairs:
    a.rgb('blue')
    a.buzz(low, 0.6)
    a.rgb('black')
    b.rgb('yellow')
    b.buzz(high, 0.6)
    b.rgb('black')

a.land()
b.land()
