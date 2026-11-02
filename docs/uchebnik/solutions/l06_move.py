# Из клетки 13 в клетку 16: три клетки вправо, 120 см за 4 секунды.
from litebee_show import Show

show = Show('Перелёт')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(16, 4)
d.land()
