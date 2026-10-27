"""Our own vector model of the LiteBee Wing, drawn with QPainter (no photos, no downloaded assets).

Real size 209 x 184 x 56 mm, wheelbase 148 mm (docs/REFERENCES.md): a white body with a dark camera
lens at the nose, a white square lid over a grey battery block, four grey X-shaped building-block arms
with holes, a silver motor and a translucent two-blade propeller at each end, short landing legs.
No guard rings: the real LiteBee Wing has none.

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

def _blade(r):
    """One tapered propeller blade lying along +x from the hub."""
    b = QPainterPath()
    b.moveTo(0, 0.25)
    b.cubicTo(r * 0.25, 0.95, r * 0.75, 0.85, r, 0.15)
    b.cubicTo(r * 0.8, -0.35, r * 0.35, -0.5, 0, -0.25)
    b.closeSubpath()
    return b


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
    # arms: grey building-block bars with a darker edge and a row of holes
    for mx, my in MOTORS:
        p.setPen(_pen(_col("drone_dark"), 2.1, s, 2.1, Qt.PenCapStyle.FlatCap))
        p.drawLine(QPointF(0, 0), QPointF(mx, my))
    for mx, my in MOTORS:
        p.setPen(_pen(_col("drone_grey"), 1.6, s, 1.6, Qt.PenCapStyle.FlatCap))
        p.drawLine(QPointF(0, 0), QPointF(mx, my))
    if s * 6 >= 26:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_col("drone_dark"))
        for mx, my in MOTORS:
            for t in (0.45, 0.62, 0.79):
                p.drawEllipse(QPointF(mx * t, my * t), 0.26, 0.26)
    # feet: the arms continue outwards past the motors (the width of 20.9 cm is measured across them)
    for mx, my in MOTORS:
        end = QPointF(mx + (1 if mx > 0 else -1) * GUARD_R, my + (1 if my > 0 else -1) * 0.5)
        p.setPen(_pen(_col("drone_dark"), 1.9, s, 1.9, Qt.PenCapStyle.FlatCap))
        p.drawLine(QPointF(mx, my), end)
        p.setPen(_pen(_col("drone_grey"), 1.4, s, 1.4, Qt.PenCapStyle.FlatCap))
        p.drawLine(QPointF(mx, my), end)
    # motors and translucent two-blade propellers
    for (mx, my), ang in zip(MOTORS, PROP_ANGLES):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_col("drone_grey"))
        p.drawEllipse(QPointF(mx, my), 1.35, 1.35)
        p.setBrush(_col("drone_guard"))
        p.drawEllipse(QPointF(mx, my), 0.95, 0.95)
        p.save()
        p.translate(mx, my)
        p.rotate(ang)
        p.setPen(_pen(_col("drone_guard", 170), 0.12, s, 0.8))
        p.setBrush(_col("drone_body", 150))
        for k in (0, 180):
            p.save()
            p.rotate(k)
            p.drawPath(_blade(PROP_R))
            p.restore()
        p.restore()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_col("drone_body"))
        p.drawEllipse(QPointF(mx, my), 0.42, 0.42)
    # body: white shell, camera block in front, grey battery block at the back, white square lid
    p.setPen(_pen(_col("drone_grey"), 0.35, s, 0.8))
    p.setBrush(_col("drone_body"))
    p.drawRoundedRect(QRectF(-2.9, -4.4, 5.8, 8.6), 1.7, 1.7)
    p.setPen(_pen(_col("drone_dark"), 0.3, s, 0.6))
    p.setBrush(_col("drone_grey"))
    p.drawRoundedRect(QRectF(-2.3, 0.6, 4.6, 3.3), 0.5, 0.5)
    p.setBrush(_col("drone_body"))
    p.drawRoundedRect(QRectF(-2.45, -1.9, 4.9, 4.2), 0.9, 0.9)
    if s * 4.9 >= 26:                                      # studs on the camera block, only when visible
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_col("drone_grey", 120))
        for i in range(3):
            p.drawEllipse(QPointF(-1.0 + i * 1.0, -3.3), 0.3, 0.3)
    # LED ring around the body
    ring = _pen(QColor(*led) if led else _col("drone_dark"), 0.7 if led else 0.35, s, 1.4 if led else 0.8)
    p.setPen(ring)
    p.setBrush(none)
    p.drawRoundedRect(QRectF(-2.65, -2.2, 5.3, 6.2), 1.4, 1.4)
    # camera lens at the nose: dark lens in a lighter ring
    p.setPen(_pen(_col("drone_grey"), 0.3, s, 0.8))
    p.setBrush(_col("drone_dark"))
    p.drawEllipse(QPointF(0, -3.5), 0.95, 0.95)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_col("drone_guard"))
    p.drawEllipse(QPointF(-0.3, -3.8), 0.25, 0.25)
    # nose mark: a small triangle in front of the propellers
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
    p.setPen(_pen(_col("drone_grey"), 1.1, s, 1.4, Qt.PenCapStyle.FlatCap))
    for x in (-5.8, 5.8):
        p.drawLine(QPointF(x, 0), QPointF(x * 0.9, -1.8))
    # arm bar with a darker edge
    p.setPen(_pen(_col("drone_dark"), 1.5, s, 1.8, Qt.PenCapStyle.FlatCap))
    p.drawLine(QPointF(-WHEELBASE_CM / 2, -3.0), QPointF(WHEELBASE_CM / 2, -3.0))
    p.setPen(_pen(_col("drone_grey"), 1.1, s, 1.4, Qt.PenCapStyle.FlatCap))
    p.drawLine(QPointF(-WHEELBASE_CM / 2, -3.0), QPointF(WHEELBASE_CM / 2, -3.0))
    # silver motor cylinders
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_col("drone_guard"))
    for x in (-WHEELBASE_CM / 2, WHEELBASE_CM / 2):
        p.drawRoundedRect(QRectF(x - 0.9, -4.3, 1.8, 2.2), 0.3, 0.3)
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
    p.setBrush(_col("drone_dark"))
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
    """A small plate with the drone number: neutral fill, Chalk digits, the LED colour as its outline, so the
    plate is readable on any LED colour and the only saturated pixel is the LED itself. Returns its rectangle."""
    text = str(text)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    f = theme.ui_font(px, True)
    painter.setFont(f)
    w = painter.fontMetrics().horizontalAdvance(text) + 10
    r = QRectF(center.x() - max(w, px + 6) / 2, center.y() - (px + 6) / 2, max(w, px + 6), px + 6)
    led = QColor(*rgb) if rgb and any(rgb) else None
    painter.setPen(QPen(led.lighter(125) if (led and outline != "accent") else theme.color(outline), 1.4))
    painter.setBrush(theme.color("card") if filled else theme.color("stage"))
    painter.drawRoundedRect(r, 4, 4)
    painter.setPen(theme.color("text"))
    painter.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()
    return r


def paint_tag(painter: QPainter, left_mid, text, px=11):
    """Small secondary text (height, x) on a card-coloured plate, so it stays readable over the grid.
    `left_mid` is the middle of its left edge."""
    painter.save()
    painter.setFont(theme.mono_font(px))
    w = painter.fontMetrics().horizontalAdvance(text) + 8
    r = QRectF(left_mid.x(), left_mid.y() - (px + 4) / 2, w, px + 4)
    painter.setPen(Qt.PenStyle.NoPen)
    c = theme.color("stage")
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
        self.led = led_rgb("accent")                 # Beacon
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
        p.setFont(theme.ui_font(12))
        p.setPen(theme.color("text2"))
        p.drawText(QRectF(0, h - 22, w, 20), Qt.AlignmentFlag.AlignCenter,
                   "LiteBee Wing: 209 × 184 × 56 мм, колёсная база 148 мм. Нос — бирюзовый треугольник")
        p.end()
