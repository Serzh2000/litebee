# Упражнение 12.3: три дрона по очереди поднимаются до 150 см и опускаются до 80.
from litebee_show import Show

show = Show('Волна')

d = show.drone(1)
d.calibrate(5)
d.takeoff(80, 5)
d.code(13, 1)
d.set_z(150, 2)
d.set_z(80, 2)
d.set_z(80, 4)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(80, 5)
d.code(15, 1)
d.set_z(80, 2)
d.set_z(150, 2)
d.set_z(80, 2)
d.set_z(80, 2)
d.land()

d = show.drone(3)
d.calibrate(5)
d.takeoff(80, 5)
d.code(17, 1)
d.set_z(80, 4)
d.set_z(150, 2)
d.set_z(80, 2)
d.land()
