# Упражнение 8.4: из 13 в 52 по диагонали и посадка в клетку 52.
from litebee_show import Show

show = Show('Диагональ и посадка')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(52, 4)
d.land_on(52)
