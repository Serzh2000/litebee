# Упражнение 7.3: сверху вправо, по диагонали вниз, снизу вправо.
from litebee_show import Show

show = Show('Буква Z')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(49, 1)
d.code(52, 4)
d.code(13, 6)
d.code(16, 4)
d.land()
