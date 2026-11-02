# Центр круга в клетке 26, дрон стартует в клетке 14, радиус 40 см.
from litebee_show import Show

show = Show('Круг')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(14, 1)
d.circle(2, 26, 26, 12)
d.land()
