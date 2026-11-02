# Два дрона меняются местами на одной линии: один на 80 см, другой на 150 см.
from litebee_show import Show

show = Show('Разминуться')

d = show.drone(1)
d.calibrate(5)
d.takeoff(80, 5)
d.rgb('blue')
d.code(13, 1)
d.code(16, 6)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(150, 5)
d.rgb('red')
d.code(16, 1)
d.code(13, 6)
d.land()
