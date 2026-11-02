# Упражнение 3.4: красный не успевает показаться, rgb занимает 0 секунд.
from litebee_show import Show

show = Show('Два цвета подряд')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('red')
d.rgb('green')
d.set_z(100, 2)
d.rgb('black')
d.land()
