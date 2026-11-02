# Шаги circle вокруг центра: две пары навстречу на разной высоте, два оборота. На дроне шаг circle длится count × время, а симулятор считает время за весь круг.
# Для одной четверти коврика: клетки 0-5 по столбцам и строкам (2,4 x 2,4 м), клетка = столбец + 12 x строка.
# Чтобы перенести шоу в другую четверть, нажмите «Перенести шоу» над картой.
# Перед загрузкой каждый дрон стоит на своей первой клетке (на карте она подсвечена), номер подтянется сам.
from litebee_show import Show

show = Show('Круг: две пары навстречу на разной высоте, два оборота')

d = show.drone(1)
d.calibrate(5)
d.takeoff(70, 5)
d.rgb('red')
d.code(13, 1)
d.circle(4, 26, 39, 24, 'cw')
d.rgb('purple')
d.circle(4, 26, 39, 24, 'cw')
d.rgb('black')
d.land_on(13)

d = show.drone(2)
d.calibrate(5)
d.takeoff(70, 5)
d.rgb('yellow')
d.code(52, 1)
d.circle(4, 26, 39, 24, 'cw')
d.rgb('white')
d.circle(4, 26, 39, 24, 'cw')
d.rgb('black')
d.land_on(52)

d = show.drone(3)
d.calibrate(5)
d.takeoff(140, 5)
d.rgb('green')
d.code(16, 1)
d.circle(4, 26, 39, 24, 'ccw')
d.rgb('red')
d.circle(4, 26, 39, 24, 'ccw')
d.rgb('black')
d.land_on(16)

d = show.drone(4)
d.calibrate(5)
d.takeoff(140, 5)
d.rgb('cyan')
d.code(49, 1)
d.circle(4, 26, 39, 24, 'ccw')
d.rgb('yellow')
d.circle(4, 26, 39, 24, 'ccw')
d.rgb('black')
d.land_on(49)
