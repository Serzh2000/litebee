# Квадрат из урока 7, к каждой клетке добавлено 6.
from litebee_show import Show

show = Show('Квадрат во второй четверти')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(19, 1)
d.code_s('22 58 55 19', 16)
d.land()
