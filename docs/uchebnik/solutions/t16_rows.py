# Проект 5. Шесть дронов в двух рядах меняются рядами: нижний ряд летит на 80 см, верхний на 150 см.
from litebee_show import Show

show = Show('Ряды меняются')

bottom = [13, 15, 17]
top = [49, 51, 53]

for i in range(3):
    d = show.drone(i + 1)
    d.calibrate(5)
    d.takeoff(80, 5)
    d.rgb('blue')
    d.code(bottom[i], 1)
    d.code(top[i], 6)
    d.rgb('black')
    d.land_on(top[i])

    d = show.drone(i + 4)
    d.calibrate(5)
    d.takeoff(150, 5)
    d.rgb('red')
    d.code(top[i], 1)
    d.code(bottom[i], 6)
    d.rgb('black')
    d.land_on(bottom[i])
