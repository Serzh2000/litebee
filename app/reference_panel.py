"""The "Справочник" dock: search, topic list, detail view with an example that can be inserted.

All content comes from litebee/reference.py; colours come from the theme tokens (app/theme.qss).
Install it on the main window with `ReferenceDock(window, editor, button)`: F1 toggles it (or, with
the editor focused on a DSL word, opens it at that function).
"""
from html import escape

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (QDockWidget, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                               QSplitter, QTextBrowser, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

from litebee import reference as ref

from . import theme
from .editor import PythonHighlighter

STATUS_KEY = {ref.STATUS_VERIFIED: "verified", ref.STATUS_SIM: "sim", ref.STATUS_HELPER: "helper",
              ref.STATUS_ABSENT: "absent"}
NO_EDITOR = "Откройте шоу или создайте новое, тогда пример можно вставить в редактор"
READ_ONLY = "Редактор только для чтения, пока дрон взведён или летит"
CONTEXT_NOTE = {"drone": "В примерах d — дрон: d = show.drone(1)",
                "show": "В примерах show — шоу: show = Show('имя')", "full": ""}
MONO = "'Consolas','Cascadia Mono'"


# ---- content -> HTML (pure functions, tested without a window) ----------------------------------

def _t():
    return theme.TOKENS


def _cell(text, mono=False, color=None, bold=False):
    t = _t()
    style = f"border-bottom: 1px solid {t['border']};"
    inner = escape(text)
    if mono:
        inner = f"<span style=\"font-family:{MONO}\">{inner}</span>"
    if color:
        inner = f"<span style=\"color:{t[color]}\">{inner}</span>"
    if bold:
        inner = f"<b>{inner}</b>"
    return f"<td style=\"{style}\" valign=\"top\">{inner}</td>"


def _th(text):
    t = _t()
    return (f"<th align=\"left\" style=\"color:{t['text2']}; border-bottom: 1px solid {t['border']};\">"
            f"{escape(text)}</th>")


def _table(header, rows, mono_cols=(), widths=None):
    out = ["<table width=\"100%\" cellspacing=\"0\" cellpadding=\"5\">",
           "<tr>" + "".join(_th(h) for h in header) + "</tr>"]
    for row in rows:
        out.append("<tr>" + "".join(_cell(c, mono=i in mono_cols) for i, c in enumerate(row)) + "</tr>")
    out.append("</table>")
    return "".join(out)


def _heading(text):
    return f"<p style=\"margin-top:12px; margin-bottom:2px; color:{_t()['text']}\"><b>{escape(text)}</b></p>"


def entry_html(entry):
    """Body of the detail view for a function: parameters, notes, command."""
    t = _t()
    parts = []
    if entry.params:
        parts.append(_heading("Параметры"))
        parts.append(_table(("Имя", "Единицы", "Что это"),
                            [(p.name, p.unit, p.text) for p in entry.params], mono_cols=(0,)))
    if entry.notes:
        parts.append(_heading("Примечания"))
        parts.append("<ul style=\"margin-top:2px; margin-left:6px; -qt-list-indent:0\">" + "".join(f"<li>{escape(n)}</li>" for n in entry.notes) + "</ul>")
    meta = []
    if entry.command:
        meta.append(f"Команда формации: {escape(entry.command_text)}")
    if entry.official:
        meta.append(f"в LiteBee Go: <span style=\"font-family:{MONO}\">{escape(entry.official)}</span>")
    if meta:
        parts.append(f"<p style=\"color:{t['text2']}; margin-top:10px\">{'. '.join(meta)}</p>")
    return "".join(parts) or f"<p style=\"color:{t['text2']}\">Без параметров</p>"


def article_html(article):
    """Body of the detail view for a topic page."""
    parts = []
    for s in article.sections:
        parts.append(_heading(s.heading))
        if s.style == "table":
            parts.append(_table(s.header, s.lines, mono_cols=(1, 2)))
        elif s.style in ("ul", "ol"):
            parts.append(f"<{s.style} style=\"margin-top:2px; margin-left:6px; -qt-list-indent:0\">"
                         + "".join(f"<li>{escape(x)}</li>" for x in s.lines) + f"</{s.style}>")
        else:
            parts.extend(f"<p style=\"margin-top:2px\">{escape(x)}</p>" for x in s.lines)
    return "".join(parts)


def item_html(item):
    return article_html(item) if item.article else entry_html(item)


# ---- inserting an example ----------------------------------------------------------------------

def insert_snippet(editor, text):
    """Insert `text` into a QPlainTextEdit at its cursor as one undo step.

    A blank current line is replaced by the snippet; on a line with code the snippet goes on a new
    line below it. Each line gets the indentation of the line it was inserted at."""
    cur = editor.textCursor()
    line = cur.block().text()
    indent = line[:len(line) - len(line.lstrip())]
    body = "\n".join((indent + ln) if ln.strip() else "" for ln in text.rstrip("\n").split("\n"))
    cur.beginEditBlock()
    if line.strip():
        cur.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        body = "\n" + body
    else:
        cur.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cur.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cur.removeSelectedText()
    cur.insertText(body)
    cur.endEditBlock()
    editor.setTextCursor(cur)
    editor.ensureCursorVisible()


# ---- the panel ---------------------------------------------------------------------------------

class ReferencePanel(QWidget):
    """Search box, grouped list and detail view. `insert_requested(text)` is emitted by the button."""
    insert_requested = Signal(str)
    selection_changed = Signal(str)          # key of the shown item

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("referencePanel")
        self._key = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Найти функцию или тему")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Поиск по справочнику")
        self.search.setToolTip("Ищет по названию и описанию. Стрелка вниз переходит к списку")
        self.search.textChanged.connect(self._refill)
        self.search.installEventFilter(self)
        lay.addWidget(self.search)

        self.split = QSplitter(Qt.Orientation.Vertical)
        self.split.setChildrenCollapsible(False)
        lay.addWidget(self.split, 1)

        # list
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        self.tree = QTreeWidget()
        self.tree.setObjectName("referenceTree")
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(0)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.setAccessibleName("Список функций и тем")
        self.tree.currentItemChanged.connect(self._on_current)
        tl.addWidget(self.tree)
        self.empty = QLabel("Ничего не найдено. Проверьте написание или очистите поиск")
        self.empty.setProperty("role", "secondary")
        self.empty.setWordWrap(True)
        self.empty.setMargin(8)
        self.empty.hide()
        tl.addWidget(self.empty)
        self.split.addWidget(top)

        # detail
        self.detail = QWidget()
        dl = QVBoxLayout(self.detail)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(6)
        self.title = QLabel()
        self.title.setObjectName("refTitle")
        self.title.setWordWrap(True)
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        dl.addWidget(self.title)
        badge_row = QHBoxLayout()
        self.badge = QLabel()
        self.badge.setObjectName("statusBadge")
        badge_row.addWidget(self.badge)
        badge_row.addStretch()
        dl.addLayout(badge_row)
        self.command = QLabel()
        self.command.setProperty("role", "secondary")
        self.command.setWordWrap(True)
        dl.addWidget(self.command)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        dl.addWidget(self.summary)
        self.body = QTextBrowser()
        self.body.setObjectName("referenceBody")
        self.body.setOpenLinks(False)
        self.body.setAccessibleName("Описание")
        dl.addWidget(self.body, 1)

        self.example_box = QWidget()
        el = QVBoxLayout(self.example_box)
        el.setContentsMargins(0, 0, 0, 0)
        el.setSpacing(4)
        cap = QLabel("Пример")
        cap.setProperty("role", "secondary")
        el.addWidget(cap)
        self.example = QPlainTextEdit()
        self.example.setObjectName("referenceExample")
        self.example.setReadOnly(True)
        self.example.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.example.setAccessibleName("Пример кода")
        self.example.setFont(self._mono())
        self._highlighter = PythonHighlighter(self.example.document())
        el.addWidget(self.example)
        self.context_note = QLabel()
        self.context_note.setProperty("role", "secondary")
        self.context_note.setWordWrap(True)
        el.addWidget(self.context_note)
        row = QHBoxLayout()
        self.insert_button = QPushButton("Вставить в редактор")
        self.insert_button.setAccessibleName("Вставить пример в редактор")
        self.insert_button.clicked.connect(self._on_insert)
        row.addWidget(self.insert_button)
        row.addStretch()
        el.addLayout(row)
        self.insert_reason = QLabel()
        self.insert_reason.setProperty("role", "secondary")
        self.insert_reason.setWordWrap(True)
        el.addWidget(self.insert_reason)
        dl.addWidget(self.example_box)
        self.split.addWidget(self.detail)
        self.split.setStretchFactor(0, 2)
        self.split.setStretchFactor(1, 3)
        self.split.setSizes([140, 460])

        self._insert_reason = ""
        self.setTabOrder(self.search, self.tree)
        self.setTabOrder(self.tree, self.body)
        self._refill()

    @staticmethod
    def _mono(size=12):
        return theme.mono_font(size)

    # ---- list ----

    def eventFilter(self, obj, e):
        if obj is self.search and e.type() == QEvent.Type.KeyPress:
            if e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.tree.isVisible():
                self.tree.setFocus()
                return True
        return super().eventFilter(obj, e)

    def _refill(self, *_):
        found = ref.search(self.search.text())
        keep = self._key
        self.tree.blockSignals(True)
        self.tree.clear()
        header_font = QFont(self.tree.font())
        header_font.setWeight(theme.EMPHASIS)
        first_leaf, wanted = None, None
        for tid, ttitle in ref.TOPICS:
            group = [it for it in found if it.topic == tid]
            if not group:
                continue
            head = QTreeWidgetItem([ttitle])
            head.setFlags(Qt.ItemFlag.NoItemFlags)                 # not selectable: keyboard skips it
            head.setFont(0, header_font)
            head.setForeground(0, theme.color("text2"))
            self.tree.addTopLevelItem(head)
            head.setFirstColumnSpanned(True)
            for it in group:
                label = f"{it.icon} {it.label}" if it.icon else it.label
                leaf = QTreeWidgetItem([label])
                leaf.setData(0, Qt.ItemDataRole.UserRole, it.key)
                leaf.setToolTip(0, f"{it.summary}\n{it.icon} {it.status}" if it.status else it.summary)
                self.tree.addTopLevelItem(leaf)
                first_leaf = first_leaf or leaf
                if it.key == keep:
                    wanted = leaf
        self.tree.blockSignals(False)
        has = first_leaf is not None
        self.tree.setVisible(has)
        self.empty.setVisible(not has)
        if has:
            self.tree.setCurrentItem(wanted or first_leaf)
            self.show_item(ref.get(self.tree.currentItem().data(0, Qt.ItemDataRole.UserRole)))
        else:
            self._key = None
            self._show_nothing()

    def _on_current(self, cur, _prev):
        key = cur.data(0, Qt.ItemDataRole.UserRole) if cur else None
        if key and key != self._key:
            self.show_item(ref.get(key))

    def _show_nothing(self):
        for w in (self.title, self.badge, self.command, self.summary, self.example_box):
            w.hide()
        self.body.setHtml(f"<p style=\"color:{_t()['text2']}\">Нет совпадений</p>")

    # ---- detail ----

    def show_item(self, item):
        if item is None:
            return
        self._key = item.key
        article = item.article
        self.title.setText(item.title if article else item.signature)
        self.title.setFont(self._mono(14) if not article else self.font())
        self.title.setStyleSheet("font-weight: 600; font-size: 15px;" if article else "")
        self.title.show()
        self.badge.setVisible(not article)
        self.command.setVisible(not article)
        if not article:
            self.badge.setText(f"{item.icon} {item.status}")
            self.badge.setProperty("status", STATUS_KEY[item.status])
            self.badge.setToolTip(ref.STATUS_HINT[item.status])
            self.badge.style().unpolish(self.badge)
            self.badge.style().polish(self.badge)
            self.command.setText(f"Команда формации: {item.command_text}" if item.command
                                 else ("Свойство" if item.kind == "property" else "Не команда дрона"))
        self.summary.setText(item.summary)
        self.summary.show()
        self.body.setHtml(item_html(item))
        self.body.verticalScrollBar().setValue(0)
        has_example = bool(item.example)
        self.example_box.setVisible(has_example)
        if has_example:
            self.example.setPlainText(item.example.rstrip("\n"))
            lines = min(self.example.document().blockCount(), 8)
            self.example.setFixedHeight(lines * self.example.fontMetrics().lineSpacing() + 34)
            self.context_note.setText(CONTEXT_NOTE[item.context])
            self.context_note.setVisible(bool(CONTEXT_NOTE[item.context]))
        self.selection_changed.emit(item.key)
        self._apply_insert_state()

    def show_key(self, key):
        """Select the item with this key; the search is cleared when it hides the item."""
        if ref.get(key) is None:
            return False
        if self.search.text() and ref.get(key) not in ref.search(self.search.text()):
            self.search.clear()
        self._key = None
        for i in range(self.tree.topLevelItemCount()):
            leaf = self.tree.topLevelItem(i)
            if leaf.data(0, Qt.ItemDataRole.UserRole) == key:
                self.tree.setCurrentItem(leaf)
                self.tree.scrollToItem(leaf)
                self.show_item(ref.get(key))
                return True
        return False

    @property
    def current_key(self):
        return self._key

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    # ---- insert ----

    def set_insert_reason(self, reason):
        """'' when inserting is possible, else why not (shown under the button and as its tooltip)."""
        self._insert_reason = reason
        self._apply_insert_state()

    def _apply_insert_state(self):
        ok = not self._insert_reason
        self.insert_button.setEnabled(ok)
        self.insert_button.setToolTip("Вставляет пример в редактор под курсором" if ok else self._insert_reason)
        self.insert_reason.setText(self._insert_reason)
        self.insert_reason.setVisible(bool(self._insert_reason) and self.example_box.isVisibleTo(self))

    def _on_insert(self):
        item = ref.get(self._key) if self._key else None
        if item is not None and item.example and self.insert_button.isEnabled():
            self.insert_requested.emit(item.example)


class _TitleBar(QWidget):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 0, 0, 4)
        name = QLabel("Справочник")
        name.setObjectName("projectName")
        hint = QLabel("F1")
        hint.setProperty("role", "secondary")
        self.close_button = QToolButton()
        self.close_button.setObjectName("refClose")
        self.close_button.setText("Закрыть")
        self.close_button.setToolTip("Закрыть справочник (F1)")
        self.close_button.setAccessibleName("Закрыть справочник")
        self.close_button.clicked.connect(self.closed)
        lay.addWidget(name)
        lay.addWidget(hint)
        lay.addStretch()
        lay.addWidget(self.close_button)


class ReferenceDock(QDockWidget):
    """Right-hand dock with the reference. F1 toggles it, or opens it at the DSL word under the editor cursor."""

    def __init__(self, window, editor, button=None, width=380, document_open=None, reveal_editor=None):
        """`document_open()` says whether a show is open (default: the editor is visible); `reveal_editor()` brings
        the editor into view (the code column and its tab) before an example is inserted."""
        super().__init__("Справочник", window)
        self.setObjectName("referenceDock")
        self.editor, self.button, self.window_ = editor, button, window
        self._document_open = document_open or editor.isVisible
        self._reveal_editor = reveal_editor
        self._width, self._grown = width, 0
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.panel = ReferencePanel()
        frame = QWidget()
        frame.setObjectName("referenceFrame")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 10, 12, 10)
        self.title_bar = _TitleBar()
        self.title_bar.closed.connect(self.toggle)
        fl.addWidget(self.title_bar)
        fl.addWidget(self.panel, 1)
        self.setWidget(frame)
        self.setTitleBarWidget(QWidget())               # our own header is inside the frame
        self.titleBarWidget().setFixedHeight(0)
        self.setMinimumWidth(340)
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self)
        window.resizeDocks([self], [width], Qt.Orientation.Horizontal)
        self.hide()
        self.panel.insert_requested.connect(self.insert)
        self.visibilityChanged.connect(self._sync_button)
        if button is not None:
            button.setCheckable(True)
            button.setToolTip("Справочник функций (F1)")
            button.setAccessibleName("Справочник функций")
            button.clicked.connect(self._on_button)
        self._shortcut = QShortcut(QKeySequence(Qt.Key.Key_F1), window, activated=self.on_f1)
        self._watch = _EditorWatch(self)
        editor.installEventFilter(self._watch)
        self.refresh_insert_state()

    # ---- showing ----

    def _sync_button(self, _visible=None):
        try:
            shown = not self.isHidden()
            if self.button is not None and self.button.isChecked() != shown:
                self.button.setChecked(shown)
        except RuntimeError:            # the window is being destroyed
            pass

    def _on_button(self, checked):
        if checked:
            self.open()
        else:
            self.close_panel()

    def _screen_width(self):
        w = self.window_
        return w.screen().availableGeometry().width() if w.screen() else w.width()

    def _make_room(self):
        """Grow the window by the dock width (as far as the screen allows) so the editor and preview keep their size."""
        w = self.window_
        if self._grown or w.isMaximized() or w.isFullScreen() or not w.isVisible():
            return
        self._grown = max(0, min(w.width() + self._width + 6, self._screen_width()) - w.width())
        if self._grown:
            w.resize(w.width() + self._grown, w.height())

    def _give_back_room(self):
        w, grown, self._grown = self.window_, self._grown, 0
        if grown and not (w.isMaximized() or w.isFullScreen()):
            w.resize(w.width() - grown, w.height())

    def open(self, key=None):
        self._make_room()
        self.show()
        self.window_.resizeDocks([self], [self._width], Qt.Orientation.Horizontal)
        if key:
            self.panel.show_key(key)
        self.refresh_insert_state()
        if key:
            self.panel.tree.setFocus()
        else:
            self.panel.focus_search()

    def close_panel(self):
        had_focus = self.isAncestorOf(self.window_.focusWidget()) if self.window_.focusWidget() else False
        self.hide()
        self._give_back_room()
        if had_focus and self.editor.isVisible():
            self.editor.setFocus()

    def toggle(self):
        if self.isHidden():
            self.open()
        else:
            self.close_panel()

    def on_f1(self):
        """F1 on a DSL word in the editor opens the reference at it; otherwise toggles the panel."""
        if self.editor.hasFocus():
            entry = self.editor.reference_entry(self.editor.word_at_cursor())
            if entry is not None:
                self.open(entry.key)
                return
        self.toggle()

    # ---- inserting ----

    def insert_problem(self):
        if not self._document_open():
            return NO_EDITOR
        if self.editor.isReadOnly():
            return READ_ONLY
        return ""

    def refresh_insert_state(self):
        self.panel.set_insert_reason(self.insert_problem())

    def insert(self, text):
        self.refresh_insert_state()
        if self.insert_problem():
            return False
        if self._reveal_editor is not None:
            self._reveal_editor()
        insert_snippet(self.editor, text)
        self.editor.setFocus()
        return True


class _EditorWatch(QObject):
    """Keeps the insert button in step with the editor: shown/hidden (no document) and read-only (flight)."""

    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock

    def eventFilter(self, obj, e):
        if e.type() in (QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.ReadOnlyChange):
            try:
                self.dock.refresh_insert_state()
            except RuntimeError:        # the window is being destroyed
                pass
        return False
