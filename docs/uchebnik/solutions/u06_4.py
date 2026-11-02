# Упражнение 6.4: 13 -> 52, 170 см, нужно больше 1,7 секунды.
from litebee_show import Show

show = Show('По диагонали')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(52, 4)
d.land()
