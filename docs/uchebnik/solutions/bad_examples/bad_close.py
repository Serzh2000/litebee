from litebee_show import Show

show = Show('Слишком близко')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(16, 4)
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.code(15, 1)
d.code(12, 4)
d.land()
