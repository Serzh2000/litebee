# Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.
# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.
# Дроны стоят на своих клетках и качаются по высоте в противофазе: когда один вверху, другой внизу.
# Посадка land_on: дрон подлетает к клетке, замирает, снижается и только потом садится: так он садится ровнее.
from litebee_show import Show

show = Show('Лифт')

d = show.drone(1)
d.calibrate(5)
d.takeoff(60, 5)
d.rgb('cyan')
d.code(13, 1)
d.set_z(150, 3)
d.rgb('white')
d.set_z(60, 3)
d.rgb('cyan')
d.set_z(150, 3)
d.rgb('white')
d.set_z(60, 3)
d.rgb('black')
d.land_on(13)

d = show.drone(2)
d.calibrate(5)
d.takeoff(150, 5)
d.rgb('yellow')
d.code(16, 1)
d.set_z(60, 3)
d.rgb('white')
d.set_z(150, 3)
d.rgb('yellow')
d.set_z(60, 3)
d.rgb('white')
d.set_z(150, 3)
d.rgb('black')
d.land_on(16)
