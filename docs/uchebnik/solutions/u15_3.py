# Упражнение 15.3: подъём с 60 до 140 см по пути из 13 в 16 и спуск обратно.
from litebee_show import Show

show = Show('Горка')

d = show.drone(1)
d.calibrate(5)
d.takeoff(60, 5)
d.code(13, 1)
d.code_z(16, 140, 6)
d.code_z(13, 60, 6)
d.land()
