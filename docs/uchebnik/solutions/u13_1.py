# Упражнение 13.1: три раза туда и обратно между 13 и 17.
from litebee_show import Show

show = Show('Челнок')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
for _ in range(3):
    d.code(17, 4)
    d.code(13, 4)
d.land()
