# Упражнение 4.2: между 60 и 120 см два раза.
from litebee_show import Show

show = Show('Дыхание')

d = show.drone(1)
d.calibrate(5)
d.takeoff(60, 5)
d.set_z(120, 2)
d.set_z(60, 2)
d.set_z(120, 2)
d.set_z(60, 2)
d.land()
