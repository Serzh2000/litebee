# Упражнение 15.2: половина круга, дрон оказывается напротив, в клетке 38.
from litebee_show import Show

show = Show('Полкруга')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(14, 1)
d.circle(1, 26, 26, 6)
d.land_on(38)
d.land()
