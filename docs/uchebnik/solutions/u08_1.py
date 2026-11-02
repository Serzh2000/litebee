# Упражнение 8.1: из 13 в 16 и посадка в центр клетки 16.
from litebee_show import Show

show = Show('Сесть у цели')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(16, 4)
d.land_on(16)
