# Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.
# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.
# Один дрон ходит зигзагом в нижней половине, другой в верхней, зеркально по зигзагу первого.
# Посадка land_on: дрон подлетает к клетке, замирает, снижается и только потом садится: так он садится ровнее.
from litebee_show import Show

show = Show('Зигзаг')

d = show.drone(1)
d.calibrate(5)
d.takeoff(80, 5)
d.rgb('green')
d.code(0, 1)
d.code(25, 2)
d.code(2, 2)
d.code(27, 2)
d.code(4, 2)
d.code(17, 2)
d.rgb('black')
d.land_on(17)

d = show.drone(2)
d.calibrate(5)
d.takeoff(130, 5)
d.rgb('purple')
d.code(60, 1)
d.code(37, 2)
d.code(62, 2)
d.code(39, 2)
d.code(64, 2)
d.code(53, 2)
d.rgb('black')
d.land_on(53)
