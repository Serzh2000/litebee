# Упражнение 13.2: семь цветов списком и циклом.
from litebee_show import Show

show = Show('Радуга циклом')

d = show.drone(1)
colors = ['red', 'yellow', 'green', 'cyan', 'blue', 'purple', 'white']
d.calibrate(5)
d.takeoff(100, 5)
for color in colors:
    d.rgb(color)
    d.set_z(100, 1)
d.rgb('black')
d.land()
