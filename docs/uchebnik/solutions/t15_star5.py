# Проект 4. Пять дронов: четыре по углам обходят квадрат, пятый в центре поднимается и опускается.
from litebee_show import Show

show = Show('Пятёрка')

corners = [0, 4, 52, 48]
colors = ['red', 'yellow', 'green', 'blue']

for n in range(4):
    d = show.drone(n + 1)
    d.calibrate(5)
    d.takeoff(100, 5)
    d.rgb(colors[n])
    d.code(corners[n], 1)
    d.code(corners[(n + 1) % 4], 5)
    d.code(corners[(n + 2) % 4], 5)
    d.rgb('black')
    d.land()

d = show.drone(5)
d.calibrate(5)
d.takeoff(60, 5)
d.rgb('white')
d.code(26, 1)
d.set_z(120, 5)
d.set_z(60, 5)
d.rgb('black')
d.land()
