# Упражнение 8.2: land_on с подлётом 3 секунды и остановкой на 60 см.
from litebee_show import Show

show = Show('Осторожная посадка')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(16, 4)
d.land_on(16, 3, 60)
