# Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.
# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.
# Два дрона обходят квадрат 3 x 3 клетки, всегда в противоположных углах. Свет у них разный.
# Посадка land_on: дрон подлетает к клетке, замирает, снижается и только потом садится: так он садится ровнее.
from litebee_show import Show

show = Show('Зеркало')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('green')
d.code(13, 1)
d.code(16, 4)
d.code(52, 4)
d.code(49, 4)
d.code(13, 4)
d.rgb('yellow')
d.rgb('black')
d.land_on(13)

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('purple')
d.code(52, 1)
d.code(49, 4)
d.code(13, 4)
d.code(16, 4)
d.code(52, 4)
d.rgb('cyan')
d.rgb('black')
d.land_on(52)
