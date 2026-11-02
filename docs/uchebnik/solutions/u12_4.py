# Упражнение 12.4: дрон 2 летит по соседней линии на 3 секунды позже дрона 1.
from litebee_show import Show

show = Show('Опоздавший')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(17, 6)
d.set_z(100, 3)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.code(37, 1)
d.set_z(100, 3)
d.code(41, 6)
d.land()
