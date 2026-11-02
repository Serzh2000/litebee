# Упражнение 10.1: два дрона летят рядом вверх по столбцам 13 -> 49 и 16 -> 52.
from litebee_show import Show

show = Show('Параллельно')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(49, 6)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.code(16, 1)
d.code(52, 6)
d.land()
