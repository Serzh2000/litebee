from litebee_show import Show

show = Show('Слишком быстро')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(13, 1)
d.code(16, 1)
d.land()
