# Три красных вспышки: тело цикла повторяется три раза.
from litebee_show import Show

show = Show('Мигание циклом')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
for _ in range(3):
    d.rgb('red')
    d.set_z(100, 1)
    d.rgb('black')
    d.set_z(100, 1)
d.land()
