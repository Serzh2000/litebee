# Упражнение 2.2: зелёный свет и пауза 3 секунды перед посадкой.
from litebee_show import Show

show = Show('Зелёный огонёк')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('green')
d.set_z(100, 3)
d.rgb('black')
d.land()
