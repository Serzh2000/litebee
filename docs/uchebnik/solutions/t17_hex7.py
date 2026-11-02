# Проект 6. Семь дронов: шестёрка по кольцу сдвигается на два места, седьмой в центре мигает.
from litebee_show import Show

show = Show('Семёрка')

ring = [2, 16, 40, 50, 36, 12]
colors = ['red', 'yellow', 'green', 'cyan', 'blue', 'purple']

for n in range(6):
    d = show.drone(n + 1)
    d.calibrate(5)
    d.takeoff(90 if n % 2 == 0 else 130, 5)
    d.rgb(colors[n])
    d.code(ring[n], 1)
    d.code(ring[(n + 1) % 6], 5)
    d.code(ring[(n + 2) % 6], 5)
    d.rgb('black')
    d.land()

d = show.drone(7)
d.calibrate(5)
d.takeoff(60, 5)
d.code(26, 1)
for _ in range(5):
    d.rgb('white')
    d.set_z(60, 1)
    d.rgb('black')
    d.set_z(60, 1)
d.land()
