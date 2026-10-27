"""Drawn drone model and the mat map: coordinate mapping (unit tests) and offscreen GUI tests."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QMouseEvent, QPainter, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from conftest import HOST, ROOT, FAST  # noqa: E402
from fake_drone import FakeDrone, free_port  # noqa: E402
from app import theme  # noqa: E402
from app.drone_art import DroneArt, DroneIcon, paint_drone  # noqa: E402
from app.drones_panel import DroneCard  # noqa: E402
from app.main_window import MainWindow  # noqa: E402
from app.mat_map import (LiveDrone, MatMapView, MatTransform, cell_center_cm, cell_rc, cell_text,  # noqa: E402
                         cm_to_cell, qr_modules, rc_cell)
from app.session import FlightController  # noqa: E402
from litebee import protocol as proto  # noqa: E402
from litebee.mission import cell_from_xy  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.stylesheet())
    return app


def pump(qapp, pred, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        qapp.processEvents()
        if pred():
            return True
        time.sleep(0.02)
    qapp.processEvents()
    return pred()


# ---- coordinate mapping (no window) -----------------------------------------------------------------------

def test_cell_zero_is_bottom_left_and_143_top_right():
    assert cell_center_cm(0) == (0, 0)
    assert cell_center_cm(143) == (440, 440)
    assert cell_center_cm(11) == (440, 0)          # right end of the bottom row
    assert cell_center_cm(132) == (0, 440)         # left end of the top row


def test_numbers_grow_to_the_right_and_up_as_in_the_users_photo():
    # bottom row 84 85 86, middle 96 97 98, top 108 109 110 (rows 7..9, columns 0..2)
    for cell, (row, col) in {84: (7, 0), 85: (7, 1), 86: (7, 2), 96: (8, 0), 97: (8, 1), 98: (8, 2),
                             108: (9, 0), 109: (9, 1), 110: (9, 2)}.items():
        assert cell_rc(cell) == (row, col) and rc_cell(row, col) == cell
    assert cell_center_cm(85)[0] > cell_center_cm(84)[0]            # to the right
    assert cell_center_cm(96)[1] > cell_center_cm(84)[1]            # up
    assert cell_center_cm(108)[1] > cell_center_cm(96)[1]


def test_cell_cm_roundtrip_for_all_cells_and_edges():
    for cell in range(144):
        x, y = cell_center_cm(cell)
        assert cm_to_cell(x, y) == cell
        assert cm_to_cell(x + 19.9, y - 19.9) == cell                # inside the cell
    assert cm_to_cell(19.9, 0) == 0 and cm_to_cell(20.1, 0) == 1
    assert cm_to_cell(-20.1, 0) is None and cm_to_cell(0, -20.1) is None
    assert cm_to_cell(459.9, 459.9) == 143 and cm_to_cell(460.1, 0) is None
    for bad in (-1, 144, 1.5):
        with pytest.raises(ValueError):
            cell_center_cm(bad)


def test_cell_text_format():
    assert cell_text(97) == "клетка 97, строка 8, столбец 1, y=320 см, x=40 см"
    assert cell_text(0) == "клетка 0, строка 0, столбец 0, y=0 см, x=0 см"


def test_telemetry_axes_match_the_map():
    """Telemetry: first int16 = y (row axis), second = x (column axis)."""
    t = proto.decode_telemetry(proto.encode_telemetry(x=40, y=320))
    assert (t.x, t.y) == (40, 320) and t.cell == 97 == cm_to_cell(t.x, t.y) == cell_from_xy(t.x, t.y)
    t0 = proto.decode_telemetry(proto.encode_telemetry(x=0, y=0))
    assert not t0.has_fix and t0.cell is None


def test_transform_puts_cell_zero_bottom_left():
    tf = MatTransform()
    from PySide6.QtCore import QRectF
    tf.fit(QRectF(0, 0, 500, 500))
    r0, r143, r11, r132 = (tf.cell_rect(c) for c in (0, 143, 11, 132))
    assert r0.center().x() < r143.center().x() and r0.center().y() > r143.center().y()
    assert r11.center().x() > r132.center().x() and r11.center().y() > r132.center().y()   # 11 right-bottom
    assert abs(r0.width() - tf.cell_px) < 1e-6 and r0.left() >= 0 and r143.right() <= 500
    for cell in (0, 11, 96, 97, 132, 143):
        c = tf.cell_rect(cell).center()
        assert tf.cell_at(c.x(), c.y()) == cell
        x, y = tf.to_cm(c.x(), c.y())
        assert (round(x), round(y)) == cell_center_cm(cell)


def test_zoom_keeps_the_point_under_the_cursor():
    tf = MatTransform()
    from PySide6.QtCore import QRectF
    tf.fit(QRectF(0, 0, 500, 500))
    before = tf.to_cm(123, 321)
    tf.zoom_at(123, 321, 2.5, 0.1)
    after = tf.to_cm(123, 321)
    assert after == pytest.approx(before) and tf.s > 1


def test_live_drone_without_fix_is_not_drawn():
    class V:     # a DroneView-like object
        def __init__(self, x, y, fix, cell=None, ip="10.0.0.5"):
            self.ip, self.x, self.y, self.z, self.has_fix, self.cell = ip, x, y, 0, fix, cell

    assert not LiveDrone.from_view(V(0, 0, False)).drawn
    assert not LiveDrone.from_view(V(0, 0, True)).drawn            # x = y = 0 is never a position
    assert LiveDrone.from_view(V(0, 320, True, 96)).drawn
    assert LiveDrone.from_view(V(None, None, False)) is None       # link lost: no telemetry at all
    assert LiveDrone.from_view(V(0, 320, True, 96), 3).label == "3"
    assert LiveDrone.from_view(V(0, 320, True, 96), None).label == "5"


def test_qr_glyph_is_deterministic_with_finder_corners():
    assert qr_modules(7) == qr_modules(7) and qr_modules(7) != qr_modules(8)
    mods = set(qr_modules(100))
    assert {(0, 0), (1, 1), (3, 0), (4, 1), (0, 3), (1, 4)} <= mods


# ---- the drawn drone -----------------------------------------------------------------------------------------

def _draw(qapp, view="top", heading=0, led=None, scale=10.0, size=500, selected=False):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    try:
        paint_drone(p, QPointF(size / 2, size / 2 if view == "top" else size * 0.7), scale, heading, led, view, selected)
    finally:
        p.end()
    return img


def _bbox(img):
    xs, ys = [], []
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 40:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def _count(img, rgb, tol=40):
    n = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = img.pixelColor(x, y)
            if c.alpha() > 200 and all(abs(a - b) <= tol for a, b in zip((c.red(), c.green(), c.blue()), rgb)):
                n += 1
    return n


def test_drone_is_drawn_to_true_scale(qapp):
    x0, y0, x1, y1 = _bbox(_draw(qapp, "top", scale=10, led=None))
    assert 205 <= x1 - x0 <= 216                       # 20.9 cm * 10 px/cm plus the guard stroke
    s0, t0, s1, t1 = _bbox(_draw(qapp, "side", scale=10, led=None))
    assert 205 <= s1 - s0 <= 222                       # width 209 mm
    assert 52 <= t1 - t0 <= 68                         # height 56 mm
    a, _, b, _ = _bbox(_draw(qapp, "top", scale=5, led=None))
    assert (b - a) == pytest.approx((x1 - x0) / 2, abs=4)      # linear in the scale


def test_nose_mark_follows_the_heading(qapp):
    accent = theme.color("accent")
    rgb = (accent.red(), accent.green(), accent.blue())

    def centroid(heading):
        img = _draw(qapp, "top", heading=heading, scale=10)
        pts = []
        for y in range(0, 500, 2):
            for x in range(0, 500, 2):
                c = img.pixelColor(x, y)
                if c.alpha() > 200 and all(abs(a - b) <= 12 for a, b in zip((c.red(), c.green(), c.blue()), rgb)):
                    pts.append((x, y))
        assert len(pts) > 5
        return sum(p[0] for p in pts) / len(pts) - 250, sum(p[1] for p in pts) / len(pts) - 250

    dx, dy = centroid(0)
    assert dy < -80 and abs(dx) < 10                   # nose up on the screen (+y of the mat)
    dx, dy = centroid(90)
    assert dx > 80 and abs(dy) < 10                    # clockwise: nose to the right
    dx, dy = centroid(180)
    assert dy > 80


def test_led_colour_glows_and_off_led_does_not(qapp):
    lit, off = _draw(qapp, "top", led=(255, 0, 255)), _draw(qapp, "top", led=None)
    assert _count(lit, (255, 0, 255), 30) > 40 and _count(off, (255, 0, 255), 30) == 0
    assert _count(_draw(qapp, "side", led=(255, 255, 0)), (255, 255, 0), 30) > 10
    assert _bbox(_draw(qapp, "top", led=(0, 0, 0))) == _bbox(off)       # black LED = off
    with pytest.raises(ValueError):
        _draw(qapp, "bottom")


def test_selected_ring_is_larger_than_the_drone(qapp):
    a = _bbox(_draw(qapp, "top", selected=False))
    b = _bbox(_draw(qapp, "top", selected=True))
    assert b[2] - b[0] > a[2] - a[0] + 40


def test_art_widgets_render(qapp, tmp_path):
    for w, name in ((DroneArt(), "art"), (DroneIcon(34), "icon")):
        w.resize(w.sizeHint() if name == "art" else w.size())
        img = w.grab().toImage()
        assert not img.isNull() and _bbox_diff(img) > 20
        img.save(str(tmp_path / f"{name}.png"))
    card = DroneCard("10.0.0.7")
    assert isinstance(card.icon, DroneIcon)


def _bbox_diff(img):
    bg = img.pixel(1, 1)
    return sum(1 for y in range(0, img.height(), 2) for x in range(0, img.width(), 2) if img.pixel(x, y) != bg)


# ---- the map widget ---------------------------------------------------------------------------------------------

@pytest.fixture
def mat(qapp):
    w = MatMapView()
    w.resize(760, 520)
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def center_of(mat, cell):
    return mat.tf.cell_rect(cell).center()


def mouse(w, kind, pos, button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.LeftButton):
    ev = QMouseEvent(kind, QPointF(pos), QPointF(w.mapToGlobal(QPoint(int(pos.x()), int(pos.y())))), button,
                     buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(w, ev)


def test_map_geometry_matches_the_window(mat):
    assert center_of(mat, 0).y() > center_of(mat, 143).y() and center_of(mat, 0).x() < center_of(mat, 143).x()
    assert mat.data_rect().contains(center_of(mat, 0)) and mat.data_rect().contains(center_of(mat, 143))
    assert mat.cell_at(center_of(mat, 97)) == 97 and mat.cell_at(QPointF(2, 2)) is None


def test_click_shows_cell_in_status_line_and_emits(mat):
    got = []
    mat.cell_clicked.connect(got.append)
    c = center_of(mat, 97)
    QTest.mouseClick(mat, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(int(c.x()), int(c.y())))
    assert got == [97]
    assert mat.status_line() == "клетка 97, строка 8, столбец 1, y=320 см, x=40 см"
    mouse(mat, QEvent.Type.MouseMove, QPointF(2, 2), Qt.MouseButton.NoButton, Qt.MouseButton.NoButton)
    assert mat.hover_cell is None and mat.status_line().startswith("клетка 97")     # selection stays
    h = center_of(mat, 5)
    mouse(mat, QEvent.Type.MouseMove, h, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton)
    assert mat.hover_cell == 5 and mat.status_line().startswith("клетка 5,")


def test_copy_cell_number_goes_to_the_clipboard(mat):
    assert mat.copy_cell(143) == 143
    assert QGuiApplication.clipboard().text() == "143"


def test_wheel_zoom_drag_pan_and_fit(mat, qapp):
    fit_s = mat.tf.s
    pos = center_of(mat, 66)
    before = mat.tf.to_cm(pos.x(), pos.y())
    ev = QWheelEvent(pos, mat.mapToGlobal(pos), QPoint(0, 0), QPoint(0, 240), Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(mat, ev)
    assert mat.tf.s > fit_s * 1.3 and not mat.auto_fit
    assert mat.tf.to_cm(pos.x(), pos.y()) == pytest.approx(before)          # zoom is around the cursor
    ox, oy = mat.tf.ox, mat.tf.oy
    mouse(mat, QEvent.Type.MouseButtonPress, QPointF(300, 300), Qt.MouseButton.LeftButton)
    mouse(mat, QEvent.Type.MouseMove, QPointF(340, 320), Qt.MouseButton.NoButton)
    mouse(mat, QEvent.Type.MouseButtonRelease, QPointF(340, 320), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
    assert (mat.tf.ox, mat.tf.oy) == pytest.approx((ox + 40, oy + 20))
    assert mat.selected_cell is None                                        # a drag is not a click
    mat.fit_button.click()
    assert mat.auto_fit and mat.tf.s == pytest.approx(fit_s)
    for _ in range(40):
        mat.zoom_by(0.5)                                                    # cannot be zoomed out of sight
    assert mat.tf.s >= fit_s * 0.6 - 1e-9
    for _ in range(40):
        mat.zoom_by(2.0)
    assert mat.tf.s <= 10.0 + 1e-9


def test_cell_numbers_are_printed_in_every_cell_at_a_sensible_zoom(mat, qapp):
    mat.set_show_qr(False)
    mat.resize(1000, 800)                      # roomy even when the platform has no real font
    qapp.processEvents()
    assert mat.tf.cell_px >= mat._number_cell_px()
    img = mat.grab().toImage()
    bg = theme.color("panel").rgb()
    for cell in (0, 11, 60, 96, 143):
        r = mat.tf.cell_rect(cell)
        ink = sum(1 for x in range(int(r.left() + 3), int(r.left() + 22)) for y in range(int(r.top() + 2), int(r.top() + 14))
                  if img.pixel(x, y) != bg)
        assert ink > 8, f"no number drawn in cell {cell}"
    mat.resize(300, 230)                                                    # tiny: only some numbers + tooltips
    qapp.processEvents()
    assert not mat.grab().isNull()


def test_qr_glyphs_can_be_turned_off(mat):
    r = mat.tf.cell_rect(77)
    def ink(img):
        return sum(1 for x in range(int(r.center().x()), int(r.right() - 2))
                   for y in range(int(r.center().y()), int(r.bottom() - 2)) if img.pixel(x, y) == theme.color("qr").rgb())
    assert ink(mat.grab().toImage()) > 10
    mat.set_show_qr(False)
    assert ink(mat.grab().toImage()) == 0


def test_live_drone_with_fix_is_drawn_and_without_fix_is_not(mat, qapp):
    base = mat.grab().toImage()
    r0 = mat.tf.cell_rect(0)

    def region(img, r):
        return [img.pixel(x, y) for x in range(int(r.left()), int(r.right())) for y in range(int(r.top()), int(r.bottom()))]

    mat.set_live([LiveDrone("10.0.0.5", "1", 0, 0, 0, False, None)])        # x = y = 0: no position
    assert mat.drawn_live() == []
    img = mat.grab().toImage()
    assert region(img, r0) == region(base, r0)                              # nothing drawn on cell 0
    mat.set_live([LiveDrone("10.0.0.5", "1", 0, 320, 50, True, 96)])
    assert [d.cell for d in mat.drawn_live()] == [96]
    img = mat.grab().toImage()
    r96 = mat.tf.cell_rect(96)
    assert region(img, r96) != region(base, r96)
    acc = theme.color("accent")
    near = sum(1 for p in region(img, r96.adjusted(-12, -12, 12, 12))
               if abs(QColor(p).red() - acc.red()) < 30 and abs(QColor(p).green() - acc.green()) < 30
               and abs(QColor(p).blue() - acc.blue()) < 30)
    assert near > 15                                                        # accent drone, ring and badge
    mat.set_live([])
    assert mat.drawn_live() == [] and not mat.trails


def test_live_trail_and_accuracy_ring(mat):
    for y in (300, 310, 320, 330):
        mat.set_live([LiveDrone("a", "1", 0, y, 40, True, cm_to_cell(0, y))])
    assert list(mat.trails["a"]) == [(0, 300), (0, 310), (0, 320), (0, 330)]
    mat.set_live([LiveDrone("a", "1", 0, 330.2, 40, True, 96)])             # moved less than 1 cm: no new point
    assert len(mat.trails["a"]) == 4
    for i in range(100):
        mat.set_live([LiveDrone("a", "1", i + 1, 330, 40, True, 96)])
    assert len(mat.trails["a"]) == 40                                       # only the last positions
    mat.set_live([LiveDrone("a", "1", 0, 0, 0, False, None)])
    assert "a" not in mat.trails                                            # a lost fix breaks the trail
    assert mat.grab().toImage().width() > 0


SHOW = os.path.join(ROOT, "shows", "my_dream.py")


def test_plan_paths_and_targets_from_the_show(qapp):
    from litebee.loader import load_show_source
    with open(SHOW, encoding="utf-8") as f:
        show = load_show_source(f.read(), SHOW)
    w = MatMapView()
    w.resize(760, 520)
    w.show()
    w.set_show(show)
    assert 25 in w._targets and 38 in w._targets and set(w._plan) == set(range(1, 11))
    assert all(1 in w._targets[c] for c in (25, 38))
    w.set_time(0.0)
    assert w._current_targets() == {}
    w.set_time(12.0)
    assert w._current_targets().get(1) == 25                                # drone 1 is flying to cell 25 at 12 s
    base = w.grab().toImage()
    w.set_show_plan(False)
    assert w.grab().toImage() != base                                       # the plan layer was visible
    w.close()


# ---- inside the window ----------------------------------------------------------------------------------------------

@pytest.fixture
def win(qapp):
    w = MainWindow(controller=FlightController(timing=FAST))
    w.resize(1100, 700)
    w.show()
    yield w
    w.close()


def test_window_renders_map_side_view_and_empty_art(win, qapp, tmp_path):
    empty = win.grab().toImage()
    assert not empty.isNull()
    empty.save(str(tmp_path / "empty.png"))
    assert win.open_file(SHOW)
    win.check()
    win.slider.setValue(1200)
    top = win.grab().toImage()
    top.save(str(tmp_path / "top.png"))
    assert win.preview.mat.isVisible() and win.preview.mat.show_obj is win.show_obj
    win.side_button.setChecked(True)
    assert not win.preview.mat.isVisible()
    side = win.grab().toImage()
    side.save(str(tmp_path / "side.png"))
    assert top != side and os.path.getsize(str(tmp_path / "top.png")) > 5000
    win.side_button.setChecked(False)
    assert win.preview.mat.isVisible()


def test_proximity_ring_and_height_limit_still_work(win, qapp):
    win.open_file(SHOW)
    win.check()
    assert win.preview.threshold == 60 and win.preview.mat.threshold == 60
    win.slider.setValue(1200)
    img = win.preview.grab().toImage()
    danger = theme.color("danger")
    n = sum(1 for y in range(img.height()) for x in range(img.width())
            if QColor(img.pixel(x, y)).red() > 200 and abs(QColor(img.pixel(x, y)).green() - danger.green()) < 30
            and abs(QColor(img.pixel(x, y)).blue() - danger.blue()) < 30)
    assert n > 20                                                           # the red ring of the close pair
    win.limit_spin.setValue(170)
    assert win.preview.limit_text() == "лимит 170 см"
    win.side_button.setChecked(True)
    img = win.preview.grab().toImage()
    warn = theme.color("warn")
    assert any(abs(QColor(img.pixel(x, y)).red() - warn.red()) < 25 and abs(QColor(img.pixel(x, y)).green() - warn.green()) < 25
               for y in range(img.height()) for x in range(0, img.width(), 3) if img.pixel(x, y) != 0)


def test_live_fake_drone_on_the_map(win, qapp, tmp_path):
    win.open_file(SHOW)
    win.check()
    win.slider.setValue(1200)
    port = free_port()
    with FakeDrone(port, fix=(0, 320)) as drone:                           # standing on cell 96
        assert win.connect_link(HOST, [HOST], port, drone.udp_port)
        assert pump(qapp, lambda: win.preview.mat.drawn_live())
        live = win.preview.mat.drawn_live()[0]
        assert (live.cell, live.x, live.y, live.label) == (96, 0, 320, "1")
        assert "клетка 96" in win.drones_panel.cards[HOST].cell.text().lower()
        win.grab().save(str(tmp_path / "live96.png"))
        drone.set_fix(None)                                                 # fix lost: not drawn, text says so
        assert pump(qapp, lambda: win.preview.mat.live and not win.preview.mat.drawn_live())
        assert win.drones_panel.cards[HOST].cell.text() == "Нет позиции"
        assert win.grab().toImage() is not None
    win.controller.disconnect_link()
    win.refresh()
    assert win.preview.mat.live == []


def test_no_fix_drone_is_never_cell_zero_on_the_map(win, qapp):
    port = free_port()
    with FakeDrone(port) as drone:                                          # fresh drone: x = y = 0
        assert win.connect_link(HOST, [HOST], port, drone.udp_port)
        assert pump(qapp, lambda: win.preview.mat.live)
        assert win.preview.mat.drawn_live() == []
        assert win.controller.view(HOST).cell is None
