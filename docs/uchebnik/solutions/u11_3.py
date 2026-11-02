# Упражнение 11.3: 90 секунд ожидания разбиты на два шага по 45.
from litebee_show import Show

show = Show('Ожидание по частям')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.set_z(100, 45)
d.set_z(100, 45)
d.land()
