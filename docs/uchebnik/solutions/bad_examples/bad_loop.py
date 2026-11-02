from litebee_show import Show

show = Show('Бесконечный цикл')

d = show.drone(1)
while True:
    d.set_z(100, 1)
