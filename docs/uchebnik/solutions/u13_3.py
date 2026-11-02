# Упражнение 13.3: три дрона мигают по очереди, пауза зависит от номера.
from litebee_show import Show

show = Show('Очередь циклом')

cells = [13, 15, 17]

for n in range(3):
    d = show.drone(n + 1)
    d.calibrate(5)
    d.takeoff(100, 5)
    d.code(cells[n], 1)
    d.set_z(100, 2 * n)
    d.rgb('red')
    d.set_z(100, 2)
    d.rgb('black')
    d.set_z(100, 2 * (2 - n))
    d.land()
