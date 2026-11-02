# Упражнение 7.2: 3 клетки в ширину, 2 в высоту (клетки 13, 16, 40, 37).
from litebee_show import Show

show = Show('Прямоугольник')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code_s('16 40 37 13', 14)
d.land()
