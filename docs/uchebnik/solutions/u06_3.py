# Упражнение 6.3: 13 -> 17 -> 13 по 4 секунды.
from litebee_show import Show

show = Show('Туда и обратно')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(17, 4)
d.code(13, 4)
d.land()
