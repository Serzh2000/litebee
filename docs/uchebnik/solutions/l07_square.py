# Квадрат со стороной 3 клетки: каждая сторона 4 секунды.
from litebee_show import Show

show = Show('Квадрат')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code_s('16 52 49 13', 16)
d.land()
