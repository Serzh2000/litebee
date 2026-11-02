# Упражнение 4.4: подняться до 150, спуститься до 30, снова до 100.
from litebee_show import Show

show = Show('Лифт')

d = show.drone(1)
d.calibrate(5)
d.takeoff(150, 5)
d.set_z(30, 4)
d.set_z(100, 3)
d.land()
