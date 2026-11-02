# Упражнение 10.2: диагонали 13 -> 52 и 16 -> 49, высоты 80 и 150 см.
from litebee_show import Show

show = Show('Крест')

d = show.drone(1)
d.calibrate(5)
d.takeoff(80, 5)
d.code(13, 1)
d.code(52, 7)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(150, 5)
d.code(16, 1)
d.code(49, 7)
d.land()
