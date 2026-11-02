# Проект 3 из урока 16, записанный циклом: один блок на всех четырёх дронов.
from litebee_show import Show

show = Show('Углы циклом')

corners = [0, 4, 52, 48]
colors = ['red', 'yellow', 'green', 'blue']

for n in range(4):
    d = show.drone(n + 1)
    d.calibrate(5)
    d.takeoff(100, 5)
    d.rgb(colors[n])
    d.code(corners[n], 1)
    for k in range(1, 5):
        d.code(corners[(n + k) % 4], 4)
    d.rgb('black')
    d.land()
