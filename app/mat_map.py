"""Mat map: the 12 x 12 marker mat seen from above, with zoom, pan, cell numbers and live drones.

Mat geometry (docs/DESIGN.md): 12 x 12 cells of 40 cm, cell = col + 12 * row. Cell 0 is at the bottom
left, numbers grow to the right and up, so cell 143 is at the top right. A cell centre is at
(x, y) = (col * 40, row * 40) cm. Telemetry reports (y, x), a drone at x = y = 0 has NO position fix
and is never drawn as cell 0.

The coordinate helpers at the top of this module have no Qt dependency beyond QPointF/QRectF, so they are
unit-tested without a window; `MatMapView` is the widget.
"""
from bisect import bisect_left
from collections import deque
from dataclasses import dataclass
from itertools import combinations
from math import ceil, dist, floor
from random import Random
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QMenu, QToolButton, QToolTip, QWidget

from litebee.mission import CELL_CM, GRID_CELLS, GRID_W
from litebee.safety import MIN_APPROACH_CM

from . import theme
from .drone_art import WIDTH_CM, paint_badge, paint_drone, paint_tag

HALF = CELL_CM / 2
WORLD_MIN, WORLD_MAX = -HALF, (GRID_W - 1) * CELL_CM + HALF          # -20 .. 460 cm
ACCURACY_CM = 15                    # live position accuracy ring (docs/DESIGN.md: about +-10-15 cm)
TRAIL_LEN = 40                      # last live positions kept per drone
MIN_DRONE_PX = 28                   # a drone is never drawn narrower than this; true scale when zoomed in
QR_MIN_CELL_PX = 26
TARGET_TEXT_CELL_PX = 56
COORD_TEXT_CELL_PX = 104
SCALE_MAX = 10.0                    # px per cm (a cell is then 400 px)
HINT = "Коврик 12×12, клетка 40 см, номер = столбец + 12 × строка. Колесо — масштаб, перетаскивание — сдвиг"


# ---- coordinates: cell <-> row/column <-> cm ---------------------------------------------------------

def cell_rc(cell):
    """Cell number -> (row, col)."""
    _check_cell(cell)
    return divmod(int(cell), GRID_W)


def rc_cell(row, col):
    if not (0 <= row < GRID_W and 0 <= col < GRID_W):
        raise ValueError(f"Строка {row}, столбец {col} вне коврика")
    return col + GRID_W * row


def cell_center_cm(cell):
    """Cell number -> (x, y) of the cell centre in cm: x along the columns, y along the rows."""
    row, col = cell_rc(cell)
    return col * CELL_CM, row * CELL_CM


def cm_to_cell(x, y):
    """Position in cm -> cell number, None outside the mat. A cell spans +-20 cm around its centre."""
    col, row = floor((x + HALF) / CELL_CM), floor((y + HALF) / CELL_CM)
    return col + GRID_W * row if 0 <= col < GRID_W and 0 <= row < GRID_W else None


def cell_text(cell):
    """The status line shown after a click on a cell."""
    row, col = cell_rc(cell)
    x, y = cell_center_cm(cell)
    return f"клетка {cell}, строка {row}, столбец {col}, y={y} см, x={x} см"


def _check_cell(cell):
    if isinstance(cell, bool) or int(cell) != cell or not 0 <= cell < GRID_CELLS:
        raise ValueError(f"Клетка {cell} вне коврика 0-{GRID_CELLS - 1}")


@dataclass
class LiveDrone:
    """A drone seen through telemetry. Without a fix (x = y = 0) it has no position and is not drawn."""
    key: str                        # ip
    label: str                      # number shown in the badge
    x: Optional[int] = None
    y: Optional[int] = None
    z: Optional[int] = None
    has_fix: bool = False
    cell: Optional[int] = None

    @classmethod
    def from_view(cls, v, label=None):
        """From a session.DroneView; None for a drone whose link is lost (no telemetry at all)."""
        if v.x is None or v.y is None:
            return None
        return cls(v.ip, str(label) if label else v.ip.rsplit(".", 1)[-1], v.x, v.y, v.z, bool(v.has_fix and (v.x or v.y)), v.cell)

    @property
    def drawn(self):
        return bool(self.has_fix and (self.x or self.y))


class MatTransform:
    """cm <-> screen pixels: screen = (ox + x * s, oy - y * s), so the mat has cell 0 at the bottom left."""

    def __init__(self, s=1.0, ox=0.0, oy=0.0):
        self.s, self.ox, self.oy = s, ox, oy

    def to_screen(self, x, y):
        return QPointF(self.ox + x * self.s, self.oy - y * self.s)

    def to_cm(self, px, py):
        return (px - self.ox) / self.s, (self.oy - py) / self.s

    def cell_rect(self, cell):
        x, y = cell_center_cm(cell)
        return QRectF(self.to_screen(x - HALF, y + HALF), self.to_screen(x + HALF, y - HALF))

    def cell_at(self, px, py):
        return cm_to_cell(*self.to_cm(px, py))

    @property
    def cell_px(self):
        return CELL_CM * self.s

    def fit(self, rect: QRectF, pad=2.0):
        span = WORLD_MAX - WORLD_MIN
        self.s = max(min((rect.width() - 2 * pad) / span, (rect.height() - 2 * pad) / span), 0.05)
        self.ox = rect.center().x() - (WORLD_MIN + span / 2) * self.s
        self.oy = rect.center().y() + (WORLD_MIN + span / 2) * self.s

    def zoom_at(self, px, py, factor, s_min, s_max=SCALE_MAX):
        s = min(max(self.s * factor, s_min), s_max)
        x, y = self.to_cm(px, py)
        self.s = s
        self.ox, self.oy = px - x * s, py + y * s

    def clamp(self, rect: QRectF, keep=60.0):
        """Keep at least `keep` px of the mat inside `rect`."""
        left, right = self.to_screen(WORLD_MIN, 0).x(), self.to_screen(WORLD_MAX, 0).x()
        top, bottom = self.to_screen(0, WORLD_MAX).y(), self.to_screen(0, WORLD_MIN).y()
        if right < rect.left() + keep:
            self.ox += rect.left() + keep - right
        elif left > rect.right() - keep:
            self.ox -= left - (rect.right() - keep)
        if bottom < rect.top() + keep:
            self.oy += rect.top() + keep - bottom
        elif top > rect.bottom() - keep:
            self.oy -= top - (rect.bottom() - keep)


_QR_CACHE = {}


def qr_modules(cell):
    """A light QR-like 5 x 5 glyph for a cell: three finder corners and cell-specific modules.
    It is decoration, not the real marker code. Returns [(i, j)] of dark modules."""
    if cell not in _QR_CACHE:
        rnd = Random(cell * 7919 + 13)
        mods = {(i, j) for i in (0, 1) for j in (0, 1)} | {(i, j) for i in (3, 4) for j in (0, 1)} \
            | {(i, j) for i in (0, 1) for j in (3, 4)}
        mods |= {(i, j) for i in range(5) for j in range(5) if (i, j) not in mods and rnd.random() < 0.5
                 and not (i < 2 and j < 2)}
        _QR_CACHE[cell] = sorted(mods)
    return _QR_CACHE[cell]


def _alpha(color: QColor, a):
    c = QColor(color)
    c.setAlpha(a)
    return c


def _identity_color(drone):
    """Stable colour of a show drone for paths: its first lit LED colour, else None."""
    for s in drone.steps:
        if s.kind == "rgb" and any(s.args["rgb"]):
            return QColor(*s.args["rgb"])
    return None


class MatMapView(QWidget):
    """The mat from above. Wheel zooms around the cursor, dragging pans, double click or the button fits it."""
    cell_clicked = Signal(int)

    ML, MT, MR, MB = 42, 6, 10, 38          # margins: row labels, top, right, column labels + status line

    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_obj = None
        self.paths = {}
        self.t = 0.0
        self.threshold = MIN_APPROACH_CM
        self.live = []
        self.trails = {}
        self.tf = MatTransform()
        self.auto_fit = True
        self.hover_cell = None
        self.selected_cell = None
        self.show_plan = True
        self.show_qr = True
        self._plan = {}             # drone -> (QPainterPath in cm, QColor or None)
        self._targets = {}          # cell -> [drone numbers]
        self._press = None
        self._moved = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(320, 200)
        self.setAccessibleName("Карта коврика")
        self.fit_button = QToolButton(self)
        self.fit_button.setText("По размеру")
        self.fit_button.setProperty("compact", True)
        self.fit_button.setToolTip("Показать весь коврик (двойной щелчок или клавиша 0)")
        self.fit_button.clicked.connect(self.fit)
        self.fit_button.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    # ---- data ----------------------------------------------------------------------------------------

    def set_show(self, show, paths=None):
        self.show_obj = show
        self.paths = (paths if paths is not None else show.paths()) if show else {}
        self._plan, self._targets = {}, {}
        if show:
            for n, d in show.drones.items():
                path = QPainterPath()
                segs = self.paths.get(n) or []
                if segs:
                    path.moveTo(segs[0][2][0], segs[0][2][1])
                    for seg in segs:
                        path.lineTo(seg[3][0], seg[3][1])
                self._plan[n] = (path, _identity_color(d))
                for s in d.steps:
                    if s.kind in ("code", "code_z") and 0 <= s.args["cell"] < GRID_CELLS:
                        lst = self._targets.setdefault(s.args["cell"], [])
                        if n not in lst:
                            lst.append(n)
        self.update()

    def set_time(self, t):
        self.t = t
        self.update()

    def set_live(self, drones):
        """`drones`: list of LiveDrone. Keeps a trail of the last positions of drones that have a fix."""
        self.live = [d for d in drones if d is not None]
        keys = {d.key for d in self.live}
        for k in list(self.trails):
            if k not in keys:
                del self.trails[k]
        for d in self.live:
            if not d.drawn:
                self.trails.pop(d.key, None)        # a lost fix breaks the trail
                continue
            tr = self.trails.setdefault(d.key, deque(maxlen=TRAIL_LEN))
            if not tr or dist(tr[-1], (d.x, d.y)) >= 1:
                tr.append((d.x, d.y))
        self.update()

    def drawn_live(self):
        """Live drones that have a position and are therefore drawn."""
        return [d for d in self.live if d.drawn]

    # ---- geometry ---------------------------------------------------------------------------------------

    def data_rect(self):
        return QRectF(self.ML, self.MT, max(self.width() - self.ML - self.MR, 10),
                      max(self.height() - self.MT - self.MB, 10))

    def fit(self):
        self.auto_fit = True
        self.tf.fit(self.data_rect())
        self.update()

    def _fit_scale(self):
        t = MatTransform()
        t.fit(self.data_rect())
        return t.s

    def resizeEvent(self, e):
        r = self.data_rect()
        self.fit_button.adjustSize()
        self.fit_button.move(int(r.right() - self.fit_button.width() - 4), int(r.top() + 4))
        if self.auto_fit:
            self.tf.fit(r)
        else:
            self.tf.clamp(r)

    def showEvent(self, e):
        if self.auto_fit:
            self.tf.fit(self.data_rect())

    def cell_at(self, pos):
        if not self.data_rect().contains(pos):
            return None
        return self.tf.cell_at(pos.x(), pos.y())

    def zoom_by(self, factor, pos=None):
        r = self.data_rect()
        pos = pos or r.center()
        self.tf.zoom_at(pos.x(), pos.y(), factor, self._fit_scale() * 0.6)
        self.tf.clamp(r)
        self.auto_fit = False
        self.update()

    # ---- status text -----------------------------------------------------------------------------------

    def status_line(self):
        if self.hover_cell is not None:
            return cell_text(self.hover_cell)
        if self.selected_cell is not None:
            return cell_text(self.selected_cell)
        return HINT

    # ---- mouse ----------------------------------------------------------------------------------------

    def wheelEvent(self, e):
        dy = e.angleDelta().y()
        if dy:
            self.zoom_by(1.0015 ** dy, e.position())
        e.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press, self._moved = e.position(), False
            self.setFocus()

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self._press is not None and e.buttons() & Qt.MouseButton.LeftButton:
            d = pos - self._press
            if self._moved or abs(d.x()) + abs(d.y()) > 4:
                self._moved = True
                self.tf.ox += d.x()
                self.tf.oy += d.y()
                self._press = pos
                self.tf.clamp(self.data_rect())
                self.auto_fit = False
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.update()
                return
        cell = self.cell_at(pos)
        if cell != self.hover_cell:
            self.hover_cell = cell
            if cell is not None and self.tf.cell_px < self._number_cell_px():
                QToolTip.showText(e.globalPosition().toPoint(), cell_text(cell), self)
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._press is not None:
            if not self._moved:
                cell = self.cell_at(e.position())
                if cell is not None:
                    self.selected_cell = cell
                    self.cell_clicked.emit(cell)
                    self.update()
            self._press, self._moved = None, False
            self.unsetCursor()

    def mouseDoubleClickEvent(self, e):
        self.fit()

    def leaveEvent(self, e):
        self.hover_cell = None
        self.update()

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key.Key_0, Qt.Key.Key_Home):
            self.fit()
        elif k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_by(1.25)
        elif k == Qt.Key.Key_Minus:
            self.zoom_by(0.8)
        else:
            super().keyPressEvent(e)

    def contextMenuEvent(self, e):
        cell = self.cell_at(QPointF(e.pos()))
        menu = QMenu(self)
        copy = menu.addAction(f"Скопировать номер клетки {cell}" if cell is not None else "Скопировать номер клетки")
        copy.setEnabled(cell is not None)
        copy.triggered.connect(lambda: self.copy_cell(cell))
        menu.addSeparator()
        plan = menu.addAction("Показывать путь и цели шоу")
        plan.setCheckable(True)
        plan.setChecked(self.show_plan)
        plan.toggled.connect(self.set_show_plan)
        qr = menu.addAction("Метки QR в клетках")
        qr.setCheckable(True)
        qr.setChecked(self.show_qr)
        qr.toggled.connect(self.set_show_qr)
        menu.addAction("По размеру окна", self.fit)
        menu.exec(e.globalPos())

    def copy_cell(self, cell=None):
        cell = self.selected_cell if cell is None else cell
        if cell is not None:
            QGuiApplication.clipboard().setText(str(cell))
        return cell

    def set_show_plan(self, on):
        self.show_plan = bool(on)
        self.update()

    def set_show_qr(self, on):
        self.show_qr = bool(on)
        self.update()

    # ---- painting ---------------------------------------------------------------------------------------

    def _font(self, px, medium=False):
        f = QFont(self.font())
        f.setPixelSize(int(px))
        f.setWeight(QFont.Weight.Medium if medium else QFont.Weight.Normal)
        return f

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), theme.color("panel"))
        rect = self.data_rect()
        p.save()
        p.setClipRect(rect)
        self._paint_cells(p)
        if self.show_obj and self.paths:
            if self.show_plan:
                self._paint_plan(p)
            self._paint_show_drones(p)
        self._paint_live(p)
        self._paint_hover(p)
        p.restore()
        self._paint_axes(p)
        self._paint_overlay(p, rect)
        p.end()

    def _visible_cells(self):
        r = self.data_rect()
        x0, y1 = self.tf.to_cm(r.left(), r.top())
        x1, y0 = self.tf.to_cm(r.right(), r.bottom())
        c0, c1 = max(0, floor((x0 + HALF) / CELL_CM)), min(GRID_W - 1, floor((x1 + HALF) / CELL_CM))
        r0, r1 = max(0, floor((y0 + HALF) / CELL_CM)), min(GRID_W - 1, floor((y1 + HALF) / CELL_CM))
        return range(r0, r1 + 1), range(c0, c1 + 1)

    def _number_cell_px(self):
        """Smallest cell (px) in which every three-digit number fits at 11 px."""
        return QFontMetrics(self._font(11)).horizontalAdvance("000") + 7

    def _paint_cells(self, p):
        tf, cp = self.tf, self.tf.cell_px
        rows, cols = self._visible_cells()
        # targets of the show: a tinted cell under everything else
        if self.show_plan:
            for cell, drones in self._targets.items():
                r = tf.cell_rect(cell)
                col = self._plan.get(drones[0], (None, None))[1] or theme.color("text2")
                p.fillRect(r, _alpha(col, 40))
        grid = QPen(theme.color("grid"))
        grid.setWidthF(1)
        p.setPen(grid)
        a, b = tf.to_screen(WORLD_MIN, WORLD_MIN), tf.to_screen(WORLD_MAX, WORLD_MAX)
        for i in range(GRID_W + 1):
            v = WORLD_MIN + i * CELL_CM
            p.drawLine(tf.to_screen(v, WORLD_MIN), tf.to_screen(v, WORLD_MAX))
            p.drawLine(tf.to_screen(WORLD_MIN, v), tf.to_screen(WORLD_MAX, v))
        edge = QPen(theme.color("border"))
        edge.setWidthF(1.5)
        p.setPen(edge)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(QPointF(a.x(), b.y()), QPointF(b.x(), a.y())))
        if cp < 12:
            return
        num_px = int(min(30, max(11, cp * 0.22)))
        p.setFont(self._font(num_px))
        need = p.fontMetrics().horizontalAdvance("000") + 7
        step = 1 if cp >= need else ceil(need / cp)
        for row in rows:
            for col in cols:
                cell = col + GRID_W * row
                r = tf.cell_rect(cell)
                if cp >= QR_MIN_CELL_PX and self.show_qr:
                    self._paint_qr(p, r, cell)
                if col % step or row % step:
                    continue
                p.setPen(theme.color("text2"))
                p.drawText(QRectF(r.left() + 3, r.top() + 1, r.width() * step - 4, num_px + 6),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, str(cell))
                if cp >= COORD_TEXT_CELL_PX:
                    x, y = cell_center_cm(cell)
                    p.setFont(self._font(11))
                    p.drawText(QRectF(r.left() + 3, r.top() + num_px + 5, r.width() - 4, 16),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, f"y {y}, x {x} см")
                    p.setFont(self._font(num_px))

    def _paint_qr(self, p, r, cell):
        g = min(r.width() * 0.4, 90)
        m = r.width() * 0.09
        x0, y0 = r.right() - m - g, r.bottom() - m - g
        mod = g / 5
        col = theme.color("qr")
        for i, j in qr_modules(cell):
            p.fillRect(QRectF(x0 + i * mod, y0 + j * mod, mod + 0.3, mod + 0.3), col)

    def _paint_plan(self, p):
        """Planned path of every drone and, once zoomed in, the drones that visit a cell."""
        tf = self.tf
        p.save()
        p.translate(tf.ox, tf.oy)
        p.scale(tf.s, -tf.s)
        for n, (path, col) in self._plan.items():
            col = col or theme.color("text2")
            pen = QPen(_alpha(col, 48))
            pen.setCosmetic(True)
            pen.setWidthF(1.2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        p.restore()
        # current target of every drone (the cell of the code step it executes now)
        for n, cell in self._current_targets().items():
            col = self._plan[n][1] or theme.color("text2")
            pen = QPen(_alpha(col, 230), 2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(tf.cell_rect(cell).adjusted(2, 2, -2, -2))
        if tf.cell_px >= TARGET_TEXT_CELL_PX:
            p.setFont(self._font(11))
            p.setPen(theme.color("text"))
            for cell, drones in self._targets.items():
                r = tf.cell_rect(cell)
                if not r.intersects(self.data_rect()):
                    continue
                names = " ".join(f"д{n}" for n in drones[:3]) + (" …" if len(drones) > 3 else "")
                p.drawText(QRectF(r.left() + 3, r.bottom() - 19, r.width() * 0.55, 16),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "→ " + names)

    def _current_targets(self):
        out = {}
        for n, path in self.paths.items():
            if not path or n not in self.show_obj.drones:
                continue
            i = min(bisect_left([seg[1] for seg in path], self.t), len(path) - 1)
            idx = path[i][5]
            steps = self.show_obj.drones[n].steps
            if idx < len(steps) and steps[idx].kind in ("code", "code_z"):
                cell = steps[idx].args["cell"]
                if 0 <= cell < GRID_CELLS:
                    out[n] = cell
        return out

    def _scale_for_drone(self):
        return max(self.tf.s, MIN_DRONE_PX / WIDTH_CM)

    def _paint_show_drones(self, p):
        show, tf = self.show_obj, self.tf
        pos = show.positions_at(self.t, self.paths)
        if self.show_plan:                           # walked part of the path, dashed
            for n, path in self.paths.items():
                col = _identity_color(show.drones[n]) or theme.color("text2")
                pen = QPen(_alpha(col, 140), 1.2)
                pen.setStyle(Qt.PenStyle.DashLine)
                p.setPen(pen)
                pts = [tf.to_screen(seg[2][0], seg[2][1]) for seg in path if seg[0] < self.t]
                pts.append(tf.to_screen(pos[n][0], pos[n][1]))
                for a, b in zip(pts, pts[1:]):
                    p.drawLine(a, b)
        ring = QPen(theme.color("danger"), 2)         # drones closer than the threshold (3D distance)
        for a, b in combinations(sorted(pos), 2):
            if dist(pos[a], pos[b]) < self.threshold:
                p.setPen(ring)
                p.setBrush(Qt.BrushStyle.NoBrush)
                mid = tf.to_screen((pos[a][0] + pos[b][0]) / 2, (pos[a][1] + pos[b][1]) / 2)
                rad = (dist(pos[a][:2], pos[b][:2]) / 2 + WIDTH_CM / 2 + 4) * self._scale_for_drone()
                p.drawEllipse(mid, rad, rad)
        s = self._scale_for_drone()
        for n in sorted(pos):
            rgb = show.drones[n].color_at(self.t)[1]
            c = tf.to_screen(pos[n][0], pos[n][1])
            paint_drone(p, c, s, 0, rgb, "top")
        for n in sorted(pos):                         # badges after all drones so they stay on top
            rgb = show.drones[n].color_at(self.t)[1]
            c = tf.to_screen(pos[n][0], pos[n][1])
            off = QPointF(WIDTH_CM / 2 * s * 0.78, WIDTH_CM / 2 * s * 0.78)
            r = paint_badge(p, c + off, str(n), rgb)
            if self.tf.cell_px >= 30:
                paint_tag(p, QPointF(r.right() + 3, r.center().y()), f"{pos[n][2]:.0f} см")

    def _paint_live(self, p):
        tf = self.tf
        accent = theme.color("accent")
        s = self._scale_for_drone()
        drawn = self.drawn_live()
        for d in drawn:                               # trail, older = fainter
            pts = [tf.to_screen(x, y) for x, y in self.trails.get(d.key, [])]
            for i in range(1, len(pts)):
                p.setPen(QPen(_alpha(accent, int(40 + 180 * i / len(pts))), 2))
                p.drawLine(pts[i - 1], pts[i])
        for d in drawn:
            c = tf.to_screen(d.x, d.y)
            rad = ACCURACY_CM * tf.s
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(accent, 30))
            p.drawEllipse(c, rad, rad)
            paint_drone(p, c, s, 0, accent, "top")
            ring = QPen(_alpha(accent, 220), 1.5)       # accuracy ring over the drone: stays visible
            ring.setStyle(Qt.PenStyle.DashLine)
            p.setPen(ring)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, rad, rad)
        for d in drawn:
            c = tf.to_screen(d.x, d.y)
            off = QPointF(WIDTH_CM / 2 * s * 0.78, -WIDTH_CM / 2 * s * 0.78)
            r = paint_badge(p, c + off, d.label, None, outline="accent", filled=False)
            if d.z is not None:
                paint_tag(p, QPointF(r.right() + 3, r.center().y()), f"{d.z} см")

    def _paint_hover(self, p):
        for cell, width in ((self.selected_cell, 2.0), (self.hover_cell, 1.0)):
            if cell is None:
                continue
            r = self.tf.cell_rect(cell)
            if cell == self.hover_cell:
                p.fillRect(r, _alpha(theme.color("accent"), 45))
            p.setPen(QPen(theme.color("accent"), width))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(width / 2, width / 2, -width / 2, -width / 2))

    def _paint_axes(self, p):
        """Row numbers hug the left edge of the mat, column numbers its bottom edge (both stay in view)."""
        tf, rect = self.tf, self.data_rect()
        cp = tf.cell_px
        left = max(tf.to_screen(WORLD_MIN, 0).x(), rect.left())
        bottom = min(tf.to_screen(0, WORLD_MIN).y(), rect.bottom())
        p.setFont(self._font(11))
        p.setPen(theme.color("text2"))
        step = max(1, ceil(22 / cp))
        for i in range(GRID_W):
            x = tf.to_screen(i * CELL_CM, 0).x()
            if rect.left() <= x <= rect.right() and i % step == 0:
                p.drawText(QRectF(x - 14, bottom + 2, 28, 15), Qt.AlignmentFlag.AlignCenter, str(i))
            y = tf.to_screen(0, i * CELL_CM).y()
            if rect.top() <= y <= rect.bottom() and i % step == 0:
                p.drawText(QRectF(left - 25, y - 8, 21, 16),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(i))
        p.drawText(QRectF(left - 38, bottom + 2, 34, 15), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   "x →")                              # column axis: x grows to the right
        p.save()                                       # row axis title, rotated, along the left edge
        p.translate(left - 28, rect.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-60, -8, 120, 14), Qt.AlignmentFlag.AlignCenter, "строка, y ↑")
        p.restore()
        text = self.fontMetrics().elidedText(self.status_line(), Qt.TextElideMode.ElideRight, self.width() - 16)
        p.setPen(theme.color("text") if self.hover_cell is not None or self.selected_cell is not None
                 else theme.color("text2"))
        p.drawText(QRectF(8, self.height() - 19, self.width() - 16, 17),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)

    def _paint_overlay(self, p, rect):
        """Text over the map: live drone positions (with the 'no position' cases) and the empty hint."""
        lines = []
        for d in self.live:
            if not d.drawn:
                lines.append((f"▲ Дрон {d.label}: нет позиции", "warn"))
            else:
                where = f"клетка {d.cell}" if d.cell is not None else "вне коврика"
                lines.append((f"● Дрон {d.label}: {where}, y={d.y} см, x={d.x} см", "text"))
        p.setFont(self._font(12))
        fm = p.fontMetrics()
        y = rect.top() + 4
        for text, tok in lines[:6]:
            w = fm.horizontalAdvance(text) + 12
            box = QRectF(rect.left() + 4, y, w, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(theme.color("card"), 235))
            p.drawRoundedRect(box, 5, 5)
            p.setPen(theme.color(tok))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
            y += 23
        if self.show_obj is None or not self.paths:
            text = "Нет шоу для показа"
            p.setFont(self._font(13))
            w = p.fontMetrics().horizontalAdvance(text) + 20
            box = QRectF(rect.center().x() - w / 2, rect.bottom() - 30, w, 24)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(theme.color("card"), 235))
            p.drawRoundedRect(box, 6, 6)
            p.setPen(theme.color("text2"))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
