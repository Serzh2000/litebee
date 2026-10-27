"""Our own vector model of the LiteBee Wing, drawn with QPainter (no photos, no downloaded assets).

Real size 209 x 184 x 56 mm, wheelbase 148 mm (docs/REFERENCES.md): a white body with a round camera
lens at the nose, a grey top block with a stud grid, four grey X-shaped arms with a motor and a white
two-blade propeller at each end, grey guard rings joined by arcs, short landing legs.

`paint_drone` draws it to true scale: `scale_cm_to_px` is pixels per centimetre of the mat.
All colours come from theme tokens (app/theme.qss).
"""
from math import radians, sin

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme

WIDTH_CM, LENGTH_CM, HEIGHT_CM, WHEELBASE_CM = 20.9, 18.4, 5.6, 14.8
MOTOR_X, MOTOR_Y = 5.9, 4.5                    # motor centres, (5.9^2 + 4.5^2)^0.5 * 2 = 14.8 cm wheelbase
GUARD_R = 4.3                                  # guard ring radius around a motor
PROP_R = 3.3                                   # half the propeller span
MOTORS = ((-MOTOR_X, -MOTOR_Y), (MOTOR_X, -MOTOR_Y), (MOTOR_X, MOTOR_Y), (-MOTOR_X, MOTOR_Y))
PROP_ANGLES = (28, -28, 28, -28)               # fixed blade angles, only a visual hint


def led_rgb(led):
    """None, (r, g, b), QColor or a theme token name -> (r, g, b) or None when the LED is off."""
    if led is None:
        return None
    if isinstance(led, str):
        c = theme.color(led) if led in theme.TOKENS else QColor(led)
        led = (c.red(), c.green(), c.blue())
    elif isinstance(led, QColor):
        led = (led.red(), led.green(), led.blue())
    led = tuple(int(v) for v in led)
    return led if any(led) else None


def _col(token, alpha=255):
    c = theme.color(token)
    c.setAlpha(alpha)
    return c


def _pen(color, width_cm, s, min_px=1.0, cap=Qt.PenCapStyle.RoundCap):
    """A pen whose width is given in cm but never thinner than `min_px` on screen."""
    pen = QPen(color)
    pen.setWidthF(max(width_cm, min_px / max(s, 1e-6)))
    pen.setCapStyle(cap)
    return pen


def drone_extent_px(scale_cm_to_px):
    """Width of the drone (guard to guard) in pixels."""
    return WIDTH_CM * scale_cm_to_px


def paint_drone(painter: QPainter, center, scale_cm_to_px, heading_deg=0.0, led_color=None, view="top",
                selected=False, glow=True):
    """Draw the drone to true scale.

    `center` (QPointF, pixels): the middle of the drone seen from above, or the point where its legs touch
    the ground for the side view. `scale_cm_to_px`: pixels per cm. `heading_deg`: 0 = nose towards +y of the
    mat (up on the screen), clockwise positive. The side view faces right unless sin(heading) < 0.
    `led_color`: (r, g, b), QColor, token name or None for LED off. `selected`: dashed accent ring.
    """
    if view not in ("top", "side"):
        raise ValueError("view must be 'top' or 'side'")
    s = float(scale_cm_to_px)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(QPointF(center))
    if view == "top":
        painter.rotate(heading_deg)
        painter.scale(s, s)
        _top(painter, s, led_rgb(led_color), selected, glow)
    else:
        painter.scale(-s if sin(radians(heading_deg)) < -1e-9 else s, s)
        _side(painter, s, led_rgb(led_color), selected, glow)
    painter.restore()


# ---- top view (local frame in cm, nose towards -y of the screen) ---------------------------------------

def _top(p, s, led, selected, glow):
    none = Qt.BrushStyle.NoBrush
    p.setBrush(none)
    if led and glow:                                       # LED glow: steps of falling opacity, no gradient
        for r, a in ((9.4, 26), (7.4, 44), (5.6, 70)):
            c = QColor(*led)
            c.setAlpha(a)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(0, 0), r, r)
    # guards: a ring around every motor, joined by the outer arcs
    guard = _pen(_col("drone_guard"), 0.55, s)
    p.setPen(guard)
    p.setBrush(none)
    for mx, my in MOTORS:
        p.drawEllipse(QPointF(mx, my), GUARD_R, GUARD_R)
    ex, ey = MOTOR_X, MOTOR_Y + GUARD_R
    outer = QPainterPath()
    outer.moveTo(-ex, -ey)
    outer.quadTo(0, -ey - 0.3, ex, -ey)                    # front arc
    outer.moveTo(ex + GUARD_R, -MOTOR_Y)
    outer.lineTo(ex + GUARD_R, MOTOR_Y)      # right arc
    outer.moveTo(ex, ey)
    outer.quadTo(0, ey + 0.3, -ex, ey)                     # rear arc
    outer.moveTo(-ex - GUARD_R, MOTOR_Y)
    outer.lineTo(-ex - GUARD_R, -MOTOR_Y)   # left arc
    p.drawPath(outer)
    # propeller disc hint
    for mx, my in MOTORS:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_col("drone_body", 26))
        p.drawEllipse(QPointF(mx, my), PROP_R, PROP_R)
    # arms
    p.setPen(_pen(_col("drone_grey"), 1.5, s, 1.5))
    for mx, my in MOTORS:
        p.drawLine(QPointF(0, 0), QPointF(mx, my))
    # motors and two-blade propellers
    for (mx, my), ang in zip(MOTORS, PROP_ANGLES):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_col("drone_dark"))
        p.drawEllipse(QPointF(mx, my), 1.15, 1.15)
        p.save()
        p.translate(mx, my)
        p.rotate(ang)
        p.setBrush(_col("drone_body", 235))
        p.drawEllipse(QPointF(0, 0), PROP_R, 0.62)         # one ellipse = both blades
        p.restore()
        p.setBrush(_col("drone_grey"))
        p.drawEllipse(QPointF(mx, my), 0.5, 0.5)
    # body
    p.setPen(_pen(_col("drone_grey"), 0.35, s, 0.8))
    p.setBrush(_col("drone_body"))
    p.drawRoundedRect(QRectF(-2.9, -4.4, 5.8, 8.6), 1.7, 1.7)
    # top block with the stud grid
    p.setPen(_pen(_col("drone_dark"), 0.3, s, 0.6))
    p.setBrush(_col("drone_grey"))
    p.drawRoundedRect(QRectF(-2.1, -1.9, 4.2, 5.1), 0.5, 0.5)
    if s * 4.2 >= 26:                                      # studs only when they are big enough to see
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_col("drone_body", 200))
        for i in range(3):
            for j in range(4):
                p.drawEllipse(QPointF(-1.2 + i * 1.2, -0.95 + j * 1.2), 0.38, 0.38)
    # LED ring around the body
    ring = _pen(QColor(*led) if led else _col("drone_dark"), 0.7 if led else 0.35, s, 1.4 if led else 0.8)
    p.setPen(ring)
    p.setBrush(none)
    p.drawRoundedRect(QRectF(-2.55, -2.3, 5.1, 6.0), 1.4, 1.4)
    # camera lens at the nose
    p.setPen(_pen(_col("drone_grey"), 0.3, s, 0.8))
    p.setBrush(_col("on_accent"))
    p.drawEllipse(QPointF(0, -3.1), 1.15, 1.15)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_col("drone_guard"))
    p.drawEllipse(QPointF(-0.3, -3.4), 0.3, 0.3)
    # nose mark: a small triangle in front of the guard
    tip = MOTOR_Y + GUARD_R + 1.0
    nose = QPainterPath()
    nose.moveTo(0, -tip - 2.2)
    nose.lineTo(-1.35, -tip)
    nose.lineTo(1.35, -tip)
    nose.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_col("accent"))
    p.drawPath(nose)
    if selected:
        sel = _pen(_col("accent"), 0.5, s, 1.5)
        sel.setStyle(Qt.PenStyle.DashLine)
        p.setPen(sel)
        p.setBrush(none)
        p.drawEllipse(QPointF(0, 0), 13.0, 13.0)


# ---- side view (local frame in cm, y up is negative, origin = ground contact point) ---------------------

def _side(p, s, led, selected, glow):
    none = Qt.BrushStyle.NoBrush
    if led and glow:
        for r, a in ((8.0, 24), (6.2, 42), (4.4, 66)):
            c = QColor(*led)
            c.setAlpha(a)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(0, -2.4), r, r * 0.7)
    # landing legs
    p.setPen(_pen(_col("drone_grey"), 0.7, s, 1.2))
    for x in (-5.4, 5.4):
        p.drawLine(QPointF(x, 0), QPointF(x * 0.85, -1.5))
    # guard seen from the side: a thin band
    p.setPen(_pen(_col("drone_guard"), 0.45, s, 1.0))
    p.drawLine(QPointF(-WIDTH_CM / 2, -2.4), QPointF(WIDTH_CM / 2, -2.4))
    # arm bar, motors
    p.setPen(_pen(_col("drone_grey"), 1.0, s, 1.4))
    p.drawLine(QPointF(-WHEELBASE_CM / 2, -3.3), QPointF(WHEELBASE_CM / 2, -3.3))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_col("drone_dark"))
    for x in (-WHEELBASE_CM / 2, WHEELBASE_CM / 2):
        p.drawRect(QRectF(x - 0.8, -4.2, 1.6, 2.0))
    # propeller discs (thin ellipses), left one a little dimmer
    p.setBrush(_col("drone_body", 220))
    for x in (-WHEELBASE_CM / 2, WHEELBASE_CM / 2):
        p.drawEllipse(QPointF(x, -4.5), PROP_R, 0.3)
    # body, top block with studs
    p.setPen(_pen(_col("drone_grey"), 0.35, s, 0.8))
    p.setBrush(_col("drone_body"))
    p.drawRoundedRect(QRectF(-4.3, -4.5, 8.6, 3.2), 1.1, 1.1)
    p.setBrush(_col("drone_grey"))
    p.drawRoundedRect(QRectF(-2.6, -5.6 + 0.4, 5.2, 1.5), 0.4, 0.4)
    if s * 5.2 >= 26:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_col("drone_body", 200))
        for i in range(4):
            p.drawRect(QRectF(-2.2 + i * 1.2, -5.6, 0.8, 0.4))
    # LED strip on the body
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(*led) if led else _col("drone_dark"))
    p.drawRoundedRect(QRectF(-2.8, -2.2, 5.6, 0.7), 0.35, 0.35)
    # camera lens at the nose (right)
    p.setPen(_pen(_col("drone_grey"), 0.3, s, 0.8))
    p.setBrush(_col("on_accent"))
    p.drawEllipse(QPointF(4.3, -2.9), 0.95, 0.95)
    # nose mark
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_col("accent"))
    tri = QPainterPath()
    tri.moveTo(7.2, -2.9)
    tri.lineTo(5.9, -3.9)
    tri.lineTo(5.9, -1.9)
    tri.closeSubpath()
    p.drawPath(tri)
    if selected:
        sel = _pen(_col("accent"), 0.5, s, 1.5)
        sel.setStyle(Qt.PenStyle.DashLine)
        p.setPen(sel)
        p.setBrush(none)
        p.drawRoundedRect(QRectF(-WIDTH_CM / 2 - 0.8, -7.2, WIDTH_CM + 1.6, 8.0), 1.5, 1.5)


# ---- number badge ----------------------------------------------------------------------------------

def text_on(c: QColor) -> QColor:
    lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    return theme.color("on_accent") if lum > 140 else theme.color("text")


def paint_badge(painter: QPainter, center, text, rgb=None, px=12, outline="text2", filled=True):
    """A pill with the drone number, readable on any LED colour. Returns its rectangle."""
    text = str(text)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    f = QFont(painter.font())
    f.setPixelSize(px)
    f.setWeight(QFont.Weight.Medium)
    painter.setFont(f)
    w = painter.fontMetrics().horizontalAdvance(text) + 10
    r = QRectF(center.x() - max(w, px + 6) / 2, center.y() - (px + 6) / 2, max(w, px + 6), px + 6)
    led = QColor(*rgb) if rgb and any(rgb) else None
    fill = led if (led and filled) else theme.color("card")
    painter.setPen(QPen(theme.color(outline) if not led else led.lighter(130), 1.4))
    painter.setBrush(fill)
    painter.drawRoundedRect(r, r.height() / 2, r.height() / 2)
    painter.setPen(text_on(fill))
    painter.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()
    return r


def paint_tag(painter: QPainter, left_mid, text, px=11):
    """Small secondary text (height, x) on a card-coloured plate, so it stays readable over the grid.
    `left_mid` is the middle of its left edge."""
    painter.save()
    f = QFont(painter.font())
    f.setPixelSize(px)
    painter.setFont(f)
    w = painter.fontMetrics().horizontalAdvance(text) + 8
    r = QRectF(left_mid.x(), left_mid.y() - (px + 4) / 2, w, px + 4)
    painter.setPen(Qt.PenStyle.NoPen)
    c = theme.color("card")
    c.setAlpha(225)
    painter.setBrush(c)
    painter.drawRoundedRect(r, 4, 4)
    painter.setPen(theme.color("text2"))
    painter.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()
    return r


# ---- widgets ---------------------------------------------------------------------------------------------

class DroneIcon(QWidget):
    """Small top-view drone for a drone card; the LED colour mirrors the card state."""

    def __init__(self, size=38, parent=None):
        super().__init__(parent)
        self.led = None
        self.setFixedSize(size, size)
        self.setAccessibleName("Рисунок дрона")

    def set_led(self, led):
        led = led_rgb(led)
        if led != self.led:
            self.led = led
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        s = min(self.width(), self.height()) / (WIDTH_CM + 5)
        paint_drone(p, QPointF(self.width() / 2, self.height() / 2 + 0.5), s, 0, self.led, "top")
        p.end()


class DroneArt(QWidget):
    """Larger picture for the empty state: the drone from above and from the side, with its dimensions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.led = (106, 169, 255)
        self.setMinimumSize(520, 220)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("Рисунок дрона LiteBee Wing: вид сверху и сбоку, 209 на 184 на 56 мм")

    def sizeHint(self):
        return QSize(520, 220)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        s = min(w * 0.5 / (WIDTH_CM + 6), (h - 34) / (LENGTH_CM + 8))
        top_c = QPointF(w * 0.27, (h - 24) / 2)
        paint_drone(p, top_c, s, 0, self.led, "top")
        side_c = QPointF(w * 0.74, (h - 24) / 2 + HEIGHT_CM * s / 2)
        paint_drone(p, side_c, s, 0, self.led, "side")
        f = QFont(self.font())
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(theme.color("text2"))
        p.drawText(QRectF(0, h - 22, w, 20), Qt.AlignmentFlag.AlignCenter,
                   "LiteBee Wing: 209 × 184 × 56 мм, колёсная база 148 мм. Нос — синий треугольник")
        p.end()
