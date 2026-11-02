from litebee_show import Show

show = Show('Нет такой клетки')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.code(144, 4)
d.land()
