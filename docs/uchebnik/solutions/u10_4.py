# Упражнение 10.4: исправленный файл bad_close.py, высоты 80 и 150 см.
from litebee_show import Show

show = Show('Без сближения')

d = show.drone(1)
d.calibrate(5)
d.takeoff(80, 5)
d.code(13, 1)
d.code(16, 4)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(150, 5)
d.code(15, 1)
d.code(12, 4)
d.land()
