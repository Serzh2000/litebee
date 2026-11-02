# Упражнение 11.1: исправленный bad_three.py.
from litebee_show import Show

show = Show('Три проблемы решены')

d = show.drone(1)
d.calibrate(5)
d.takeoff(80, 5)
d.code(13, 1)
d.code(16, 4)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(150, 5)
d.code(15, 1)
d.code(13, 6)
d.land()
