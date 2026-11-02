# Упражнение 3.2: семь цветов по номерам, по секунде каждый.
from litebee_show import Show

show = Show('Радуга')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb(1)
d.set_z(100, 1)
d.rgb(2)
d.set_z(100, 1)
d.rgb(3)
d.set_z(100, 1)
d.rgb(4)
d.set_z(100, 1)
d.rgb(5)
d.set_z(100, 1)
d.rgb(6)
d.set_z(100, 1)
d.rgb(7)
d.set_z(100, 1)
d.rgb(0)
d.land()
