"""Main window of the Litebee IDE (layout and behaviour: docs/UI_DESIGN.md)."""
import os
import sys
import threading
import time

from PySide6.QtCore import QEventLoop, QSettings, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
                               QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSlider,
                               QSpinBox, QSplitter, QStackedWidget, QTabWidget, QToolButton,
                               QVBoxLayout, QWidget)

from litebee import protocol as proto
from litebee.lbg import LbgError, lbg_to_source
from litebee.loader import SHOW_TIMEOUT_S, ShowLoadError, ShowRun
from litebee.mission import (DEFAULT_MAX_HEIGHT_CM, HARD_MAX_HEIGHT_CM, MIN_TAKEOFF_CM,
                             resolve_max_height)
from litebee.safety import MIN_APPROACH_CM, SafetyError, check_show, position_problem
from litebee.show import UploadUnsupported, drone_to_mission

from . import theme
from .drone_art import DroneArt
from .drones_panel import DronesPanel
from .editor import CodeEditor
from .preview import PreviewWidget, TimelineWidget
from .reference_panel import ReferenceDock
from .session import FlightController

TEMPLATE = """from litebee import Show

show = Show('Новое шоу')

d = show.drone(1)
d.calibrate(5)
d.takeoff(100, 5)
d.rgb('green')
d.set_z(100, 3)
d.rgb('black')
d.land()
"""

DISCLAIMER = ("Модель приблизительная: стартовое положение берётся с первой клетки, посадка занимает 3 с, "
              "направление кругов угадано.")


def ru_plural(n, forms=("дрон", "дрона", "дронов")):
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return f"{n} {forms[0]}"
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return f"{n} {forms[1]}"
    return f"{n} {forms[2]}"


class ConnectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Связь с дронами")
        form = QFormLayout(self)
        self.pc = QLineEdit()
        self.pc.setPlaceholderText("192.168.13.100")
        self.drones = QLineEdit()
        self.drones.setPlaceholderText("192.168.13.108, 192.168.13.109")
        self.tcp = QSpinBox()
        self.tcp.setRange(1, 65535)
        self.tcp.setValue(proto.TCP_PORT)
        self.udp = QSpinBox()
        self.udp.setRange(1, 65535)
        self.udp.setValue(proto.UDP_REMOTE)
        form.addRow("IP этого ПК", self.pc)
        form.addRow("IP дронов (белый список)", self.drones)
        form.addRow("TCP-порт", self.tcp)
        form.addRow("UDP-порт дронов", self.udp)
        note = QLabel("Приложение объявит IP ПК в сети и будет ждать дронов. Лететь можно только дронам из списка.")
        note.setProperty("role", "secondary")
        note.setWordWrap(True)
        form.addRow(note)
        row = QHBoxLayout()
        ok = QPushButton("Подключить")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(ok)
        form.addRow(row)

    def values(self):
        ips = [s.strip() for s in self.drones.text().replace(";", ",").split(",") if s.strip()]
        return self.pc.text().strip(), ips, self.tcp.value(), self.udp.value()


class MainWindow(QMainWindow):
    check_finished = Signal(bool)          # a check ended; True when it found no errors
    _check_done = Signal(object, object)   # (run, result) from the worker thread to the GUI thread

    def __init__(self, settings_path=None, controller=None):
        super().__init__()
        self.setWindowTitle("Litebee IDE")
        self.setMinimumSize(1100, 700)
        self.setAcceptDrops(True)
        self.settings = QSettings(settings_path, QSettings.Format.IniFormat) if settings_path else None
        self.controller = controller or FlightController(self)
        self.path = None
        self.title = "Без названия"
        self.show_obj = None
        self.checked_text = None
        self.has_errors = False
        self.last_report = ""
        self.problems = []              # [(level, message, line, t)]
        self.confirm_start = self._confirm_start_dialog      # tests may replace this
        self.playing = False
        self.show_timeout = SHOW_TIMEOUT_S      # seconds the show code may run during a check
        self._checking = False
        self._check_run = None
        self.max_height_cm = self._stored_max_height()
        self.checked_limit = None               # height limit used by the last check
        self._build()
        self.reference_dock = ReferenceDock(self, self.editor, self.reference_button)     # F1, docs/UI_DESIGN.md
        self._check_done.connect(self._on_check_done)
        self.controller.set_max_height(self.max_height_cm)
        self.controller.log.connect(self.append_log)
        self.controller.changed.connect(self.refresh)
        self.controller.armed_changed.connect(self._on_armed_changed)
        self.controller.busy_changed.connect(lambda _: self.refresh())
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.controller.poll)
        self.poll_timer.start(250)
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._tick)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._on_escape)
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_dialog)
        self._restore_layout()
        self.refresh()

    # ---- construction ------------------------------------------------------

    def _btn(self, text, name=None, tip=None):
        b = QPushButton(text)
        if name:
            b.setObjectName(name)
        if tip:
            b.setToolTip(tip)
        return b

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        # 1. header
        head = QHBoxLayout()
        self.project_label = QLabel("Litebee IDE")
        self.project_label.setObjectName("projectName")
        self.file_label = QLabel("")
        self.file_label.setProperty("role", "secondary")
        self.link_label = QLabel()
        head.addWidget(self.project_label)
        head.addWidget(self.file_label)
        head.addStretch()
        head.addWidget(self.link_label)
        outer.addLayout(head)

        # 2. toolbar
        bar = QHBoxLayout()
        self.open_button = self._btn("Открыть", "open")
        self.save_button = self._btn("Сохранить", "save")
        self.check_button = self._btn("Проверить", "primary", "Симуляция и проверки безопасности")
        self.upload_button = self._btn("Загрузить", "upload")
        self.arm_box = QCheckBox("Взвести")
        self.arm_box.setObjectName("arm")
        self.arm_box.setToolTip("Разрешает старт. Сбрасывается после каждого полёта и при потере связи")
        self.start_button = self._btn("Старт", "start")
        self.link_button = self._btn("Связь…", "link", "Подключить дроны по Wi-Fi")
        self.check_button.setObjectName("primary")
        for w in (self.open_button, self.save_button, self.check_button, self.upload_button, self.arm_box,
                  self.start_button):
            bar.addWidget(w)
        bar.addStretch()
        limit_label = QLabel("Лимит высоты")
        limit_label.setProperty("role", "secondary")
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(MIN_TAKEOFF_CM, HARD_MAX_HEIGHT_CM)     # the ceiling cannot be exceeded here
        self.limit_spin.setSuffix(" см")
        self.limit_spin.setValue(self.max_height_cm)
        self.limit_spin.setAccessibleName("Лимит высоты")
        self.limit_spin.setToolTip(f"Предельная высота для проверки и загрузки, от {MIN_TAKEOFF_CM} до "
                                   f"{HARD_MAX_HEIGHT_CM} см. По умолчанию {DEFAULT_MAX_HEIGHT_CM} см")
        self.limit_spin.valueChanged.connect(self.set_max_height)
        bar.addWidget(limit_label)
        bar.addWidget(self.limit_spin)
        bar.addWidget(self.link_button)
        self.reference_button = self._btn("Справочник", "reference")
        bar.addWidget(self.reference_button)
        outer.addLayout(bar)
        self.open_button.clicked.connect(self.open_dialog)
        self.save_button.clicked.connect(self.save)
        self.check_button.clicked.connect(self.start_check)
        self.upload_button.clicked.connect(self.upload)
        self.arm_box.toggled.connect(self._on_arm_toggled)
        self.start_button.clicked.connect(self.start)
        self.link_button.clicked.connect(self.connect_dialog)

        # 3. content: empty state or workspace
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.stack.addWidget(self._build_empty())
        self.stack.addWidget(self._build_workspace())

        # 5. bottom strip
        bottom = QHBoxLayout()
        self.drones_panel = DronesPanel()
        self.drones_panel.selection_changed.connect(self.refresh)
        bottom.addWidget(self.drones_panel, 1)
        self.emergency_button = QPushButton("Аварийная посадка")
        self.emergency_button.setObjectName("emergency")
        self.emergency_button.setToolTip("Посадить все дроны сейчас (Esc, если дрон взведён или летит)")
        self.emergency_button.clicked.connect(self.emergency)
        bottom.addWidget(self.emergency_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        outer.addLayout(bottom)

        self.setTabOrder(self.check_button, self.upload_button)

    def _build_empty(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addStretch()
        lay.addWidget(DroneArt(), 0, Qt.AlignmentFlag.AlignHCenter)
        title = QLabel("Откройте шоу или создайте новое")
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Шоу — это файл на Python или проект LiteBee Go (.lbg). Можно перетащить файл в окно")
        sub.setProperty("role", "secondary")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row = QHBoxLayout()
        row.addStretch()
        self.empty_open = self._btn("Открыть шоу")
        self.empty_new = self._btn("Создать новое", "primary")
        self.empty_open.clicked.connect(self.open_dialog)
        self.empty_new.clicked.connect(self.new_show)
        row.addWidget(self.empty_open)
        row.addWidget(self.empty_new)
        row.addStretch()
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addLayout(row)
        lay.addStretch()
        return page

    def _build_workspace(self):
        ws = QWidget()
        lay = QVBoxLayout(ws)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.split_main = QSplitter(Qt.Orientation.Horizontal)
        self.split_main.setChildrenCollapsible(False)

        # left: editor + tabs
        self.split_left = QSplitter(Qt.Orientation.Vertical)
        self.split_left.setChildrenCollapsible(False)
        self.editor = CodeEditor()
        self.editor.setAccessibleName("Код шоу")
        self.editor.textChanged.connect(self._on_text_changed)
        self.tabs = QTabWidget()
        self.problem_list = QListWidget()
        self.problem_list.setAccessibleName("Список проблем")
        self.problem_list.itemActivated.connect(self._problem_activated)
        self.problem_list.itemClicked.connect(self._problem_activated)
        self.report_view = QPlainTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setAccessibleName("Отчёт проверки")
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setAccessibleName("Журнал")
        self.tabs.addTab(self.problem_list, "Проверки")
        self.tabs.addTab(self.report_view, "Отчёт")
        self.tabs.addTab(self.log_view, "Журнал")
        self.split_left.addWidget(self.editor)
        self.split_left.addWidget(self.tabs)
        self.split_left.setSizes([420, 160])

        # right: preview
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        top = QHBoxLayout()
        self.side_button = QToolButton()
        self.side_button.setText("Вид сбоку")
        self.side_button.setCheckable(True)
        self.side_button.toggled.connect(lambda c: self.preview.set_side(c))
        top.addWidget(QLabel("Превью"))
        top.addStretch()
        top.addWidget(self.side_button)
        rl.addLayout(top)
        self.preview = PreviewWidget()
        self.preview.threshold = MIN_APPROACH_CM
        self.preview.set_max_height(self.max_height_cm)
        rl.addWidget(self.preview, 1)
        self.disclaimer = QLabel(DISCLAIMER)
        self.disclaimer.setProperty("role", "secondary")
        self.disclaimer.setWordWrap(True)
        rl.addWidget(self.disclaimer)

        self.split_main.addWidget(self.split_left)
        self.split_main.addWidget(right)
        self.split_main.setSizes([560, 540])
        lay.addWidget(self.split_main, 1)

        # 4. timeline + playback
        self.timeline = TimelineWidget()
        self.timeline.time_selected.connect(self._seek)
        self.timeline.step_clicked.connect(lambda n, line: self.editor.go_to_line(line))
        lay.addWidget(self.timeline)
        play = QHBoxLayout()
        self.play_button = self._btn("Играть")
        self.play_button.clicked.connect(self.toggle_play)
        self.speed = QComboBox()
        for label, v in (("1×", 1), ("4×", 4), ("10×", 10)):
            self.speed.addItem(label, v)
        self.speed.setAccessibleName("Скорость симуляции")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setAccessibleName("Время")
        self.slider.valueChanged.connect(self._on_slider)
        self.time_label = QLabel("0,0 / 0,0 с")
        self.time_label.setProperty("role", "mono")
        play.addWidget(self.play_button)
        play.addWidget(self.speed)
        play.addWidget(self.slider, 1)
        play.addWidget(self.time_label)
        lay.addLayout(play)
        return ws

    # ---- layout persistence --------------------------------------------------

    def _restore_layout(self):
        if not self.settings:
            return
        for name, split in (("main", self.split_main), ("left", self.split_left)):
            raw = self.settings.value(f"splitter/{name}")
            if raw:
                try:
                    split.setSizes([int(v) for v in raw])
                except (TypeError, ValueError):
                    pass
        geo = self.settings.value("window/geometry")
        if geo:
            self.restoreGeometry(geo)

    def closeEvent(self, e):
        self._cancel_check()
        if self.settings:
            self.settings.setValue("splitter/main", self.split_main.sizes())
            self.settings.setValue("splitter/left", self.split_left.sizes())
            self.settings.setValue("window/geometry", self.saveGeometry())
            self.settings.sync()
        self.play_timer.stop()
        self.poll_timer.stop()
        self.controller.shutdown()
        super().closeEvent(e)

    # ---- files ---------------------------------------------------------------

    def new_show(self):
        self._set_document(TEMPLATE, None, "Новое шоу")

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Открыть шоу", "", "Шоу (*.py *.lbg)")
        if path:
            self.open_file(path)

    def open_file(self, path):
        """Open a .py show or import a .lbg project into the editor."""
        path = os.fspath(path)
        if path.lower().endswith(".lbg"):
            try:
                text = lbg_to_source(path)
            except LbgError as e:
                self.append_log(str(e))
                QMessageBox.warning(self, "Импорт .lbg", f"{e}. Проверьте, что файл создан в LiteBee Go")
                return False
            self._set_document(text, None, os.path.basename(path))
            self.append_log(f"Проект {os.path.basename(path)} импортирован")
        else:
            with open(path, encoding="utf-8") as f:
                self._set_document(f.read(), path, os.path.basename(path))
        return True

    def _set_document(self, text, path, title):
        self._cancel_check()
        self.path, self.title = path, title
        self.editor.setPlainText(text)
        self.show_obj = None
        self.checked_text = None
        self.has_errors = False
        self.problems = []
        self._show_problems()
        self.preview.set_show(None)
        self.timeline.set_show(None)
        self._set_duration(0)
        self.stack.setCurrentIndex(1)
        self.refresh()

    def save(self):
        if self.stack.currentIndex() != 1:
            return
        if not self.path:
            path, _ = QFileDialog.getSaveFileName(self, "Сохранить шоу", "show.py", "Шоу (*.py)")
            if not path:
                return
            self.path, self.title = path, os.path.basename(path)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
        self.append_log(f"Сохранено: {self.path}")
        self.refresh()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p.lower().endswith((".lbg", ".py")):
                self.open_file(p)
                break

    # ---- check -----------------------------------------------------------------

    def _on_text_changed(self):
        self.refresh()

    @property
    def dirty(self):
        return self.checked_text != self.editor.toPlainText() or self.checked_limit != self.max_height_cm

    # ---- height limit ------------------------------------------------------------

    def _stored_max_height(self):
        """The remembered limit; the default when nothing valid is stored."""
        if self.settings:
            try:
                return resolve_max_height(int(self.settings.value("limits/max_height_cm")))
            except (TypeError, ValueError, SafetyError):
                pass
        return DEFAULT_MAX_HEIGHT_CM

    def set_max_height(self, cm):
        """Set the height limit (20-200 cm). Returns False and changes nothing when it is refused."""
        try:
            cm = resolve_max_height(cm)
        except SafetyError as e:
            self.append_log(f"{e}. Лимит остался {self.max_height_cm} см")
            return False
        if cm != self.limit_spin.value():
            self.limit_spin.setValue(cm)        # calls back here with the same value
            return True
        changed = cm != self.max_height_cm
        self.max_height_cm = cm
        self.preview.set_max_height(cm)
        self.controller.set_max_height(cm)
        if self.settings:
            self.settings.setValue("limits/max_height_cm", cm)
            self.settings.sync()
        if changed:
            self.append_log(f"Лимит высоты: {cm} см. Нажмите «Проверить» ещё раз")
            self.refresh()
        return True

    # ---- check -----------------------------------------------------------------

    def start_check(self):
        """Run the show in a worker process (time-limited) without blocking the window.

        The result is applied in `_on_check_done`; `check_finished` is emitted at the end."""
        if self._checking:
            return
        text = self.editor.toPlainText()
        run = ShowRun(text, self.path or "<show>", self.show_timeout)
        self._check_run, self._checking = run, True
        self.check_button.setText("Проверяю…")
        self.append_log("Проверка: запускаю код шоу")
        self.refresh()

        def work():
            try:
                result = ("ok", run.run(), text)
            except ShowLoadError as e:
                result = ("error", e, text)
            except Exception as e:      # a bug in the loader must not leave the button disabled
                result = ("error", ShowLoadError(f"Внутренняя ошибка проверки: {type(e).__name__}: {e}"), text)
            try:
                self._check_done.emit(run, result)
            except RuntimeError:        # the window is already gone
                pass
        threading.Thread(target=work, daemon=True).start()

    def _cancel_check(self):
        """Forget a running check and kill its worker process (new document, closing window)."""
        run, self._check_run = self._check_run, None
        if run is not None:
            run.cancel()
        if self._checking:
            self._checking = False
            self.check_button.setText("Проверить")

    def _on_check_done(self, run, result):
        if run is not self._check_run:      # cancelled or replaced: drop the result
            return
        self._check_run, self._checking = None, False
        self.check_button.setText("Проверить")
        kind, value, text = result
        self._apply_check(kind, value, text)
        self.check_finished.emit(not self.has_errors)

    def check(self):
        """Blocking variant of the check button for scripts and tests: starts the check and waits
        for it (the event loop keeps running). Returns True when there are no errors."""
        self.start_check()
        if self._checking:
            loop = QEventLoop(self)
            self.check_finished.connect(loop.quit)
            loop.exec()
            self.check_finished.disconnect(loop.quit)
        return not self.has_errors

    def _apply_check(self, kind, show, text):
        """Show the result of a finished check (on the GUI thread)."""
        self.problems = []
        if kind == "error":
            e = show
            self.show_obj = None
            self.problems = [("error", str(e), e.line, None)]
            self.last_report = f"Шоу не запустилось.\n{e}"
            self.has_errors = True
            self.preview.set_show(None)
            self.timeline.set_show(None)
            self._set_duration(0)
        else:
            self.show_obj = show
            findings = check_show(show, MIN_APPROACH_CM, max_height_cm=self.max_height_cm)
            self.problems = [(f.level, f.message, f.line, f.t) for f in findings]
            self.has_errors = any(f.level == "error" for f in findings)
            lines = [show.report(), "", "Проверки безопасности:" if findings else "Проверки безопасности: замечаний нет"]
            lines += [f"  {f}" for f in findings]
            self.last_report = "\n".join(lines)
            self.preview.set_show(show)
            self.timeline.set_show(show)
            self._set_duration(show.duration)
            self.drones_panel.set_roles(sorted(show.drones))
            self.project_label.setText(show.name)
        self.checked_text = text
        self.checked_limit = self.max_height_cm
        self.report_view.setPlainText(self.last_report)
        self._show_problems()
        self.tabs.setCurrentIndex(0 if self.problems else 1)
        self.append_log("Проверка: " + ("есть ошибки" if self.has_errors else "ошибок нет"))
        self.refresh()

    def _show_problems(self):
        self.problem_list.clear()
        marks = {"error": "✖ ", "warn": "▲ ", "info": "● "}
        for level, msg, line, t in self.problems:
            where = f"строка {line}: " if line else ""
            item = QListWidgetItem(f"{marks[level]}{where}{msg}")
            item.setData(Qt.ItemDataRole.UserRole, (line, t))
            color = {"error": "danger", "warn": "warn", "info": "text2"}[level]
            item.setForeground(theme.color(color))
            self.problem_list.addItem(item)
        if not self.problems and self.checked_text is not None:
            self.problem_list.addItem("Замечаний нет")
        self.editor.set_problems([(ln, lvl) for lvl, _, ln, _ in self.problems if lvl in ("error", "warn")])

    def _problem_activated(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        line, t = data
        if line:
            self.editor.go_to_line(line)
        if t is not None:
            self.slider.setValue(int(t * 10))

    # ---- preview time ------------------------------------------------------------

    def _set_duration(self, seconds):
        self.slider.setRange(0, int(round(seconds * 10)))
        self.slider.setValue(0)
        self._on_slider(0)

    def _on_slider(self, v):
        t = v / 10
        self.preview.set_time(t)
        self.timeline.set_time(t)
        total = self.slider.maximum() / 10
        self.time_label.setText(f"{t:.1f} / {total:.1f} с".replace(".", ","))

    def _seek(self, t):
        self.slider.setValue(int(round(t * 10)))

    def toggle_play(self):
        if self.playing:
            self.stop_play()
        elif self.slider.maximum() > 0:
            if self.slider.value() >= self.slider.maximum():
                self.slider.setValue(0)
            self.playing = True
            self.play_button.setText("Пауза")
            self._last_tick = time.monotonic()
            self.play_timer.start(33)

    def stop_play(self):
        self.playing = False
        self.play_timer.stop()
        self.play_button.setText("Играть")

    def _tick(self):
        now = time.monotonic()
        dt, self._last_tick = now - self._last_tick, now
        v = self.slider.value() + int(round(dt * 10 * self.speed.currentData()))
        if v >= self.slider.maximum():
            self.slider.setValue(self.slider.maximum())
            self.stop_play()
        else:
            self.slider.setValue(max(v, self.slider.value() + 1))

    # ---- drones: upload / start ---------------------------------------------------

    def _target(self):
        """(ip, show drone number) of the single included drone, else None."""
        inc = self.drones_panel.included()
        return inc[0] if len(inc) == 1 else None

    def _upload_block_reason(self):
        c = self.controller
        if c.busy or c.flying:
            return "Идёт загрузка или полёт"
        if self._checking:
            return "Идёт проверка шоу"
        if self.stack.currentIndex() != 1:
            return "Откройте шоу"
        if self.show_obj is None or self.dirty:
            return "Нажмите «Проверить»: код или лимит высоты изменились, либо шоу ещё не проверено"
        if self.has_errors:
            return "В проверках есть ошибки: исправьте их"
        if not c.connected:
            return "Нет связи с дронами: нажмите «Связь…»"
        inc = self.drones_panel.included()
        if not inc:
            return "Нет дронов в сети, включите питание"
        if len(inc) > 1:
            return "Несколько дронов и общий старт не проверялись на живых дронах: оставьте один дрон"
        if inc[0][1] not in (self.show_obj.drones if self.show_obj else {}):
            return "Выберите номер дрона из шоу в карточке"
        return self._position_block_reason(*inc[0])

    def _position_block_reason(self, ip, number):
        """Cell moves need a position fix and a drone standing near the first cell of the show."""
        first = next((s.args["cell"] for s in self.show_obj.drones[number].steps if s.kind == "code"), None)
        if first is None:
            return None
        v = self.controller.view(ip)
        return position_problem(first, v.x or 0, v.y or 0)

    def _start_block_reason(self):
        why = self._upload_block_reason()
        if why:
            return why
        ip, _ = self._target()
        if ip not in self.controller.loaded:
            return "Сначала нажмите «Загрузить»"
        if not self.controller.armed:
            return "Поставьте флажок «Взвести»"
        return None

    def refresh(self):
        c = self.controller
        flying = c.flying
        views = [c.view(ip) for ip in c.drone_ips()]
        self.drones_panel.update_drones(views, c.connected)
        self.preview.set_live(views, self.drones_panel.roles_by_ip())
        n_up = sum(1 for v in views if v.state != "Нет связи")
        self.link_label.setText(
            f'<span style="color:{theme.TOKENS["ok"]}">●</span> Дронов в сети: {n_up}' if c.connected
            else f'<span style="color:{theme.TOKENS["text2"]}">○</span> Симуляция')
        self.file_label.setText(self.title + (" *" if self.stack.currentIndex() == 1 and self.path is None else ""))
        self.setWindowTitle(f"{self.title} — Litebee IDE")
        in_ws = self.stack.currentIndex() == 1
        self.save_button.setEnabled(in_ws and not flying)
        self.check_button.setEnabled(in_ws and not flying and not self._checking)
        self.limit_spin.setEnabled(not flying)
        self.editor.setReadOnly(flying)
        why_up = self._upload_block_reason()
        self.upload_button.setEnabled(why_up is None)
        self.upload_button.setToolTip(why_up or "Отправить миссию дрону и сверить контрольную сумму")
        self.arm_box.setEnabled(c.connected and not flying)
        why_go = self._start_block_reason()
        self.start_button.setEnabled(why_go is None)
        self.start_button.setToolTip(why_go or "Запустить загруженную миссию")
        if self.arm_box.isChecked() != c.armed:
            self.arm_box.blockSignals(True)
            self.arm_box.setChecked(c.armed)
            self.arm_box.blockSignals(False)

    def _on_arm_toggled(self, on):
        self.controller.set_armed(on)
        self.refresh()

    def _on_armed_changed(self, on):
        self.refresh()

    def connect_dialog(self):
        dlg = ConnectDialog(self)
        if dlg.exec():
            self.connect_link(*dlg.values(), interactive=True)

    def connect_link(self, pc, drones, tcp, udp, interactive=False):
        """Start the link; returns False on a busy port or bad arguments."""
        while True:
            try:
                self.controller.connect_link(pc, drones, tcp, udp)
                self.append_log(f"Связь запущена на {pc}:{self.controller.link.tcp_port}")
                return True
            except OSError as e:
                msg = f"Порт занят. Закройте LiteBee Go и повторите ({e})"
            except ValueError as e:
                msg = f"Неверные параметры связи: {e}"
            self.append_log(msg)
            if not interactive:
                return False
            box = QMessageBox(self)
            box.setWindowTitle("Связь")
            box.setText(msg)
            retry = box.addButton("Повторить", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is not retry:
                return False

    def upload(self):
        why = self._upload_block_reason()
        if why:
            self.append_log(why)
            return
        ip, number = self._target()
        try:
            mission = drone_to_mission(self.show_obj.drones[number])
        except UploadUnsupported as e:
            self.append_log(f"Загрузка невозможна. {e}")
            self.problems.append(("info", f"Загрузка невозможна. {e}", None, None))
            self._show_problems()
            self.tabs.setCurrentIndex(0)
            return
        self.append_log(f"Дрон {ip}: загружаю миссию дрона шоу {number} ({len(mission.steps)} шагов, "
                        f"~{mission.total_seconds:.0f} с)")
        self.controller.upload(ip, mission)

    def start(self):
        why = self._start_block_reason()
        if why:
            self.append_log(why)
            return
        ip, number = self._target()
        mission = self.controller.loaded[ip]
        if not self.confirm_start([ip], mission):
            self.append_log("Старт отменён")
            return
        self.controller.start(ip)

    def start_summary(self, mission, ip=None):
        """Lines of the start dialog: checksum, height against the active limit, duration and,
        for cell moves, the cell the drone stands on and the first cell of the show."""
        lines = [f"Контрольная сумма миссии совпала ({mission.checksum})",
                 f"Высота до {mission.max_height_cm} см (лимит {self.max_height_cm} см), "
                 f"длительность ~{mission.total_seconds:.0f} с"]
        if mission.has_moves:
            v = self.controller.view(ip) if ip else None
            where = (f"клетке {v.cell}" if v and v.cell is not None else "неизвестной клетке")
            first = mission.moves[0].cell
            lines.append(f"Дрон на {where}, первое движение шоу к клетке {first}")
        return lines

    def _confirm_start_dialog(self, ips, mission):
        n = len(ips)
        flies = mission.can_fly
        checks = self.start_summary(mission, ips[0] if ips else None)
        box = QMessageBox(self)
        box.setWindowTitle("Старт")
        box.setText(("Дроны полетят: " if flies else "Миссия только со светодиодами: ") + ", ".join(ips))
        box.setInformativeText("\n".join(checks))
        go = box.addButton(f"{'Взлететь' if flies else 'Запустить'}, {ru_plural(n)}",
                           QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is go

    # ---- emergency -----------------------------------------------------------------

    def emergency(self):
        self.stop_play()
        self.controller.emergency()

    def _on_escape(self):
        if self.controller.armed or self.controller.flying:
            self.emergency()

    # ---- log -----------------------------------------------------------------------

    def append_log(self, msg):
        self.log_view.appendPlainText(f"{time.strftime('%H:%M:%S')}  {msg}")


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(argv)
    app.setStyleSheet(theme.stylesheet())
    cfg = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    os.makedirs(cfg, exist_ok=True)
    win = MainWindow(settings_path=os.path.join(cfg, "litebee_ide.ini"))
    if len(argv) > 1 and os.path.exists(argv[1]):
        win.open_file(argv[1])
    win.show()
    return app.exec()
