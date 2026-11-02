# Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.
# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.
# Три дрона на вершинах треугольника (клетки 13, 17 и 63) одновременно переходят на следующую вершину, три раза.
from litebee_show import Show

show = Show('Треугольник в четверти')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('green')
d.code(13, 1)
d.code(17, 6)
d.code(63, 6)
d.code(13, 6)
d.rgb('black')
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('blue')
d.code(17, 1)
d.code(63, 6)
d.code(13, 6)
d.code(17, 6)
d.rgb('black')
d.land()

d = show.drone(3)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('purple')
d.code(63, 1)
d.code(13, 6)
d.code(17, 6)
d.code(63, 6)
d.rgb('black')
d.land()
