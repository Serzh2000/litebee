# Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.
# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.
# Две пары дронов меняются местами. Один дрон каждой пары идёт на 80 см, другой на 150 см:
# на пересечении между ними 70 см по высоте. Высоту 150 см занимает только верхний дрон.
from litebee_show import Show

show = Show('Обмен местами в четверти')

d = show.drone(1)
d.calibrate(5)
d.takeoff(80, 5)
d.rgb('blue')
d.code(25, 1)
d.code(28, 6)
d.rgb('black')
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(150, 5)
d.rgb('red')
d.code(28, 1)
d.code(25, 6)
d.rgb('black')
d.land()

d = show.drone(3)
d.calibrate(5)
d.takeoff(80, 5)
d.rgb('blue')
d.code(49, 1)
d.code(52, 6)
d.rgb('black')
d.land()

d = show.drone(4)
d.calibrate(5)
d.takeoff(150, 5)
d.rgb('red')
d.code(52, 1)
d.code(49, 6)
d.rgb('black')
d.land()
