"""The reference panel, the F1 dock in the main window and the editor hints (offscreen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QHelpEvent, QTextCursor  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QToolTip  # noqa: E402

from conftest import FAST  # noqa: E402
from app import theme  # noqa: E402
from app.editor import API, CodeEditor  # noqa: E402
from app.main_window import MainWindow  # noqa: E402
from app.reference_panel import (NO_EDITOR, READ_ONLY, ReferencePanel, article_html, entry_html,  # noqa: E402
                                 insert_snippet, item_html)
from app.session import FlightController  # noqa: E402
from litebee import reference as ref  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.stylesheet())
    return app


@pytest.fixture
def panel(qapp):
    p = ReferencePanel()
    p.resize(380, 600)
    p.show()
    QTest.qWaitForWindowActive(p)
    yield p
    p.close()


@pytest.fixture
def win(qapp):
    w = MainWindow(controller=FlightController(timing=FAST))
    w.show()
    QTest.qWaitForWindowActive(w)
    yield w
    w.close()


def _key(p, i):
    return p.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)


def tree_keys(p):
    return [_key(p, i) for i in range(p.tree.topLevelItemCount()) if _key(p, i)]


def tree_headers(p):
    return [p.tree.topLevelItem(i).text(0) for i in range(p.tree.topLevelItemCount()) if not _key(p, i)]


# ---- panel ------------------------------------------------------------------------------------

def test_list_is_grouped_by_topic_and_complete(panel):
    assert tree_keys(panel) == [it.key for it in ref.items()]
    assert tree_headers(panel) == [t for _, t in ref.TOPICS]
    assert panel.current_key == ref.items()[0].key          # something is always shown


@pytest.mark.parametrize("it", ref.items(), ids=lambda i: i.key)
def test_every_item_renders(panel, it):
    assert panel.show_key(it.key)
    assert panel.current_key == it.key
    assert panel.body.toPlainText().strip()
    assert panel.summary.text() == it.summary
    assert panel.example_box.isVisibleTo(panel) == bool(it.example)
    if it.article:
        assert panel.title.text() == it.title and not panel.badge.isVisibleTo(panel)
    else:
        assert panel.title.text() == it.signature
        # the status is a word and an icon, never colour alone
        assert panel.badge.text() == f"{it.icon} {it.status}" and it.icon and it.status
        assert panel.badge.property("status") in ("verified", "sim", "helper")


def test_search_filters_by_name_and_summary(panel):
    panel.search.setText("rgb")
    assert tree_keys(panel)[:2] == ["Drone.rgb", "Drone.rgb_value"]
    assert panel.current_key == "Drone.rgb" and panel.tree.isVisibleTo(panel)
    panel.search.setText("полкруга")                          # a word from a summary
    assert "Drone.circle_z" in tree_keys(panel) and "Drone.takeoff" not in tree_keys(panel)
    panel.search.setText("zzz-nothing")
    assert tree_keys(panel) == [] and panel.empty.isVisibleTo(panel) and not panel.tree.isVisibleTo(panel)
    assert not panel.example_box.isVisibleTo(panel)
    panel.search.clear()
    assert tree_keys(panel) == [it.key for it in ref.items()] and panel.tree.isVisibleTo(panel)


def test_selection_survives_filtering_and_show_key_clears_search(panel):
    panel.show_key("Drone.land")
    panel.search.setText("land")
    assert panel.current_key == "Drone.land"
    panel.show_key("Drone.takeoff")                            # hidden by the search: the search is cleared
    assert panel.search.text() == "" and panel.current_key == "Drone.takeoff"
    assert not panel.show_key("no.such.key")


def test_keyboard_navigation(panel, qapp):
    panel.search.setFocus()
    QTest.keyClicks(panel.search, "rgb")
    QTest.keyClick(panel.search, Qt.Key.Key_Down)               # search -> list
    assert panel.tree.hasFocus()
    QTest.keyClick(panel.tree, Qt.Key.Key_Down)
    assert panel.current_key == "Drone.rgb_value"
    for w in (panel.search, panel.tree, panel.body, panel.insert_button):   # all reachable by Tab
        assert w.focusPolicy() & Qt.FocusPolicy.TabFocus
    css = theme.stylesheet()
    assert "QTreeWidget#referenceTree:focus" in css and "QTextBrowser#referenceBody:focus" in css
    assert "QLineEdit:focus" in css and "QPushButton:focus" in css


def test_header_rows_are_skipped_by_the_keyboard(panel):
    panel.show_key(ref.ARTICLES[-1].key)                        # the last article, a header follows it
    QTest.keyClick(panel.tree, Qt.Key.Key_Down)
    assert panel.current_key == "Show.Show"
    QTest.keyClick(panel.tree, Qt.Key.Key_Up)
    assert panel.current_key == ref.ARTICLES[-1].key


def test_detail_html_uses_theme_tokens_and_has_the_facts():
    html = entry_html(ref.get("Drone.takeoff"))
    assert "Команда формации: takeOff (1)" in html and "litebeeWingFormation_takeOff" in html
    assert theme.TOKENS["border"] in html and "см" in html
    arts = article_html(ref.get("commands"))
    assert "moveXYZ" in arts and "только симулятор" in arts and "<table" in arts
    assert item_html(ref.get("mat")) == article_html(ref.get("mat"))


def test_html_escapes_text():
    e = ref.Entry("Drone", "x", "method", "x(a)", "S", "sim", ref.STATUS_HELPER, notes=("a < b & c",))
    assert "a &lt; b &amp; c" in entry_html(e)


def test_contrast_of_status_colours():
    def lum(hexc):
        v = [int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        v = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]

    def ratio(a, b):
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    t = theme.TOKENS
    for fg in ("ok", "warn", "text2", "text", "accent"):
        for bg in ("bg", "panel", "card"):
            assert ratio(t[fg], t[bg]) >= 4.5, (fg, bg)


# ---- inserting ---------------------------------------------------------------------------------

def test_insert_snippet_on_blank_line_and_after_code(qapp):
    ed = QPlainTextEdit()
    ed.setPlainText("a = 1\n\nb = 2")
    c = ed.textCursor()
    c.setPosition(len("a = 1\n"))                               # the blank line
    ed.setTextCursor(c)
    insert_snippet(ed, "d.code(97, 4)\nd.land()\n")
    assert ed.toPlainText() == "a = 1\nd.code(97, 4)\nd.land()\nb = 2"
    c = ed.textCursor()
    c.setPosition(0)                                           # a line with code: snippet goes below it
    ed.setTextCursor(c)
    insert_snippet(ed, "d.rgb('red')\n")
    assert ed.toPlainText().splitlines()[:2] == ["a = 1", "d.rgb('red')"]
    ed.undo()                                                  # one undo step per insertion
    assert ed.toPlainText().splitlines()[:2] == ["a = 1", "d.code(97, 4)"]


def test_insert_snippet_keeps_indentation(qapp):
    ed = QPlainTextEdit()
    ed.setPlainText("for i in range(3):\n    d.rgb('red')")
    c = ed.textCursor()
    c.movePosition(QTextCursor.MoveOperation.End)
    ed.setTextCursor(c)
    insert_snippet(ed, "d.code(1, 2)\n\nd.land()\n")
    assert ed.toPlainText() == "for i in range(3):\n    d.rgb('red')\n    d.code(1, 2)\n\n    d.land()"


# ---- main window -------------------------------------------------------------------------------

def test_dock_is_hidden_until_f1_or_the_button(win, qapp):
    assert win.reference_dock.isHidden() and not win.reference_button.isChecked()
    assert win.reference_button.text() == "Справочник" and "F1" in win.reference_button.toolTip()
    QTest.keyClick(win, Qt.Key.Key_F1)
    qapp.processEvents()
    assert not win.reference_dock.isHidden() and win.reference_button.isChecked()
    assert win.reference_dock.panel.search.hasFocus()
    QTest.keyClick(win, Qt.Key.Key_F1)
    assert win.reference_dock.isHidden() and not win.reference_button.isChecked()
    win.reference_button.click()
    assert not win.reference_dock.isHidden() and win.reference_button.isChecked()
    win.reference_dock.title_bar.close_button.click()
    assert win.reference_dock.isHidden() and not win.reference_button.isChecked()


def test_f1_on_a_word_opens_that_function(win, qapp):
    win.new_show()
    win.editor.setPlainText("d = show.drone(1)\nd.takeoff(100, 5)\n")
    win.editor.setFocus()
    c = win.editor.textCursor()
    c.setPosition(len("d = show.drone(1)\nd.take") + 1)
    win.editor.setTextCursor(c)
    assert win.editor.word_at_cursor() == "takeoff"
    win.reference_dock.on_f1()
    assert not win.reference_dock.isHidden()
    assert win.reference_dock.panel.current_key == "Drone.takeoff"
    win.reference_dock.close_panel()
    c.setPosition(0)                                           # `d` is not a DSL word: F1 just toggles
    win.editor.setTextCursor(c)
    win.editor.setFocus()
    win.reference_dock.on_f1()
    assert not win.reference_dock.isHidden()
    win.reference_dock.on_f1()
    assert win.reference_dock.isHidden()


def test_insert_button_follows_the_editor_state(win, qapp):
    dock = win.reference_dock
    dock.open("Drone.code")
    p = dock.panel
    assert win.stack.currentIndex() == 0                       # no document yet
    assert not p.insert_button.isEnabled() and NO_EDITOR in p.insert_button.toolTip()
    assert p.insert_reason.text() == NO_EDITOR
    win.new_show()
    assert p.insert_button.isEnabled() and not p.insert_reason.text()
    win.editor.setReadOnly(True)                               # a drone is flying
    assert not p.insert_button.isEnabled() and p.insert_reason.text() == READ_ONLY
    assert dock.insert("d.land()\n") is False
    win.editor.setReadOnly(False)
    assert p.insert_button.isEnabled()


def test_insert_button_puts_the_example_at_the_cursor(win, qapp):
    win.new_show()
    win.editor.setPlainText("d = show.drone(1)\n\nd.land()\n")
    c = win.editor.textCursor()
    c.setPosition(len("d = show.drone(1)\n"))
    win.editor.setTextCursor(c)
    win.reference_dock.open("Drone.code")
    win.reference_dock.panel.insert_button.click()
    assert win.editor.toPlainText() == "d = show.drone(1)\nd.code(97, 4)   # к клетке 97 за 4 с\nd.land()\n"
    assert win.editor.hasFocus()


def test_dock_makes_room_and_gives_it_back(win, qapp):
    win.resize(1100, 700)
    dock = win.reference_dock
    dock._screen_width = lambda: 3000                          # the offscreen screen is only 800 wide
    dock.open()
    assert dock._grown == 380 + 6 and win.width() == 1100 + dock._grown
    dock.close_panel()
    assert win.width() == 1100 and dock._grown == 0
    dock._screen_width = lambda: 1180                          # a small screen: grow only as far as it allows
    dock.open()
    assert dock._grown == 80 and win.width() == 1180
    dock.close_panel()
    assert win.width() == 1100


def test_escape_still_belongs_to_the_emergency_stop(win, qapp):
    win.new_show()
    assert win.check()
    win.reference_dock.open()
    win.toggle_play()
    assert win.playing
    QTest.keyClick(win, Qt.Key.Key_Escape)                      # no armed or flying drone: nothing happens
    assert win.playing and not win.reference_dock.isHidden()
    win.emergency_button.click()
    assert not win.playing


# ---- editor hints ------------------------------------------------------------------------------

def test_editor_api_is_read_from_the_reference(qapp):
    assert set(API) == {e.name for e in ref.drone_commands()}
    for name, (sig, doc) in API.items():
        e = ref.entries_dict()[("Drone", name)]
        assert (sig, doc) == (e.signature, e.summary)
    ed = CodeEditor()
    texts = [ed._model.item(i).text() for i in range(ed._model.rowCount())]
    assert any(t.startswith("takeoff   takeoff(z, seconds) — ") for t in texts)
    assert any(t.startswith("Show   Show(name)") for t in texts)


def test_editor_reference_entry(qapp):
    assert CodeEditor.reference_entry("takeoff").key == "Drone.takeoff"
    assert CodeEditor.reference_entry("Show").key == "Show.Show"
    assert CodeEditor.reference_entry("drone").key == "Show.drone"
    assert CodeEditor.reference_entry("duration") is None       # a simulator helper, not a show command
    assert CodeEditor.reference_entry("banana") is None


def test_editor_tooltip_shows_signature_and_status(qapp):
    ed = CodeEditor()
    ed.resize(500, 200)
    ed.show()
    ed.setPlainText("d.takeoff(100, 5)\nx = 1")
    qapp.processEvents()
    c = ed.textCursor()
    c.setPosition(4)
    pos = ed.cursorRect(c).center()
    QApplication.sendEvent(ed, QHelpEvent(QEvent.Type.ToolTip, pos, ed.viewport().mapToGlobal(pos)))
    qapp.processEvents()
    text = QToolTip.text()
    assert "takeoff(z, seconds)" in text and ref.STATUS_VERIFIED in text
    assert CodeEditor.reference_entry("x") is None              # over `x` there is nothing to show
    ed.close()
