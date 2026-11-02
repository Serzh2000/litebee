# Проект 7. Восемь дронов по кольцу: чётные дроны идут по кольцу в одну сторону, нечётные навстречу, на два места.
from litebee_show import Show

show = Show('Встречный хоровод')

ring = [0, 2, 4, 28, 52, 50, 48, 24]

for i in range(8):
    high = i % 2 == 0
    step = 1 if high else -1
    way = [ring[(i + step * k) % 8] for k in range(3)]
    d = show.drone(i + 1)
    d.calibrate(5)
    d.takeoff(150 if high else 80, 5)
    d.rgb('yellow' if high else 'cyan')
    d.code(way[0], 1)
    d.code(way[1], 5)
    d.code(way[2], 5)
    d.rgb('black')
    d.land_on(way[2])
