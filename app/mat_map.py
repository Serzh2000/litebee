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

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QMenu, QToolButton, QToolTip, QWidget

from litebee.mission import CELL_CM, GRID_CELLS, GRID_W
from litebee.safety import MIN_APPROACH_CM

from . import theme
from .cue_sheet import step_text
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
            return theme.readable(QColor(*s.args["rgb"]))
    return None


class MatMapView(QWidget):
    """The mat from above, the hero of the window. Wheel zooms around the cursor, dragging pans, double
    click or the button fits it. A click on a drone focuses it (its path at full strength, the rest dimmed),
    a click on empty space clears the focus."""
    cell_clicked = Signal(int)
    drone_clicked = Signal(object)          # show drone number, or None for empty space

    ML, MT, MR, MB = 26, 4, 8, 36           # margins: row labels, top, right, column labels + the model note
    ASIDE_MIN = 190                         # free width beside the plane that is used for the text column
    DIM = 0.28                              # strength of everything that is not the focused drone

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
        self.focus = None
        self.note = ""
        self._buttons_left = 10 ** 6
        self.extra_buttons = []     # more toolbar buttons placed next to "По размеру" (the window's side view)
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
        self.setAccessibleDescription(HINT)
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
        if self.focus not in self.paths:
            self.focus = None
        self.update()

    def set_time(self, t):
        self.t = t
        self.update()

    def set_focus(self, n):
        """Focus mode: the path and the drone n at full strength, everything else dimmed. None clears it."""
        n = n if n in self.paths else None
        if n != self.focus:
            self.focus = n
            self.update()

    def set_note(self, text):
        self.note = text
        self.setToolTip("")
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

    def _strength(self, n):
        """1.0 for the focused drone (or when nothing is focused), DIM for the others."""
        return 1.0 if self.focus in (None, n) else self.DIM

    # ---- geometry ---------------------------------------------------------------------------------------

    def data_rect(self):
        return QRectF(self.ML, self.MT, max(self.width() - self.ML - self.MR, 10),
                      max(self.height() - self.MT - self.MB, 10))

    def _fit_to(self, tf):
        """Fit the mat in the data rectangle, flush left: the free width is used by the text column."""
        r = self.data_rect()
        tf.fit(r)
        tf.ox -= (r.width() - (WORLD_MAX - WORLD_MIN) * tf.s) / 2

    def fit(self):
        self.auto_fit = True
        self._fit_to(self.tf)
        self.update()

    def _fit_scale(self):
        t = MatTransform()
        t.fit(self.data_rect())
        return t.s

    def resizeEvent(self, e):
        r = self.data_rect()
        if self.auto_fit:
            self._fit_to(self.tf)
        else:
            self.tf.clamp(r)
        self._place_buttons()

    def set_toolbar(self, buttons):
        """Other buttons that sit next to 'По размеру' (children of the same parent)."""
        self.extra_buttons = list(buttons)
        self._place_buttons()

    def _place_buttons(self):
        """The buttons go to the top of the free column beside the mat; with no such column, to the bottom right."""
        btns = [self.fit_button] + self.extra_buttons
        for b in btns:
            b.adjustSize()
        total = sum(b.width() for b in btns) + 6 * (len(btns) - 1)
        aside = self.aside_rect()
        if aside is not None:
            x, y = aside.left(), self.MT + 2
        else:
            x, y = self.width() - self.MR - total, self.height() - btns[0].height() - 2
        for b in btns:
            if b.pos() != QPoint(int(x), int(y)):
                b.move(int(x), int(y))
            b.raise_()
            x += b.width() + 6
        self._buttons_left = int(self.width() - self.MR - total) if aside is None else self.width()

    def showEvent(self, e):
        if self.auto_fit:
            self._fit_to(self.tf)

    def plane_rect(self):
        """The mat on the screen (the whole 12 x 12 plane)."""
        return QRectF(self.tf.to_screen(WORLD_MIN, WORLD_MAX), self.tf.to_screen(WORLD_MAX, WORLD_MIN))

    def aside_rect(self):
        """Free column to the right of the mat when the whole mat is in view and there is room; else None."""
        if not self.auto_fit:
            return None
        left = self.plane_rect().right() + 18
        width = self.width() - self.MR - left
        if width < self.ASIDE_MIN:
            return None
        return QRectF(left, self.MT + 30, width, max(self.height() - self.MT - self.MB - 30, 40))

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

    def show_positions(self):
        """{drone: (x, y, z)} of the show drones at the current time."""
        if not (self.show_obj and self.paths):
            return {}
        return self.show_obj.positions_at(self.t, self.paths)

    def drone_at(self, pos):
        """The show drone drawn under a screen point, else None (the nearest one when several overlap)."""
        s = self._scale_for_drone()
        reach = max(WIDTH_CM / 2 * s, 14.0)
        best, best_d = None, None
        for n, xyz in self.show_positions().items():
            c = self.tf.to_screen(xyz[0], xyz[1])
            d = dist((c.x(), c.y()), (pos.x(), pos.y()))
            if d <= reach and (best_d is None or d < best_d):
                best, best_d = n, d
        return best

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
                drone = self.drone_at(e.position())
                cell = self.cell_at(e.position())
                if cell is not None:
                    self.selected_cell = cell
                    self.cell_clicked.emit(cell)
                self.drone_clicked.emit(drone)       # None on empty space: the window clears the focus
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

    def _font(self, px, emphasis=False):
        return theme.ui_font(int(px), emphasis)

    def paintEvent(self, e):
        self._place_buttons()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), theme.color("bg"))
        rect = self.data_rect()
        p.save()
        p.setClipRect(rect)
        p.fillRect(self.plane_rect(), theme.color("stage"))
        self._paint_cells(p)
        if self.show_obj and self.paths:
            if self.show_plan:
                self._paint_plan(p)
            self._paint_show_drones(p)
        self._paint_live(p)
        self._paint_hover(p)
        p.restore()
        self._paint_axes(p)
        self._paint_text(p, rect)
        if self.hasFocus():                          # keyboard focus: a 2 px accent bar on the left edge of the plane
            p.fillRect(QRectF(max(self.plane_rect().left() - 3, 0), self.MT, 2, rect.height()), theme.color("accent"))
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

    def _bright_cells(self):
        """Cells whose number is brightened: the cells the show drones are flying to now (only the focused drone's
        when one is focused), cells under a show drone or a live drone, the hovered and the selected cell."""
        cells = set()
        if self.show_obj and self.show_plan:
            cells.update(c for n, c in self._current_targets().items() if self.focus in (None, n))
        for n, xyz in self.show_positions().items():
            if self.focus in (None, n):
                c = cm_to_cell(xyz[0], xyz[1])
                if c is not None:
                    cells.add(c)
        cells.update(d.cell for d in self.drawn_live() if d.cell is not None)
        cells.update(c for c in (self.hover_cell, self.selected_cell) if c is not None)
        return cells

    def _paint_cells(self, p):
        tf, cp = self.tf, self.tf.cell_px
        rows, cols = self._visible_cells()
        if self.show_plan and self.focus is not None:     # targets of the focused drone: a tint under everything else
            for cell, drones in self._targets.items():
                if self.focus in drones:
                    col = self._plan.get(self.focus, (None, None))[1] or theme.color("text2")
                    p.fillRect(tf.cell_rect(cell), _alpha(col, 70))
        grid = QPen(theme.color("grid"))
        grid.setWidthF(1)
        p.setPen(grid)
        for i in range(GRID_W + 1):
            v = WORLD_MIN + i * CELL_CM
            p.drawLine(tf.to_screen(v, WORLD_MIN), tf.to_screen(v, WORLD_MAX))
            p.drawLine(tf.to_screen(WORLD_MIN, v), tf.to_screen(WORLD_MAX, v))
        edge = QPen(theme.color("border"))
        edge.setWidthF(1)
        p.setPen(edge)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.plane_rect())
        if cp < 12:
            return
        num_px = int(min(30, max(11, cp * 0.22)))
        p.setFont(theme.mono_font(num_px))
        need = p.fontMetrics().horizontalAdvance("000") + 7
        step = 1 if cp >= need else ceil(need / cp)
        bright = self._bright_cells()
        for row in rows:
            for col in cols:
                cell = col + GRID_W * row
                r = tf.cell_rect(cell)
                if cp >= QR_MIN_CELL_PX and self.show_qr:
                    self._paint_qr(p, r, cell)
                if (col % step or row % step) and cell not in bright:
                    continue
                p.setPen(theme.color("text") if cell in bright else theme.color("cellnum"))
                p.drawText(QRectF(r.left() + 3, r.top() + 1, r.width() * step - 4, num_px + 6),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, str(cell))
                if cp >= COORD_TEXT_CELL_PX:
                    x, y = cell_center_cm(cell)
                    p.setFont(theme.mono_font(11))
                    p.setPen(theme.color("text2") if cell in bright else theme.color("cellnum"))
                    p.drawText(QRectF(r.left() + 3, r.top() + num_px + 5, r.width() - 4, 16),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, f"y {y}, x {x} см")
                    p.setFont(theme.mono_font(num_px))

    def _paint_qr(self, p, r, cell):
        g = min(r.width() * 0.4, 90)
        m = r.width() * 0.09
        x0, y0 = r.right() - m - g, r.bottom() - m - g
        mod = g / 5
        col = theme.color("qr")
        for i, j in qr_modules(cell):
            p.fillRect(QRectF(x0 + i * mod, y0 + j * mod, mod + 0.3, mod + 0.3), col)

    def _paint_plan(self, p):
        """Planned path of every drone (thin; the focused one at full strength) and its current target cell."""
        tf = self.tf
        p.save()
        p.translate(tf.ox, tf.oy)
        p.scale(tf.s, -tf.s)
        for n, (path, col) in sorted(self._plan.items(), key=lambda kv: kv[0] == self.focus):
            col = col or theme.color("text2")
            strong = self.focus == n
            pen = QPen(_alpha(col, 255 if strong else 110 if self.focus is None else 40))
            pen.setCosmetic(True)
            pen.setWidthF(1.6 if strong else 1.0)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        p.restore()
        for n, cell in self._current_targets().items():     # the cell each drone is flying to now
            if self.focus not in (None, n):
                continue
            col = self._plan[n][1] or theme.color("text2")
            p.setPen(QPen(_alpha(col, 230), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(tf.cell_rect(cell).adjusted(2, 2, -2, -2))
        if tf.cell_px >= TARGET_TEXT_CELL_PX:
            p.setFont(self._font(11))
            p.setPen(theme.color("text"))
            for cell, drones in self._targets.items():
                r = tf.cell_rect(cell)
                if not r.intersects(self.data_rect()):
                    continue
                shown = [n for n in drones if self.focus in (None, n)]
                if not shown:
                    continue
                names = " ".join(f"д{n}" for n in shown[:3]) + (" …" if len(shown) > 3 else "")
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
                strong = self.focus == n
                pen = QPen(_alpha(col, 255 if strong else 150 if self.focus is None else 40), 2.0 if strong else 1.2)
                pen.setStyle(Qt.PenStyle.DashLine)
                p.setPen(pen)
                pts = [tf.to_screen(seg[2][0], seg[2][1]) for seg in path if seg[0] < self.t]
                pts.append(tf.to_screen(pos[n][0], pos[n][1]))
                for a, b in zip(pts, pts[1:]):
                    p.drawLine(a, b)
        ring = QPen(theme.color("danger"), 1.5)       # drones closer than the threshold (3D distance)
        for a, b in combinations(sorted(pos), 2):
            if dist(pos[a], pos[b]) < self.threshold:
                p.setPen(ring)
                p.setBrush(Qt.BrushStyle.NoBrush)
                mid = tf.to_screen((pos[a][0] + pos[b][0]) / 2, (pos[a][1] + pos[b][1]) / 2)
                rad = (dist(pos[a][:2], pos[b][:2]) / 2 + WIDTH_CM / 2 + 4) * self._scale_for_drone()
                p.drawEllipse(mid, rad, rad)
        s = self._scale_for_drone()
        for n in sorted(pos, key=lambda k: k == self.focus):         # the focused drone is drawn last
            rgb = show.drones[n].color_at(self.t)[1]
            c = tf.to_screen(pos[n][0], pos[n][1])
            p.setOpacity(self._strength(n) if self.focus is None or self.focus == n else 0.45)
            paint_drone(p, c, s, 0, rgb, "top", selected=self.focus == n)
        p.setOpacity(1.0)
        for n in sorted(pos, key=lambda k: k == self.focus):         # number plates after all drones
            rgb = show.drones[n].color_at(self.t)[1]
            c = tf.to_screen(pos[n][0], pos[n][1])
            off = QPointF(WIDTH_CM / 2 * s * 0.78, WIDTH_CM / 2 * s * 0.78)
            p.setOpacity(1.0 if self.focus in (None, n) else 0.5)
            r = paint_badge(p, c + off, str(n), rgb, outline="accent" if self.focus == n else "text2")
            if self.tf.cell_px >= 30 and self.focus in (None, n):
                paint_tag(p, QPointF(r.right() + 3, r.center().y()), f"{pos[n][2]:.0f} см")
        p.setOpacity(1.0)

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
                p.fillRect(r, _alpha(theme.color("accent"), 38))
            p.setPen(QPen(theme.color("accent"), width))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r.adjusted(width / 2, width / 2, -width / 2, -width / 2))

    def _paint_axes(self, p):
        """Row numbers hug the left edge of the mat, column numbers its bottom edge (both stay in view);
        the one-line note about the model sits below, in the bottom left corner."""
        tf, rect = self.tf, self.data_rect()
        cp = tf.cell_px
        left = max(tf.to_screen(WORLD_MIN, 0).x(), rect.left())
        bottom = min(tf.to_screen(0, WORLD_MIN).y(), rect.bottom())
        p.setFont(theme.mono_font(11))
        p.setPen(theme.color("cellnum"))
        step = max(1, ceil(22 / cp))
        for i in range(GRID_W):
            x = tf.to_screen(i * CELL_CM, 0).x()
            if rect.left() <= x <= rect.right() and i % step == 0:
                p.drawText(QRectF(x - 14, bottom + 2, 28, 15), Qt.AlignmentFlag.AlignCenter, str(i))
            y = tf.to_screen(0, i * CELL_CM).y()
            if rect.top() <= y <= rect.bottom() and i % step == 0:
                p.drawText(QRectF(left - 25, y - 8, 21, 16),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(i))
        if self.note:
            p.setFont(theme.ui_font(12))
            p.setPen(theme.color("text2"))
            room = self._buttons_left - 2 * self.ML
            text = QFontMetrics(p.font()).elidedText(self.note, Qt.TextElideMode.ElideRight, max(room, 60))
            p.drawText(QRectF(self.ML - 14, self.height() - 19, self.width() - self.ML, 17),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)

    # ---- text: the column beside the mat (or small plates over it when there is no room) -------------------

    def info_lines(self):
        """[(text, role)] shown beside the mat. role: 'title', 'text', 'dim', 'warn', 'mono'."""
        lines = []
        cell = self.hover_cell if self.hover_cell is not None else self.selected_cell
        if cell is not None:
            row, col = cell_rc(cell)
            x, y = cell_center_cm(cell)
            lines += [(f"Клетка {cell}", "title"), (f"строка {row}, столбец {col}", "dim"), (f"y {y} см, x {x} см", "mono")]
        if self.focus is not None and self.show_obj:
            drone = self.show_obj.drones[self.focus]
            step = drone.step_at(self.t)
            pos = self.show_positions().get(self.focus)
            lines += [("", "gap"), (f"Дрон {self.focus} выбран", "title")]
            if step is not None:
                lines.append((step_text(step.kind, step.args), "text"))
            if pos is not None:
                lines.append((f"высота {pos[2]:.0f} см", "mono"))
            lines.append(("Щелчок по пустому месту снимает выбор", "dim"))
        for d in self.live:
            lines.append(("", "gap"))
            if not d.drawn:
                lines.append((f"Дрон {d.label}: нет позиции", "warn"))
            else:
                where = f"клетка {d.cell}" if d.cell is not None else "вне коврика"
                lines.append((f"Дрон {d.label} в сети: {where}", "text"))
                lines.append((f"y {d.y} см, x {d.x} см", "mono"))
        if cell is None and self.focus is None and not self.live:
            lines.append(("Колесо — масштаб, перетаскивание — сдвиг", "dim"))
        while lines and lines[0][1] == "gap":
            lines.pop(0)
        return lines

    def _paint_text(self, p, rect):
        lines = self.info_lines()
        aside = self.aside_rect()
        if aside is not None:
            self._paint_aside(p, aside, lines)
        else:
            self._paint_plates(p, rect, lines)
        if self.show_obj is None or not self.paths:
            text = "Нет шоу для показа"
            p.setFont(self._font(13))
            w = p.fontMetrics().horizontalAdvance(text) + 20
            plane = self.plane_rect().intersected(rect)
            box = QRectF(plane.center().x() - w / 2, plane.center().y() - 14, w, 28)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(theme.color("stage"), 235))
            p.drawRoundedRect(box, 4, 4)
            p.setPen(theme.color("text2"))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    ROLE_STYLE = {"title": (15, True, "text"), "text": (13, False, "text"), "dim": (12, False, "text2"),
                  "warn": (13, False, "warn"), "mono": (12, False, "text2")}

    def _paint_aside(self, p, area, lines):
        y = area.top()
        for text, role in lines:
            if role == "gap":
                y += 12
                continue
            px, emphasis, tok = self.ROLE_STYLE[role]
            p.setFont(theme.mono_font(px) if role == "mono" else theme.ui_font(px, emphasis))
            p.setPen(theme.color(tok))
            flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)
            box = p.fontMetrics().boundingRect(QRectF(0, 0, area.width(), 400).toRect(), flags, text)
            h = max(box.height(), px + 2) + 4
            p.drawText(QRectF(area.left(), y, area.width(), h), flags, text)
            y += h
            if y > area.bottom():
                break

    def _paint_plates(self, p, rect, lines):
        """No room beside the mat: the same facts on small plates in the top left corner of the plane."""
        y = rect.top() + 4
        p.setFont(self._font(12))
        fm = p.fontMetrics()
        texts = [(text, "warn" if role == "warn" else "text") for text, role in lines
                 if text and role in ("title", "text", "warn")]
        for text, tok in texts[:5]:
            w = fm.horizontalAdvance(text) + 12
            box = QRectF(rect.left() + 4, y, w, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_alpha(theme.color("card"), 235))
            p.drawRoundedRect(box, 4, 4)
            p.setPen(theme.color(tok))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
            y += 23
