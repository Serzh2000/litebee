from litebee_show import Show

show = Show('Слишком долгое ожидание')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.set_z(100, 90)
d.land()
