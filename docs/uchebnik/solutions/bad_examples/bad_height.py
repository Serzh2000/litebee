from litebee_show import Show

show = Show('Слишком высоко')

d = show.drone(1)
d.calibrate(5)
d.takeoff(180, 5)
d.land()
