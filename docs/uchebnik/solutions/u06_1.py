# Упражнение 6.1: из 13 в 15 за 3 секунды.
from litebee_show import Show

show = Show('На две клетки')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(15, 3)
d.land()
