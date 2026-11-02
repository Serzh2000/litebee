# Упражнение 15.4: два дрона по кругу вокруг клетки 26, один напротив другого.
from litebee_show import Show

show = Show('Танец вдвоём')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(14, 1)
d.circle(2, 26, 26, 12)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.code(38, 1)
d.circle(2, 26, 26, 12)
d.land()
