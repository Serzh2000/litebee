# Упражнение 7.1: клетки 13, 16, 52 и обратно в 13.
from litebee_show import Show

show = Show('Треугольник')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(16, 4)
d.code(52, 4)
d.code(13, 6)
d.land()
