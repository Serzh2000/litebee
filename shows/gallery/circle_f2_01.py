# Шаги circle вокруг центра: два дрона напротив друг друга, оборот, потом столько же в другую сторону. На дроне шаг circle длится count × время, а симулятор считает время за весь круг.
# Для всего коврика 12 x 12 клеток.
# Перед загрузкой каждый дрон стоит на своей первой клетке (на карте она подсвечена), номер подтянется сам.
from litebee_show import Show

show = Show('Круг: два дрона напротив друг друга, оборот и обратно')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('red')
d.code(13, 1)
d.circle(2, 65, 78, 22, 'cw')
d.rgb('cyan')
d.circle(2, 65, 78, 22, 'ccw')
d.rgb('purple')
d.circle(2, 65, 78, 22, 'cw')
d.rgb('cyan')
d.circle(2, 65, 78, 22, 'ccw')
d.rgb('black')
d.land_on(13)

d = show.drone(2)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('yellow')
d.code(130, 1)
d.circle(2, 65, 78, 22, 'cw')
d.rgb('blue')
d.circle(2, 65, 78, 22, 'ccw')
d.rgb('white')
d.circle(2, 65, 78, 22, 'cw')
d.rgb('blue')
d.circle(2, 65, 78, 22, 'ccw')
d.rgb('black')
d.land_on(130)
