# Упражнение 14.1: квадрат из урока 7, к каждой клетке добавлено 72.
from litebee_show import Show

show = Show('Третья четверть')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(85, 1)
d.code_s('88 124 121 85', 16)
d.land()
