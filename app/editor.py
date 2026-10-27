"""Code editor: Python highlighting, line numbers, litebee API hints, problem underlines."""
import keyword
import re

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QPainter, QStandardItem, QStandardItemModel,
                           QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextFormat)
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QToolTip, QWidget

from litebee import reference

from . import theme

# name -> (signature as in code, one-line summary): read from litebee/reference.py, the single source
# of truth for the DSL (also shown by the "Справочник" panel).
API = {e.name: (e.signature, e.summary) for e in reference.drone_commands()}
TOP_LEVEL = {"Show": f"{reference.get('Show.Show').signature} — {reference.get('Show.Show').summary}",
             "show": "переменная шоу",
             "show.drone": f"{reference.get('Show.drone').signature} — {reference.get('Show.drone').summary}",
             "from litebee import Show": "импорт API"}


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)

        def fmt(name, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(theme.TOKENS[name]))
            if bold:
                f.setFontWeight(theme.EMPHASIS)
            f.setFontItalic(italic)
            return f

        self.rules = [
            (re.compile(r"\b(" + "|".join(keyword.kwlist) + r")\b"), fmt("text", bold=True)),
            (re.compile(r"\b(" + "|".join(API) + r")(?=\()"), fmt("syn_api")),
            (re.compile(r"\b\d+(\.\d+)?\b"), fmt("syn_num")),
        ]
        self.string = (re.compile(r"'[^'\n]*'?|\"[^\"\n]*\"?"), fmt("syn_str"))
        self.comment = (re.compile(r"#[^\n]*"), fmt("text2", italic=True))

    def highlightBlock(self, text):
        for rx, f in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), f)
        for rx, f in (self.string, self.comment):
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), f)


class _Numbers(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.number_width(), 0)

    def paintEvent(self, e):
        self.editor.paint_numbers(e)


class CodeEditor(QPlainTextEdit):
    """Plain editor; `set_problems` underlines lines, `go_to_line` jumps to one."""
    cursor_line_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("editor")
        self.setFont(theme.mono_font(13))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.highlighter = PythonHighlighter(self.document())
        self._numbers = _Numbers(self)
        self._problems = []
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._scroll_numbers)
        self.cursorPositionChanged.connect(self._refresh_selections)
        self._update_margin()
        self._setup_completer()
        self._refresh_selections()

    # ---- line numbers ------------------------------------------------------

    def number_width(self):
        digits = max(3, len(str(self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self, *_):
        self.setViewportMargins(self.number_width(), 0, 0, 0)

    def _scroll_numbers(self, rect, dy):
        if dy:
            self._numbers.scroll(0, dy)
        else:
            self._numbers.update(0, rect.y(), self._numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cr = self.contentsRect()
        self._numbers.setGeometry(QRect(cr.left(), cr.top(), self.number_width(), cr.height()))

    def paint_numbers(self, event):
        p = QPainter(self._numbers)
        p.fillRect(event.rect(), theme.color("panel"))
        block = self.firstVisibleBlock()
        n = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        bad = {ln for ln, _ in self._problems}
        p.setFont(self.font())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                p.setPen(theme.color("warn") if n + 1 in bad else theme.color("text2"))
                p.drawText(0, top, self._numbers.width() - 6, self.fontMetrics().height(),
                           Qt.AlignmentFlag.AlignRight, str(n + 1))
            block = block.next()
            top, bottom = bottom, bottom + round(self.blockBoundingRect(block).height())
            n += 1

    # ---- problems ----------------------------------------------------------

    def set_problems(self, problems):
        """problems: iterable of (line_number_1_based, 'error'|'warn')."""
        self._problems = [(ln, lvl) for ln, lvl in problems if ln]
        self._refresh_selections()
        self._numbers.update()

    def _refresh_selections(self):
        sels = []
        cur = QTextEdit.ExtraSelection()
        cur.format.setBackground(theme.color("card"))
        cur.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        cur.cursor = self.textCursor()
        cur.cursor.clearSelection()
        sels.append(cur)
        for ln, lvl in self._problems:
            block = self.document().findBlockByNumber(ln - 1)
            if not block.isValid():
                continue
            s = QTextEdit.ExtraSelection()
            c = QTextCursor(block)
            c.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
            s.cursor = c
            s.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
            s.format.setUnderlineColor(theme.color("danger" if lvl == "error" else "warn"))
            sels.append(s)
        self.setExtraSelections(sels)

    def go_to_line(self, line):
        block = self.document().findBlockByNumber(max(line - 1, 0))
        if block.isValid():
            c = QTextCursor(block)
            self.setTextCursor(c)
            self.centerCursor()
            self.setFocus()

    # ---- completion --------------------------------------------------------

    def _setup_completer(self):
        self._model = QStandardItemModel(self)
        for name, (sig, doc) in API.items():
            it = QStandardItem(f"{name}   {sig} — {doc}")
            it.setData(name, Qt.ItemDataRole.UserRole)
            self._model.appendRow(it)
        for name, doc in TOP_LEVEL.items():
            it = QStandardItem(f"{name}   {doc}")
            it.setData(name, Qt.ItemDataRole.UserRole)
            self._model.appendRow(it)
        self._completer = QCompleter(self._model, self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.activated[str].connect(self._insert_completion_text)

    def _word_under_cursor(self):
        c = self.textCursor()
        c.select(QTextCursor.SelectionType.WordUnderCursor)
        return c.selectedText()

    def word_at_cursor(self):
        """The identifier under the text cursor ('' when there is none)."""
        w = self._word_under_cursor()
        return w if re.fullmatch(r"\w+", w) else ""

    @staticmethod
    def reference_entry(word):
        """The reference entry a word names (a DSL method, `Show`), else None."""
        hits = reference.find(word)
        return hits[0] if hits and hits[0].dsl else None

    # ---- tooltips ----------------------------------------------------------

    def event(self, e):
        if e.type() == QEvent.Type.ToolTip:
            c = self.cursorForPosition(self.viewport().mapFromGlobal(e.globalPos()))
            c.select(QTextCursor.SelectionType.WordUnderCursor)
            entry = self.reference_entry(c.selectedText())
            if entry is not None:
                QToolTip.showText(e.globalPos(), reference.hint_html(entry, theme.TOKENS), self)
            else:
                QToolTip.hideText()
            return True
        return super().event(e)

    def _insert_completion_text(self, text):
        name = text.split()[0]
        c = self.textCursor()
        c.movePosition(QTextCursor.MoveOperation.StartOfWord, QTextCursor.MoveMode.KeepAnchor)
        c.removeSelectedText()
        c.insertText(name + ("(" if name in API else ""))
        self.setTextCursor(c)

    def keyPressEvent(self, e):
        popup = self._completer.popup()
        if popup.isVisible() and e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab,
                                             Qt.Key.Key_Escape, Qt.Key.Key_Backtab):
            e.ignore()          # the completer popup handles these
            return
        super().keyPressEvent(e)
        if self.isReadOnly():
            return
        if e.key() == Qt.Key.Key_Tab or not e.text():
            return
        word = self._word_under_cursor()
        if len(word) >= 2 and re.fullmatch(r"\w+", word):
            if word != self._completer.completionPrefix():
                self._completer.setCompletionPrefix(word)
                popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
            if self._completer.completionCount() > 0:
                rect = self.cursorRect()
                rect.setWidth(popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width())
                self._completer.complete(rect)
                return
        popup.hide()
