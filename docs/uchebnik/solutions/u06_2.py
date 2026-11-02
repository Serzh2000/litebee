# Упражнение 6.2: тот же перелёт 13 -> 16, но не быстрее 100 см/с.
from litebee_show import Show

show = Show('Помедленнее')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(16, 4)
d.land()
