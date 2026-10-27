import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from conftest import FAST, HOST, ROOT  # noqa: E402
from fake_drone import FakeDrone, free_port  # noqa: E402
from app import theme  # noqa: E402
from app.main_window import MainWindow, TEMPLATE, ru_plural  # noqa: E402
from app.session import FlightController  # noqa: E402
from litebee.mission import HARD_MAX_HEIGHT_CM  # noqa: E402


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


@pytest.fixture
def win(qapp):
    w = MainWindow(controller=FlightController(timing=FAST))
    w.show()
    yield w
    w.close()


def test_theme_has_all_tokens_and_no_unresolved_names():
    css = theme.stylesheet()
    assert "@" not in css.split("*/", 1)[1]            # every token substituted
    assert theme.TOKENS["bg"] == "#12161C" and theme.TOKENS["danger"] == "#E5484D"


def test_ru_plural():
    assert [ru_plural(n) for n in (1, 2, 5, 11, 21)] == ["1 дрон", "2 дрона", "5 дронов", "11 дронов", "21 дрон"]


def test_smoke_offscreen_my_dream_check(win, qapp):
    assert win.minimumWidth() >= 1100 and win.minimumHeight() >= 700
    assert win.stack.currentIndex() == 0                      # empty state first
    assert win.emergency_button.text() == "Аварийная посадка" and win.emergency_button.isEnabled()
    assert win.open_file(os.path.join(ROOT, "shows", "my_dream.py"))
    assert win.stack.currentIndex() == 1
    win.check()
    assert win.last_report.strip()
    assert "дронов 10" in win.last_report
    assert len(win.show_obj.drones) == 10
    assert win.report_view.toPlainText() == win.last_report
    # my_dream climbs to 160 cm: above the 150 cm limit, so it is an error and nothing may fly
    assert win.has_errors
    assert any("160" in m for lvl, m, _, _ in win.problems if lvl == "error")
    assert win.problem_list.count() > 0
    assert not win.start_button.isEnabled() and win.start_button.toolTip()
    assert not win.upload_button.isEnabled()
    assert win.timeline.blocks and win.slider.maximum() > 1000
    win.slider.setValue(1200)
    pix = win.grab()
    assert not pix.isNull()
    win.side_button.setChecked(True)
    assert not win.grab().isNull()


def test_no_drones_simulation_only(win, qapp):
    win.new_show()
    assert win.check() is True
    assert win.link_label.text().endswith("Симуляция")
    assert "Ждём" not in win.drones_panel.empty.text()
    assert not win.start_button.isEnabled() and not win.arm_box.isEnabled()
    win.emergency()                                        # safe with no drones, stops playback
    win.toggle_play()
    assert win.playing
    QTest.keyClick(win, Qt.Key.Key_Escape)                 # Esc without armed/flying drones: nothing
    assert win.playing
    win.emergency_button.click()
    assert not win.playing


def test_editing_invalidates_check(win, qapp):
    win.new_show()
    win.check()
    win.editor.appendPlainText("# edit")
    assert win.dirty
    win.check()
    assert not win.dirty


def test_syntax_error_is_reported_with_line(win, qapp):
    win.new_show()
    win.editor.setPlainText("from litebee import Show\nshow = Show('x')\nshow.drone(1).rgb('pink')\n")
    assert win.check() is False
    assert win.problems[0][2] == 3 and "pink" in win.problems[0][1]
    assert win.last_report.strip()


def test_lbg_import_via_open(win, qapp, tmp_path):
    from test_show import make_lbg
    p = str(tmp_path / "FM10 sets-Imp.lbg")
    make_lbg(p)
    assert win.open_file(p)
    assert "show = Show('Imp')" in win.editor.toPlainText()
    assert win.path is None


def test_full_gui_flow_with_fake_drone(win, qapp):
    """Connect (loopback), check, load, arm, start with confirmation; arming resets afterwards."""
    port = free_port()
    with FakeDrone(port) as drone:
        win.new_show()
        assert win.check()
        assert win.connect_link(HOST, [HOST], port, drone.udp_port)
        assert pump(qapp, lambda: HOST in win.drones_panel.cards and win.controller.view(HOST).volts)
        assert win.link_label.text().endswith("Дронов в сети: 1")
        card = win.drones_panel.cards[HOST]
        assert card.role_number() == 1
        assert win.upload_button.isEnabled()
        assert not win.start_button.isEnabled() and "Загрузить" in win.start_button.toolTip()
        win.upload_button.click()
        assert pump(qapp, lambda: HOST in win.controller.loaded and not win.controller.busy)
        assert drone.checksum == win.controller.loaded[HOST].checksum
        assert not win.start_button.isEnabled() and "Взвести" in win.start_button.toolTip()
        assert drone.starts == []
        win.arm_box.setChecked(True)
        assert win.controller.armed and win.start_button.isEnabled()
        asked = []
        win.confirm_start = lambda ips, mission: asked.append((ips, mission.can_fly)) or True
        win.start_button.click()
        assert asked == [([HOST], True)]
        assert pump(qapp, lambda: len(drone.starts) == 1)
        assert pump(qapp, lambda: not win.controller.flying, 30)
        assert not win.controller.armed and not win.arm_box.isChecked()      # arming resets
        assert HOST not in win.controller.loaded
        assert drone.lands >= 3


def test_start_refuses_when_not_armed(win, qapp):
    port = free_port()
    with FakeDrone(port) as drone:
        win.new_show()
        win.check()
        assert win.connect_link(HOST, [HOST], port, drone.udp_port)
        assert pump(qapp, lambda: HOST in win.drones_panel.cards and win.controller.view(HOST).volts)
        assert pump(qapp, lambda: win.upload_button.isEnabled())
        win.upload_button.click()
        assert pump(qapp, lambda: HOST in win.controller.loaded and not win.controller.busy)
        win.controller.start(HOST)                         # armed is False: must be refused
        win.confirm_start = lambda *a: pytest.fail("must not ask")
        assert drone.starts == [] and not win.controller.flying


def test_emergency_button_lands_armed_drone(win, qapp):
    port = free_port()
    with FakeDrone(port) as drone:
        win.new_show()
        win.check()
        assert win.connect_link(HOST, [HOST], port, drone.udp_port)
        assert pump(qapp, lambda: win.controller.view(HOST).volts)
        win.arm_box.setChecked(True)
        assert win.controller.armed
        QTest.keyClick(win, Qt.Key.Key_Escape)             # Esc lands while armed
        assert drone.wait_for(lambda: drone.lands >= 3)
        assert not win.controller.armed
        before = drone.lands
        win.emergency_button.click()
        assert drone.wait_for(lambda: drone.lands >= before + 3)


def test_connection_loss_resets_arming(win, qapp):
    port = free_port()
    with FakeDrone(port) as drone:
        win.new_show()
        win.check()
        assert win.connect_link(HOST, [HOST], port, drone.udp_port)
        assert pump(qapp, lambda: win.controller.view(HOST).volts)
        assert pump(qapp, lambda: HOST in win.drones_panel.cards)
        win.arm_box.setChecked(True)
        assert win.controller.armed
        drone.drop_connection()
        assert pump(qapp, lambda: not win.controller.armed)
        assert win.controller.view(HOST).state == "Нет связи"


def test_busy_port_message(win, qapp):
    import socket
    s = socket.socket()
    s.bind((HOST, 0))
    s.listen()
    port = s.getsockname()[1]
    try:
        assert win.connect_link(HOST, [HOST], port, free_port()) is False
        assert "Порт занят" in win.log_view.toPlainText()
    finally:
        s.close()


# ---- configurable height limit ----------------------------------------------------

TALL = """from litebee import Show

show = Show('Высокое')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.set_z(160, 3)
d.land()
"""


def height_errors(win):
    return [m for lvl, m, _, _ in win.problems if lvl == "error" and "больше лимита" in m]


def make_window(settings_path=None):
    w = MainWindow(settings_path=settings_path, controller=FlightController(timing=FAST))
    w.show()
    return w


def test_limit_spin_defaults_and_ceiling(win):
    assert win.limit_spin.value() == 150 and win.max_height_cm == 150
    assert win.limit_spin.minimum() == 20 and win.limit_spin.maximum() == HARD_MAX_HEIGHT_CM == 200
    win.limit_spin.setValue(999)                       # the spin box cannot go above the ceiling
    assert win.limit_spin.value() == 200 and win.max_height_cm == 200
    win.limit_spin.setValue(1)
    assert win.limit_spin.value() == 20
    win.limit_spin.setValue(170)
    for bad in (201, 19, 170.5, "x"):                  # direct calls are refused too
        assert win.set_max_height(bad) is False
        assert win.max_height_cm == 170 and win.limit_spin.value() == 170
    assert "вне допустимых пределов" in win.log_view.toPlainText()
    assert win.controller.max_height_cm == 170 and win.preview.max_height_cm == 170


def test_default_limit_flags_160_and_raised_limit_passes(win, qapp):
    win.editor.setPlainText(TALL)
    win.stack.setCurrentIndex(1)
    assert win.check() is False
    assert len(height_errors(win)) == 1 and "лимита 150 см" in height_errors(win)[0]
    assert "лимита 150 см" in win.last_report
    win.limit_spin.setValue(170)
    assert win.dirty                                   # the old check no longer counts
    assert "Нажмите «Проверить»" in win.start_button.toolTip()
    assert win.check() is True
    assert height_errors(win) == [] and not win.dirty
    win.limit_spin.setValue(155)                       # lowering invalidates again and flags again
    assert win.dirty and win.check() is False and len(height_errors(win)) == 1
    assert "лимита 155 см" in height_errors(win)[0]


def test_preview_limit_label_shows_active_value(win):
    assert win.preview.limit_text() == "лимит 150 см" and win.preview.z_max == 180
    win.limit_spin.setValue(170)
    assert win.preview.limit_text() == "лимит 170 см" and win.preview.z_max == 200
    win.limit_spin.setValue(200)
    assert win.preview.limit_text() == "лимит 200 см" and win.preview.z_max == 220
    with pytest.raises(Exception):
        win.preview.set_max_height(201)                 # the widget refuses it as well
    win.new_show()
    win.check()
    win.side_button.setChecked(True)
    assert not win.grab().isNull()                       # the side view paints at the high limit


def test_limit_is_remembered_between_runs(qapp, tmp_path):
    ini = str(tmp_path / "settings.ini")
    w = make_window(ini)
    assert w.limit_spin.value() == 150
    w.limit_spin.setValue(170)
    w.close()
    w2 = make_window(ini)
    try:
        assert w2.limit_spin.value() == 170 and w2.max_height_cm == 170
        assert w2.preview.limit_text() == "лимит 170 см" and w2.controller.max_height_cm == 170
    finally:
        w2.close()


@pytest.mark.parametrize("stored", ["999", "5", "abc", "170.5", ""])
def test_invalid_stored_limit_falls_back_to_default(qapp, tmp_path, stored):
    from PySide6.QtCore import QSettings
    ini = str(tmp_path / "settings.ini")
    cfg = QSettings(ini, QSettings.Format.IniFormat)
    cfg.setValue("limits/max_height_cm", stored)
    cfg.sync()
    w = make_window(ini)
    try:
        assert w.limit_spin.value() == 150 and w.controller.max_height_cm == 150
    finally:
        w.close()


def test_start_dialog_shows_active_limit(win):
    from litebee.mission import hop_mission
    win.limit_spin.setValue(170)
    lines = win.start_summary(hop_mission(160, 3, max_height_cm=170))
    assert any("Высота до 160 см (лимит 170 см)" in line for line in lines)


def test_limit_flows_into_upload_and_start(win, qapp):
    port = free_port()
    with FakeDrone(port) as drone:
        win.editor.setPlainText(TALL)
        win.stack.setCurrentIndex(1)
        win.limit_spin.setValue(170)
        assert win.check()
        assert win.connect_link(HOST, [HOST], port, drone.udp_port)
        assert pump(qapp, lambda: HOST in win.drones_panel.cards and win.controller.view(HOST).volts)
        assert pump(qapp, lambda: win.upload_button.isEnabled())
        win.upload_button.click()
        assert pump(qapp, lambda: HOST in win.controller.loaded and not win.controller.busy)       # 160 cm accepted at limit 170
        assert win.controller.loaded[HOST].max_height_cm == 160
        win.arm_box.setChecked(True)
        win.limit_spin.setValue(150)                                    # lowered after the upload
        assert not win.start_button.isEnabled()                         # a new check is needed
        win.controller.start(HOST)                                      # and the core refuses as well
        assert drone.starts == [] and not win.controller.flying
        assert "больше лимита 150 см" in win.log_view.toPlainText()


def test_upload_refused_at_default_limit(qapp):
    """A mission built at limit 170 is refused by the controller when the limit is 150."""
    from litebee.mission import hop_mission
    port = free_port()
    ctl = FlightController(timing=FAST)
    with FakeDrone(port) as drone:
        try:
            ctl.connect_link(HOST, [HOST], port, drone.udp_port)
            assert pump(qapp, lambda: ctl.view(HOST).volts)
            logs = []
            ctl.log.connect(logs.append)
            ctl.upload(HOST, hop_mission(160, 3, max_height_cm=170))
            assert pump(qapp, lambda: not ctl.busy)
            assert HOST not in ctl.loaded and drone.steps == {}
            assert any("больше лимита 150 см" in m for m in logs)
            ctl.set_max_height(170)
            ctl.upload(HOST, hop_mission(160, 3, max_height_cm=170))
            assert pump(qapp, lambda: HOST in ctl.loaded)
            with pytest.raises(Exception):
                ctl.set_max_height(201)
        finally:
            ctl.shutdown()


# ---- timeout of the check ----------------------------------------------------------

LOOP = "from litebee import Show\nwhile True:\n    pass\n"


def test_check_timeout_keeps_window_responsive(win, qapp):
    assert win.show_timeout == 5
    win.new_show()
    win.show_timeout = 1.0
    win.editor.setPlainText(LOOP)
    t0 = time.time()
    win.check_button.click()
    assert time.time() - t0 < 0.5                       # the click returned at once: no blocking
    assert win._checking and not win.check_button.isEnabled()
    assert win.check_button.text() == "Проверяю…"
    assert not win.upload_button.isEnabled() and "Идёт проверка" in win.upload_button.toolTip()
    ticks = []
    from PySide6.QtCore import QTimer
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(20)
    assert pump(qapp, lambda: not win._checking, 6)
    timer.stop()
    assert time.time() - t0 < 1.0 + 2 + 1               # limit + 2 s (+1 s for the slow test machine)
    assert len(ticks) >= 10                             # the event loop kept running meanwhile
    assert win.check_button.isEnabled() and win.check_button.text() == "Проверить"
    assert win.has_errors and win.show_obj is None
    assert win.problems[0][:2] == ("error", "Шоу выполняется дольше 1 с. Проверьте циклы в коде")
    assert win.problem_list.item(0).text().endswith("Проверьте циклы в коде")
    assert "дольше 1 с" in win.last_report
    win.editor.setPlainText("from litebee import Show\nshow = Show('ok')\nshow.drone(1).takeoff(60, 2)\n")
    assert win.check() is True and win.show_obj.name == "ok"        # the window recovers


def test_check_timeout_message_with_default_limit_text(win, qapp):
    win.new_show()
    win.show_timeout = 5.0
    win.editor.setPlainText(LOOP)
    t0 = time.time()
    assert win.check() is False
    assert time.time() - t0 < 5 + 2
    assert win.problems[0][1] == "Шоу выполняется дольше 5 с. Проверьте циклы в коде"


def test_second_click_during_check_does_nothing(win, qapp):
    win.new_show()
    win.show_timeout = 1.0
    win.editor.setPlainText(LOOP)
    win.start_check()
    run = win._check_run
    win.start_check()
    assert win._check_run is run
    assert pump(qapp, lambda: not win._checking, 6)


def test_new_document_cancels_running_check(win, qapp):
    win.new_show()
    win.show_timeout = 30
    win.editor.setPlainText(LOOP)
    win.start_check()
    run = win._check_run
    assert win._checking
    time.sleep(0.5)
    win.new_show()                                       # replaces the document: the worker is killed
    assert not win._checking and win.check_button.isEnabled() and win.check_button.text() == "Проверить"
    assert pump(qapp, lambda: run._proc is not None and run._proc.poll() is not None, 5)
    pump(qapp, lambda: False, 0.3)
    assert win.show_obj is None and win.problems == []   # the late result was dropped


def test_too_many_steps_is_reported_in_the_window(win, qapp):
    win.new_show()
    win.editor.setPlainText("from litebee import Show\nshow = Show('big')\nd = show.drone(1)\n"
                            "for i in range(10001):\n    d.set_z(100, 0.1)\n")
    assert win.check() is False
    assert win.problems[0][1].startswith("Шоу содержит больше 10000 шагов. Проверьте циклы в коде")
    assert win.problems[0][2] == 5


# ---- cell moves: position in the card, refusals, start dialog ------------------------

CODE_TEXT = """from litebee import Show

show = Show('Клетки')

d = show.drone(1)
d.calibrate(5)
d.takeoff(50, 5)
d.code(97, 4)
d.land()
"""


def connect_with_code_show(win, qapp, drone, port, text=CODE_TEXT):
    win.editor.setPlainText(text)
    win.stack.setCurrentIndex(1)
    assert win.check()
    assert win.connect_link(HOST, [HOST], port, drone.udp_port)
    assert pump(qapp, lambda: HOST in win.drones_panel.cards and win.controller.view(HOST).volts)


def test_card_shows_the_cell_or_no_position(win, qapp):
    port = free_port()
    with FakeDrone(port) as drone:                                  # fresh drone: x = y = 0
        win.new_show()
        assert win.connect_link(HOST, [HOST], port, drone.udp_port)
        assert pump(qapp, lambda: HOST in win.drones_panel.cards and win.controller.view(HOST).volts)
        card = win.drones_panel.cards[HOST]
        assert card.cell.text() == "Нет позиции"
        assert not win.controller.view(HOST).has_fix and win.controller.view(HOST).cell is None
        drone.set_fix((3, 317))                                     # round(3/40) + 12 * round(317/40) = 96
        assert pump(qapp, lambda: card.cell.text() == "Клетка 96")
        assert win.controller.view(HOST).cell == 96
        assert "клетка 96" in card.accessibleName()
        drone.set_fix((900, 40))
        assert pump(qapp, lambda: card.cell.text() == "Вне коврика")
        drone.set_fix(None)
        assert pump(qapp, lambda: card.cell.text() == "Нет позиции")


def test_cell_move_show_is_refused_without_a_fix(win, qapp):
    from litebee.safety import NO_FIX_MESSAGE
    port = free_port()
    with FakeDrone(port) as drone:
        connect_with_code_show(win, qapp, drone, port)
        assert not win.upload_button.isEnabled()
        assert win.upload_button.toolTip() == NO_FIX_MESSAGE
        assert "50 см" in NO_FIX_MESSAGE and "нет позиции" in NO_FIX_MESSAGE
        win.upload_button.click()                                    # a disabled button does nothing
        win.upload()                                                 # and the method refuses as well
        assert drone.steps == {} and drone.cleared == 0
        assert not win.start_button.isEnabled() and win.start_button.toolTip() == NO_FIX_MESSAGE
        drone.set_fix((40, 320))                                     # the drone has hopped: now it has a fix
        assert pump(qapp, lambda: win.upload_button.isEnabled())


def test_cell_move_show_is_refused_from_a_wrong_start_cell(win, qapp):
    port = free_port()
    with FakeDrone(port, fix=(400, 400)) as drone:                   # stands on cell 130, the show expects 97
        connect_with_code_show(win, qapp, drone, port)
        assert pump(qapp, lambda: win.controller.view(HOST).cell == 130)
        assert pump(qapp, lambda: "клетке 130" in win.upload_button.toolTip())
        tip = win.upload_button.toolTip()
        assert "клетке 97" in tip and "200 см" in tip and not win.upload_button.isEnabled()
        win.upload()
        assert drone.steps == {}


def test_cell_move_show_uploads_starts_and_the_dialog_names_the_cell(win, qapp):
    port = free_port()
    with FakeDrone(port, fix=(3, 317)) as drone:                     # on cell 96, the show goes to 97 first
        connect_with_code_show(win, qapp, drone, port)
        assert pump(qapp, lambda: win.controller.view(HOST).cell == 96)
        assert pump(qapp, lambda: win.upload_button.isEnabled())
        win.upload_button.click()
        assert pump(qapp, lambda: HOST in win.controller.loaded and not win.controller.busy)
        mission = win.controller.loaded[HOST]
        assert drone.checksum == mission.checksum == 6 and mission.has_moves
        summary = win.start_summary(mission, HOST)
        assert any(line.startswith("Дрон на клетке 96") and "к клетке 97" in line for line in summary)
        win.arm_box.setChecked(True)
        assert win.start_button.isEnabled()
        seen = []
        win.confirm_start = lambda ips, m: seen.append(win.start_summary(m, ips[0])) or True
        win.start_button.click()
        assert len(seen) == 1 and any("Дрон на клетке 96" in line for line in seen[0])
        assert pump(qapp, lambda: len(drone.starts) == 1)
        assert pump(qapp, lambda: not win.controller.flying, 30)


def test_start_is_refused_when_the_drone_was_moved_after_upload(win, qapp):
    port = free_port()
    with FakeDrone(port, fix=(40, 320)) as drone:
        connect_with_code_show(win, qapp, drone, port)
        assert pump(qapp, lambda: win.upload_button.isEnabled())
        win.upload_button.click()
        assert pump(qapp, lambda: HOST in win.controller.loaded and not win.controller.busy)
        win.arm_box.setChecked(True)
        assert win.start_button.isEnabled()
        drone.set_fix((400, 400))
        assert pump(qapp, lambda: win.controller.view(HOST).cell == 130)
        assert pump(qapp, lambda: not win.start_button.isEnabled())
        assert "клетке 130" in win.start_button.toolTip()
        win.confirm_start = lambda *a: pytest.fail("must not ask")
        win.start()                                                  # the method refuses too
        win.controller.start(HOST)                                   # and so does the controller
        assert drone.starts == [] and not win.controller.flying
        assert "клетке 130" in win.log_view.toPlainText()


def test_code_z_and_circle_are_still_not_uploadable(win, qapp):
    for call in ("d.code_z(97, 80, 4)", "d.circle(2, 66, 77, 13, 'cw')"):
        port = free_port()
        text = ("from litebee import Show\nshow = Show('x')\nd = show.drone(1)\nd.takeoff(50, 5)\n"
                f"d.code(97, 4)\n{call}\nd.land()\n")
        with FakeDrone(port, fix=(40, 320)) as drone:
            win.log_view.clear()
            connect_with_code_show(win, qapp, drone, port, text)
            assert any("загрузка в дрон недоступна" in m for _, m, _, _ in win.problems)
            win.upload()
            assert drone.steps == {} and "Загрузка невозможна" in win.log_view.toPlainText()
            win.controller.disconnect_link()
