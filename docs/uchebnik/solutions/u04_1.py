# Упражнение 4.1: ступени 50, 100, 150 см по две секунды.
from litebee_show import Show

show = Show('Лесенка вверх')

d = show.drone(1)
d.calibrate(5)
d.takeoff(50, 3)
d.set_z(100, 2)
d.set_z(150, 2)
d.land()
