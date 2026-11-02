# Каждый цвет держится две секунды.
from litebee_show import Show

show = Show('Три цвета')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('red')
d.set_z(100, 2)
d.rgb('green')
d.set_z(100, 2)
d.rgb('blue')
d.set_z(100, 2)
d.rgb('black')
d.land()
