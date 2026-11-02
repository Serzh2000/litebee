# Упражнение 12.1: сначала летит дрон 1, потом дрон 2.
from litebee_show import Show

show = Show('Два по очереди')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(49, 4)
d.code(13, 4)
d.set_z(100, 9)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.code(15, 1)
d.set_z(100, 9)
d.code(51, 4)
d.code(15, 4)
d.land()
