# Упражнение 2.1: взлёт на 60 см за 4 секунды.
from litebee_show import Show

show = Show('Низкий взлёт')

d = show.drone(1)
d.calibrate(5)
d.takeoff(60, 4)
d.land()
