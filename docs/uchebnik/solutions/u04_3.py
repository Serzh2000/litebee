# Упражнение 4.3: десять секунд на 100 см, пять синих и пять красных.
from litebee_show import Show

show = Show('Десять секунд')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('blue')
d.set_z(100, 5)
d.rgb('red')
d.set_z(100, 5)
d.rgb('black')
d.land()
