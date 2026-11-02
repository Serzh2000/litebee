# Круг в одной четверти коврика. Четыре дрона стоят по углам квадрата (клетки 13, 16, 52, 49)
# и вместе делают один оборот вокруг его центра: середины между клетками 26 и 39.
# Направление кругов в симуляторе угадано: на живом дроне проверьте, куда он повернёт.
from litebee_show import Show

show = Show('Круг в четверти')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('red')
d.code(13, 1)
d.circle(2, 26, 39, 12, 'cw')
d.rgb('black')
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('yellow')
d.code(16, 1)
d.circle(2, 26, 39, 12, 'cw')
d.rgb('black')
d.land()

d = show.drone(3)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('green')
d.code(52, 1)
d.circle(2, 26, 39, 12, 'cw')
d.rgb('black')
d.land()

d = show.drone(4)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('blue')
d.code(49, 1)
d.circle(2, 26, 39, 12, 'cw')
d.rgb('black')
d.land()
