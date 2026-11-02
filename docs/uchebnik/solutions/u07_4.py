# Упражнение 7.4: квадрат в обратную сторону, 13 -> 49 -> 52 -> 16 -> 13.
from litebee_show import Show

show = Show('Другая сторона')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code_s('49 52 16 13', 16)
d.land()
