# Шаги circle вокруг центра: два дрона напротив друг друга, оборот, потом столько же в другую сторону. На дроне шаг circle длится count × время, а симулятор считает время за весь круг.
# Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.
# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.
# Перед загрузкой каждый дрон стоит на своей первой клетке (на карте она подсвечена), номер подтянется сам.
from litebee_show import Show

show = Show('Круг: два дрона напротив друг друга, оборот и обратно')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('red')
d.code(13, 1)
d.circle(2, 26, 39, 16, 'cw')
d.rgb('cyan')
d.circle(2, 26, 39, 16, 'ccw')
d.rgb('purple')
d.circle(2, 26, 39, 16, 'cw')
d.rgb('cyan')
d.circle(2, 26, 39, 16, 'ccw')
d.rgb('black')
d.land_on(13)

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('yellow')
d.code(52, 1)
d.circle(2, 26, 39, 16, 'cw')
d.rgb('blue')
d.circle(2, 26, 39, 16, 'ccw')
d.rgb('white')
d.circle(2, 26, 39, 16, 'cw')
d.rgb('blue')
d.circle(2, 26, 39, 16, 'ccw')
d.rgb('black')
d.land_on(52)
