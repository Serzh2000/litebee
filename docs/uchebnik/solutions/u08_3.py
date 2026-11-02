# Упражнение 8.3: то же, что land_on(16), но четырьмя командами.
from litebee_show import Show

show = Show('land_on по шагам')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(16, 4)
d.code(16, 2)
d.set_z(100, 1.5)
d.set_z(35, 2.5)
d.land()
