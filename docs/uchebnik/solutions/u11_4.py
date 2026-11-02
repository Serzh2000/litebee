# Упражнение 11.4: клетка 8 заменена на клетку 5.
from litebee_show import Show

show = Show('Внутри четверти')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(5, 4)
d.land()
