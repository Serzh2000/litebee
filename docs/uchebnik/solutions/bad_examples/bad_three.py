from litebee_show import Show

show = Show('Три проблемы')

d = show.drone(1)
d.calibrate(5)
d.takeoff(170, 5)
d.code(13, 1)
d.code(16, 1)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(170, 5)
d.code(15, 1)
d.code(13, 6)
d.land()
