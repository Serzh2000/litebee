# Из 13 в 49 с подъёмом на 150 см и обратно с опусканием на 60.
from litebee_show import Show

show = Show('Подъём на ходу')

d = show.drone(1)
d.calibrate(5)
d.takeoff(60, 5)
d.code(13, 1)
d.code_z(49, 150, 6)
d.code_z(13, 60, 6)
d.land()
