# Облёт квадрата и посадка в центр стартовой клетки.
from litebee_show import Show

show = Show('Посадка в клетку')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code_s('16 52 49 13', 16)
d.land_on(13)
