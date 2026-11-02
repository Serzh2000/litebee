# Упражнение 3.1: красный 3 с, жёлтый 1 с, зелёный 3 с.
from litebee_show import Show

show = Show('Светофор')

d = show.drone(1)
d.calibrate(5)
d.takeoff(60, 5)
d.rgb('red')
d.set_z(60, 3)
d.rgb('yellow')
d.set_z(60, 1)
d.rgb('green')
d.set_z(60, 3)
d.rgb('black')
d.land()
