"""Top/side preview of the simulated show and the per-drone timeline."""
from itertools import combinations
from math import dist

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from litebee.show import CELL_CM, GRID_W
from litebee.mission import DEFAULT_MAX_HEIGHT_CM, resolve_max_height

from . import theme
from .drone_art import HEIGHT_CM, WIDTH_CM, paint_badge, paint_drone, paint_tag, text_on
from .mat_map import MIN_DRONE_PX, WORLD_MAX, WORLD_MIN, LiveDrone, MatMapView

Z_MAX = 180            # top of the side view; grows when the height limit is higher

STEP_GLYPH = {"calibrate": "К", "takeoff": "↑", "land": "↓", "set_z": "Z", "code": "→",
              "code_z": "↗", "circle": "↻", "circle_z": "↻", "rgb": ""}
STEP_NAME = {"calibrate": "калибровка", "takeoff": "взлёт", "land": "посадка", "set_z": "высота",
             "code": "к клетке", "code_z": "к клетке и высота", "circle": "круг", "circle_z": "круг с подъёмом",
             "rgb": "цвет"}


def led_qcolor(rgb):
    return QColor(*rgb)


class PreviewWidget(QWidget):
    """Top view (the mat map, app/mat_map.py) or side view of all drones at time t."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_obj = None
        self.paths = {}
        self.t = 0.0
        self.max_height_cm = DEFAULT_MAX_HEIGHT_CM
        self.side = False
        self.mat = MatMapView(self)
        self.mat.setGeometry(self.rect())
        self.setMinimumSize(320, 220)
        self.setAccessibleName("Превью траекторий")

    @property
    def threshold(self):
        return self.mat.threshold

    @threshold.setter
    def threshold(self, cm):
        self.mat.threshold = cm
        self.update()

    def resizeEvent(self, e):
        self.mat.setGeometry(self.rect())

    def set_show(self, show):
        self.show_obj = show
        self.paths = show.paths() if show else {}
        self.mat.set_show(show, self.paths)
        self.update()

    def set_time(self, t):
        self.t = t
        self.mat.set_time(t)
        self.update()

    def set_live(self, views, labels=None):
        """Live drones from telemetry (session.DroneView list); `labels` maps ip -> number shown in the badge."""
        labels = labels or {}
        self.mat.set_live([LiveDrone.from_view(v, labels.get(v.ip)) for v in views])

    def set_max_height(self, cm):
        """Height limit of the dashed line (SafetyError outside 20-200 cm)."""
        self.max_height_cm = resolve_max_height(cm)
        self.update()

    def limit_text(self):
        return f"лимит {self.max_height_cm} см"

    @property
    def z_max(self):
        """Top of the side view: at least Z_MAX, and 20 cm above the limit line."""
        return max(Z_MAX, -(-(self.max_height_cm + 20) // 20) * 20)

    def set_side(self, side: bool):
        self.side = side
        self.mat.setVisible(not side)
        self.update()

    # ---- geometry of the side view ---------------------------------------------------------------------

    def _layout(self):
        m = 26
        w, h = self.width() - 2 * m, self.height() - 2 * m - 18
        k = max(min(w / (WORLD_MAX - WORLD_MIN), h / self.z_max), 0.1)
        span_w = (WORLD_MAX - WORLD_MIN) * k
        span_h = self.z_max * k
        return k, m + (w - span_w) / 2, m + (h - span_h) / 2, span_h

    def to_screen(self, x, y, z=0.0):
        """Side view: x along the mat, z height; `y` is unused."""
        k, ox, oy, span_h = self._layout()
        return QPointF(ox + (x - WORLD_MIN) * k, oy + span_h - z * k)

    # ---- painting (side view; the top view is the child MatMapView) ----------------------------------

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), theme.color("panel"))
        if self.side:
            p.setFont(self._font(11))
            self._paint_side_grid(p)
            if self.show_obj and self.paths:
                self._paint_drones(p)
            else:
                p.setPen(theme.color("text2"))
                p.setFont(self._font(13))
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет шоу для показа")
        p.end()

    def _font(self, px):
        f = QFont(self.font())
        f.setPixelSize(px)
        return f

    def _paint_side_grid(self, p):
        grid = QPen(theme.color("grid"))
        p.setPen(grid)
        for z in range(0, self.z_max + 1, 20):
            p.drawLine(self.to_screen(WORLD_MIN, 0, z), self.to_screen(WORLD_MAX, 0, z))
            p.setPen(theme.color("text2"))
            p.drawText(self.to_screen(WORLD_MIN, 0, z) + QPointF(-24, 4), str(z))
            p.setPen(grid)
        for i in range(GRID_W + 1):
            v = WORLD_MIN + i * CELL_CM
            p.drawLine(self.to_screen(v, 0, 0), self.to_screen(v, 0, self.z_max))
        lim = QPen(theme.color("warn"))
        lim.setStyle(Qt.PenStyle.DashLine)
        p.setPen(lim)
        y = self.max_height_cm
        p.drawLine(self.to_screen(WORLD_MIN, 0, y), self.to_screen(WORLD_MAX, 0, y))
        p.setPen(theme.color("warn"))
        p.drawText(self.to_screen(WORLD_MIN, 0, y) + QPointF(6, -4), self.limit_text())
        p.setPen(theme.color("text2"))
        p.drawText(8, self.height() - 8, "Вид сбоку: по горизонтали X, по вертикали высота, см")

    def _paint_drones(self, p):
        show = self.show_obj
        pos = show.positions_at(self.t, self.paths)
        k = self._layout()[0]
        s = max(k, 1.5 * MIN_DRONE_PX / WIDTH_CM)       # the side view is flat: draw it larger
        for n, path in self.paths.items():          # dashed trail behind each drone
            color = show.drones[n].color_at(self.t)[1]
            c = led_qcolor(color) if any(color) else theme.color("text2")
            c.setAlpha(150)
            pen = QPen(c)
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidthF(1.2)
            p.setPen(pen)
            pts = [self._pt(seg[2]) for seg in path if seg[0] < self.t]
            pts.append(self._pt(pos[n]))
            for a, b in zip(pts, pts[1:]):
                p.drawLine(a, b)
        ring = QPen(theme.color("danger"))
        ring.setWidthF(2)
        for a, b in combinations(sorted(pos), 2):  # close pairs (3D distance below the threshold)
            if dist(pos[a], pos[b]) < self.threshold:
                p.setPen(ring)
                p.setBrush(Qt.BrushStyle.NoBrush)
                pa, pb = self._pt(pos[a]), self._pt(pos[b])
                mid = (pa + pb) / 2
                r = (pa - pb).manhattanLength() / 2 + 20
                p.drawEllipse(mid, r, r)
        for n in sorted(pos):
            paint_drone(p, self._pt(pos[n]), s, 0, show.drones[n].color_at(self.t)[1], "side")
        for n in sorted(pos):
            rgb = show.drones[n].color_at(self.t)[1]
            c = self._pt(pos[n]) - QPointF(0, HEIGHT_CM * s + 10)
            r = paint_badge(p, c, str(n), rgb)
            paint_tag(p, self._pt(pos[n]) + QPointF(-14, 9), f"{pos[n][0]:.0f}")

    def _pt(self, xyz):
        return self.to_screen(xyz[0], xyz[1], xyz[2])


class TimelineWidget(QWidget):
    """One lane per drone; a block per step coloured with the LED colour; a vertical time line."""
    time_selected = Signal(float)
    step_clicked = Signal(int, int)       # drone number, source line

    LABEL_W, GAP = 64, 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_obj = None
        self.t = 0.0
        self.blocks = {}        # drone -> [(t0, t1, kind, rgb, line)]
        self.duration = 1.0
        self.setMinimumHeight(130)
        self.setMouseTracking(True)
        self.setAccessibleName("Временная шкала")

    def set_show(self, show):
        self.show_obj = show
        self.blocks = {}
        self.duration = max(show.duration, 0.1) if show else 1.0
        if show:
            for n, d in sorted(show.drones.items()):
                t, cur, out = 0.0, (0, 0, 0), []
                for s in d.steps:
                    if s.kind == "rgb":
                        cur = s.args["rgb"]
                    out.append((t, t + s.seconds, s.kind, cur, s.line))
                    t += s.seconds
                self.blocks[n] = out
        self.update()

    def set_time(self, t):
        self.t = t
        self.update()

    @property
    def LANE_H(self):
        """Lane height adapts to the number of drones (6..22 px)."""
        n = max(len(self.blocks), 1)
        return int(min(22, max(6, (self.height() - 8) / n - self.GAP)))

    def _x(self, t):
        w = max(self.width() - self.LABEL_W - 12, 10)
        return self.LABEL_W + t / self.duration * w

    def _t_at(self, x):
        w = max(self.width() - self.LABEL_W - 12, 10)
        return min(max((x - self.LABEL_W) / w * self.duration, 0.0), self.duration)

    def mousePressEvent(self, e):
        self._seek(e)
        if e.button() == Qt.MouseButton.LeftButton:
            lane = int((e.position().y() - 4) // (self.LANE_H + self.GAP))
            drones = sorted(self.blocks)
            if 0 <= lane < len(drones):
                t = self._t_at(e.position().x())
                for t0, t1, kind, rgb, line in self.blocks[drones[lane]]:
                    if t0 <= t <= t1 and line:
                        self.step_clicked.emit(drones[lane], line)
                        break

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._seek(e)

    def _seek(self, e):
        self.time_selected.emit(self._t_at(e.position().x()))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), theme.color("panel"))
        f = QFont(self.font())
        f.setPixelSize(11)
        p.setFont(f)
        if not self.blocks:
            p.setPen(theme.color("text2"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Нажмите «Проверить», чтобы построить шкалу")
            return
        y = 4
        for n, blocks in sorted(self.blocks.items()):
            p.setPen(theme.color("text2"))
            p.drawText(QRectF(4, y, self.LABEL_W - 8, self.LANE_H), Qt.AlignmentFlag.AlignVCenter, f"Дрон {n}")
            for t0, t1, kind, rgb, line in blocks:
                x0, x1 = self._x(t0), max(self._x(t1), self._x(t0) + 2)
                r = QRectF(x0, y, x1 - x0 - 0.5, self.LANE_H)
                led = led_qcolor(rgb)
                off = not any(rgb)
                p.setPen(QPen(theme.color("border") if not off else theme.color("text2"), 0.5))
                p.setBrush(theme.color("card") if off else led)
                p.drawRoundedRect(r, 3, 3)
                glyph = STEP_GLYPH.get(kind, "")
                if glyph and r.width() > 14:
                    p.setPen(theme.color("text") if off else text_on(led))
                    p.drawText(r, Qt.AlignmentFlag.AlignCenter, glyph)
            y += self.LANE_H + self.GAP
        p.setPen(QPen(theme.color("text"), 1.5))
        x = self._x(self.t)
        p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
