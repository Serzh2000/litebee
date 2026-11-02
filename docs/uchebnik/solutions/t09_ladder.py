# Проект 2. Лесенка: три дрона на высотах 20, 85 и 150 см (зазор не меньше 60 см) сдвигаются по кругу.
from litebee_show import Show

show = Show('Лесенка')

d = show.drone(1)
d.calibrate(5)
d.takeoff(20, 5)
d.rgb('red')
d.code(13, 1)
d.code(15, 5)
d.rgb('black')
d.land()

d = show.drone(2)
d.calibrate(5)
d.takeoff(85, 5)
d.rgb('yellow')
d.code(15, 1)
d.code(17, 5)
d.rgb('black')
d.land()

d = show.drone(3)
d.calibrate(5)
d.takeoff(150, 5)
d.rgb('green')
d.code(17, 1)
d.code(13, 5)
d.rgb('black')
d.land()
