# Упражнение 3.3: свой цвет через rgb_value.
from litebee_show import Show

show = Show('Оранжевый')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb_value(255, 128, 0)
d.set_z(100, 3)
d.rgb('black')
d.land()
