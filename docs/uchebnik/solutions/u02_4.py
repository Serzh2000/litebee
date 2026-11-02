# Упражнение 2.4: взлёт ровно до лимита 150 см.
from litebee_show import Show

show = Show('Не выше лимита')

d = show.drone(1)
d.calibrate(5)
d.takeoff(150, 5)
d.land()
