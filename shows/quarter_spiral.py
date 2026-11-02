# Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.
# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.
# Два дрона на противоположных углах обходят квадрат и по ходу поднимаются с 80 до 140 см и спускаются.
# Идут одновременно, поэтому всегда на разных сторонах квадрата (не ближе 120 см друг от друга).
from litebee_show import Show

show = Show('Спираль в четверти')

d = show.drone(1)
d.calibrate(5)
d.takeoff(80, 5)
d.rgb('green')
d.code(13, 1)
d.code(16, 4)
d.set_z(100, 2)
d.code(52, 4)
d.set_z(120, 2)
d.code(49, 4)
d.set_z(140, 2)
d.code(13, 4)
d.set_z(120, 2)
d.code(16, 4)
d.set_z(100, 2)
d.rgb('black')
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(80, 5)
d.rgb('blue')
d.code(52, 1)
d.code(49, 4)
d.set_z(100, 2)
d.code(13, 4)
d.set_z(120, 2)
d.code(16, 4)
d.set_z(140, 2)
d.code(52, 4)
d.set_z(120, 2)
d.code(49, 4)
d.set_z(100, 2)
d.rgb('black')
d.land()
