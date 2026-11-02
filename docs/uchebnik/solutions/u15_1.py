# Упражнение 15.1: полный круг в другую сторону.
from litebee_show import Show

show = Show('Против часовой')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(14, 1)
d.circle(2, 26, 26, 12, 'ccw')
d.land()
