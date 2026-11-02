# Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.
# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.
# Три дрона стоят у нижнего края через клетку. По очереди каждый летит до верхнего края и возвращается.
# Колонки в 80 см друг от друга, поэтому дроны не встречаются.
from litebee_show import Show

show = Show('Челнок в четверти')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('green')
d.code(1, 1)
d.code(61, 6)
d.set_z(100, 1)
d.code(1, 6)
d.set_z(100, 8)
d.rgb('black')
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('blue')
d.code(3, 1)
d.set_z(100, 4)
d.code(63, 6)
d.set_z(100, 1)
d.code(3, 6)
d.set_z(100, 4)
d.rgb('black')
d.land()

d = show.drone(3)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('purple')
d.code(5, 1)
d.set_z(100, 8)
d.code(65, 6)
d.set_z(100, 1)
d.code(5, 6)
d.rgb('black')
d.land()
