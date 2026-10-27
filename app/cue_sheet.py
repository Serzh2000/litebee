"""Cue sheet: one lane per drone. On the left the lane header (a swatch of the LED colour right now and
"Дрон N"), to its right a continuous strip: the LED colour over time, which is the light design of the show.
Thin ticks above the strip mark the steps (docs/UI_DESIGN.md, "Партитура света").

The columns line up with the transport row of the main window: LABEL_W on the left, TIME_W on the right."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from . import theme

LABEL_W = 164
TIME_W = 112
MIN_LANES = 3                 # the sheet is never shorter than three lanes
DIM = 0.28                    # opacity of the lanes that are not in focus
TICK_HIT_PX = 4

STEP_NAME = {
    "calibrate": "калибровка", "takeoff": "взлёт", "land": "посадка", "code": "переход между клетками",
    "code_z": "переход между клетками с высотой", "set_z": "смена высоты", "rgb": "цвет светодиода",
    "circle": "круг", "circle_z": "круг с подъёмом",
}


def step_text(kind, args=None):
    """A short phrase for a step: 'к клетке 25', 'взлёт на 100 см'."""
    a = args or {}
    if kind == "code":
        return f"к клетке {a.get('cell')}"
    if kind == "code_z":
        return f"к клетке {a.get('cell')}, высота {a.get('z', 0):.0f} см"
    if kind == "takeoff":
        return f"взлёт на {a.get('z', 0):.0f} см"
    if kind == "set_z":
        return f"высота {a.get('z', 0):.0f} см"
    if kind == "circle":
        return f"круг вокруг клеток {a.get('cell1')} и {a.get('cell2')}, полуоборотов {a.get('count')}"
    if kind == "circle_z":
        return f"круг вокруг клеток {a.get('cell1')} и {a.get('cell2')} с подъёмом {a.get('dz', 0):.0f} см"
    if kind == "rgb":
        return f"цвет {a.get('color', '')}".strip()
    return STEP_NAME.get(kind, kind)


class TimelineWidget(QWidget):
    time_selected = Signal(float)          # seconds, from a click or a drag on a strip, or the arrow keys
    step_clicked = Signal(int, int)        # drone number, line in the show code
    drone_selected = Signal(object)        # drone number, or None to clear the focus

    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_obj = None
        self.t = 0.0
        self.duration = 0.0
        self.focus = None
        self.lane_h = 14
        self.numbers = []
        self.blocks = []           # [(drone, t0, t1, (r, g, b))]: the LED strip
        self.ticks = []            # [(drone, t, kind, line, args)]
        self._drag = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("Партитура света")
        self._fit()

    # ---- model -------------------------------------------------------------------------------------

    def set_show(self, show):
        self.show_obj = show
        self.blocks, self.ticks, self.numbers = [], [], []
        self.duration = 0.0
        if show is not None:
            self.numbers = sorted(show.drones)
            self.duration = float(show.duration)
            for n in self.numbers:
                now, color, since = 0.0, (0, 0, 0), 0.0
                for s in show.drones[n].steps:
                    if s.kind == "rgb":
                        if now > since:
                            self.blocks.append((n, since, now, color))
                        color, since = tuple(s.args["rgb"]), now
                    else:
                        self.ticks.append((n, now, s.kind, s.line, s.args))
                    now += s.seconds
                self.blocks.append((n, since, max(now, self.duration), color))
            if self.focus not in self.numbers:
                self.focus = None
        else:
            self.focus = None
        self._fit()
        self.update()

    def blocks_for(self, n):
        return [b for b in self.blocks if b[0] == n]

    def set_time(self, t):
        self.t = max(0.0, float(t))
        self.update()

    def set_focus(self, n):
        self.focus = n if n in self.numbers else None
        self.update()

    def set_lane_height(self, px):
        self.lane_h = max(8, int(px))
        self._fit()
        self.update()

    def _fit(self):
        self.setFixedHeight(max(MIN_LANES, len(self.numbers)) * self.lane_h + 2)

    def sizeHint(self):
        return QSize(600, self.height())

    # ---- geometry ----------------------------------------------------------------------------------

    def strip_rect(self):
        return QRectF(LABEL_W, 0, max(self.width() - LABEL_W - TIME_W, 1), self.height())

    def x_of(self, t):
        r = self.strip_rect()
        return r.left() + (min(t, self.duration) / self.duration if self.duration > 0 else 0.0) * r.width()

    def t_of(self, x):
        r = self.strip_rect()
        if self.duration <= 0:
            return 0.0
        return min(max((x - r.left()) / r.width(), 0.0), 1.0) * self.duration

    def lane_of(self, y):
        i = int(y // self.lane_h)
        return self.numbers[i] if 0 <= i < len(self.numbers) else None

    def led_at(self, n, t):
        return self.show_obj.drones[n].color_at(t)[1]

    # ---- painting ----------------------------------------------------------------------------------

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.lane_h
        strip = self.strip_rect()
        if not self.numbers:
            p.setPen(theme.color("text2"))
            p.setFont(theme.ui_font(12))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет шоу: дорожки появятся после проверки")
            self._paint_focus_bar(p)
            p.end()
            return
        label_font = theme.ui_font(max(9, min(h - 3, 12)), True)
        for i, n in enumerate(self.numbers):
            y = i * h
            p.setOpacity(1.0 if self.focus in (None, n) else DIM)
            lane = QRectF(strip.left(), y + 1, strip.width(), h - 2)
            p.fillRect(lane, theme.color("lane"))
            for b in self.blocks:
                if b[0] != n or b[2] <= b[1]:
                    continue
                x0, x1 = self.x_of(b[1]), self.x_of(b[2])
                if any(b[3]):
                    p.fillRect(QRectF(x0, y + h * 0.42, max(x1 - x0, 1.0), h * 0.5 - 1), QColor(*b[3]))
            ink = theme.color("on_accent")             # ticks sit on the dark lane
            ink.setAlpha(200)
            p.setPen(QPen(ink, 1.0))
            for tn, t, kind, _line, _args in self.ticks:
                if tn == n:
                    self._paint_tick(p, self.x_of(t), y, kind)
            # header: LED swatch at the current time, then the name
            led = self.led_at(n, self.t)
            sw = QRectF(0, y + 2, 6, h - 4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(*led) if any(led) else theme.color("border"))
            p.drawRoundedRect(sw, 2, 2)
            p.setFont(label_font)
            p.setPen(theme.color("text") if self.focus == n else theme.color("text2"))
            p.drawText(QRectF(12, y, LABEL_W - 14, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       f"Дрон {n}")
        p.setOpacity(1.0)
        x = self.x_of(self.t)
        p.setPen(QPen(theme.color("accent"), 4))              # the time cursor: white core in an accent halo
        p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        p.setPen(QPen(theme.color("on_accent"), 1.5))
        p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        self._paint_focus_bar(p)
        p.end()

    def _paint_tick(self, p, x, y, kind):
        """Step marks above the colour strip: ▲ takeoff, ▼ land, | cell move, – height, ○ circle, ■ calibration."""
        h = self.lane_h
        top, bot = y + 1.0, y + h * 0.4
        mid = (top + bot) / 2
        r = max((bot - top) / 2, 2.0)
        if kind == "takeoff":
            p.drawPolygon([QPointF(x, top), QPointF(x - r, bot), QPointF(x + r, bot)])
        elif kind == "land":
            p.drawPolygon([QPointF(x - r, top), QPointF(x + r, top), QPointF(x, bot)])
        elif kind in ("code", "code_z"):
            p.drawLine(QPointF(x, top), QPointF(x, bot))
        elif kind == "set_z":
            p.drawLine(QPointF(x - r, mid), QPointF(x + r, mid))
        elif kind in ("circle", "circle_z"):
            p.save()
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(x, mid), r * 0.8, r * 0.8)
            p.restore()
        elif kind == "calibrate":
            p.save()
            p.setBrush(p.pen().color())
            p.drawRect(QRectF(x - r * 0.7, mid - r * 0.7, r * 1.4, r * 1.4))
            p.restore()

    def _paint_focus_bar(self, p):
        if self.hasFocus():
            p.fillRect(QRectF(0, 0, 2, self.height()), theme.color("accent"))

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.update()

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.update()

    # ---- mouse and keys ----------------------------------------------------------------------------

    def _tick_at(self, pos):
        n = self.lane_of(pos.y())
        if n is None:
            return None
        y = (pos.y() % self.lane_h)
        if y > self.lane_h * 0.45:
            return None
        best = None
        for tn, t, kind, line, args in self.ticks:
            d = abs(self.x_of(t) - pos.x())
            if tn == n and d <= TICK_HIT_PX and (best is None or d < best[0]):
                best = (d, (n, t, kind, line, args))
        return best[1] if best else None

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or not self.numbers:
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        pos = e.position()
        if pos.x() < LABEL_W:
            n = self.lane_of(pos.y())
            self.drone_selected.emit(None if n is None or n == self.focus else n)
            return
        if self.strip_rect().contains(pos):
            tick = self._tick_at(pos)
            if tick:
                self.step_clicked.emit(tick[0], tick[3] or 0)
            self._drag = True
            self.time_selected.emit(self.t_of(pos.x()))

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self._drag:
            self.time_selected.emit(self.t_of(pos.x()))
            return
        n = self.lane_of(pos.y())
        if n is None or not self.show_obj or not self.strip_rect().contains(pos):
            QToolTip.hideText()
            return
        tick = self._tick_at(pos)
        t = self.t_of(pos.x())
        if tick:
            _n, st, kind, line, args = tick
            text = f"Дрон {n}: {STEP_NAME.get(kind, kind)}, {step_text(kind, args)}\n{st:.1f} с" \
                   + (f", строка {line}" if line else "")
        else:
            name, rgb = self.show_obj.drones[n].color_at(t)
            text = f"Дрон {n}, {t:.1f} с\nСветодиод: {name if any(rgb) else 'выключен'} {tuple(rgb)}"
        QToolTip.showText(e.globalPosition().toPoint(), text, self)

    def mouseReleaseEvent(self, e):
        self._drag = False

    def leaveEvent(self, e):
        QToolTip.hideText()

    def keyPressEvent(self, e):
        k = e.key()
        step = 10.0 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
        if k in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            sign = -1 if k == Qt.Key.Key_Left else 1
            self.time_selected.emit(min(max(self.t + sign * step, 0.0), self.duration))
        elif k in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.numbers:
            i = self.numbers.index(self.focus) if self.focus in self.numbers else None
            d = -1 if k == Qt.Key.Key_Up else 1
            i = (0 if d > 0 else len(self.numbers) - 1) if i is None else min(max(i + d, 0), len(self.numbers) - 1)
            self.drone_selected.emit(self.numbers[i])
        else:
            super().keyPressEvent(e)
