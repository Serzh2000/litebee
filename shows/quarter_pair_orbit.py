# Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.
# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.
# Первый дрон висит над центром на 150 см, второй обходит его по кольцу из восьми клеток на 80 см.
# Посадка land_on: дрон подлетает к клетке, замирает, снижается и только потом садится: так он садится ровнее.
from litebee_show import Show

show = Show('Облёт')

d = show.drone(1)
d.calibrate(5)
d.takeoff(150, 5)
d.rgb('white')
d.code(26, 1)
d.rgb('red')
d.set_z(150, 3)
d.rgb('green')
d.set_z(150, 3)
d.rgb('blue')
d.set_z(150, 3)
d.rgb('purple')
d.set_z(150, 3)
d.rgb('white')
d.set_z(150, 5)
d.rgb('black')
d.land_on(26)

d = show.drone(2)
d.calibrate(5)
d.takeoff(80, 5)
d.rgb('yellow')
d.code(1, 1)
d.code(13, 2)
d.code(14, 2)
d.code(15, 2)
d.code(27, 2)
d.code(39, 2)
d.code(38, 2)
d.code(37, 2)
d.code(25, 2)
d.code(13, 2)
d.rgb('black')
d.land_on(1)
