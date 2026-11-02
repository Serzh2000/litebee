# Упражнение 14.2: квадрат из урока 7, к каждой клетке добавлено 78.
from litebee_show import Show

show = Show('Четвёртая четверть')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(91, 1)
d.code_s('94 130 127 91', 16)
d.land()
