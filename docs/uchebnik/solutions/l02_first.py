# Калибровка, взлёт на 100 см и посадка.
from litebee_show import Show

show = Show('Первый взлёт')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.land()
