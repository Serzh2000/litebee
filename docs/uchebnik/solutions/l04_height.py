# Подъём, пауза на новой высоте и спуск.
from litebee_show import Show

show = Show('Этажи')

d = show.drone(1)
d.calibrate(5)
d.takeoff(60, 5)
d.set_z(120, 3)
d.set_z(120, 2)
d.set_z(60, 3)
d.land()
