"""Pre-flight sequence: the four step buttons as a numbered chain with a state word under each step and the
reason the next step is not possible on the right (docs/UI_DESIGN.md, "Порядок подготовки к полёту").

The buttons stay the window's own (`check_button`, `upload_button`, `arm_box`, `start_button`); this widget only
lays them out and sets their `step` property and icon. State is always a shape and a word, never only colour."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import theme

ICON_PX = 16
STATES = ("done", "current", "next", "blocked")


def step_icon(state, number, error=False) -> QIcon:
    """A 16 px badge: a check for a done step, '!' for a current step with errors, the step number otherwise."""
    dpr = 2
    pm = QPixmap(ICON_PX * dpr, ICON_PX * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(1, 1, ICON_PX - 2, ICON_PX - 2)
    if state == "done":
        ink = theme.color("ok")
    elif state == "current":
        ink = theme.color("on_accent")
    elif state == "next":
        ink = theme.color("accent")
    else:
        ink = theme.color("text2")
    pen = QPen(ink, 1.3)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(r)
    if state == "done":
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setWidthF(1.6)
        p.setPen(pen)
        p.drawPolyline([QPointF(4.6, 8.4), QPointF(7.0, 10.8), QPointF(11.6, 5.6)])
    else:
        f = QFont(theme.ui_family())
        f.setPixelSize(10)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, "!" if (error and state == "current") else str(number))
    p.end()
    return QIcon(pm)


def _repolish(w):
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


class PreflightStrip(QWidget):
    """The chain 1 - 2 - 3 - 4 with a word under every step and the reason text at the right."""

    def __init__(self, buttons, parent=None):
        super().__init__(parent)
        self.buttons = list(buttons)
        self.words = []
        self.states = []
        self.reason = ""
        self.setObjectName("preflightStrip")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        for i, b in enumerate(self.buttons):
            if i:
                bar = QLabel("—")
                bar.setProperty("role", "secondary")
                bar.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
                bar.setFixedHeight(b.sizeHint().height())
                lay.addWidget(bar)
            col = QVBoxLayout()
            col.setSpacing(2)
            col.setContentsMargins(0, 0, 0, 0)
            word = QLabel("")
            word.setObjectName("stepWord")
            word.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            b.setIconSize(QSize(ICON_PX, ICON_PX))
            col.addWidget(b)
            col.addWidget(word)
            lay.addLayout(col)
            self.words.append(word)
        self.reason_label = QLabel("")
        self.reason_label.setObjectName("reason")
        self.reason_label.setWordWrap(True)
        self.reason_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.reason_label.setMinimumWidth(180)
        lay.addSpacing(10)
        lay.addWidget(self.reason_label, 1)
        self.set_states([("blocked", "позже")] * len(self.buttons), "")

    def set_states(self, states, reason=""):
        """`states`: [(state, word[, error])] for each button; `reason`: why the next step is not possible."""
        self.states = list(states)
        self.reason = reason or ""
        for i, (b, w, st) in enumerate(zip(self.buttons, self.words, self.states)):
            state, word = st[0], st[1]
            error = bool(st[2]) if len(st) > 2 else False
            if state not in STATES:
                raise ValueError(f"unknown step state {state!r}")
            b.setProperty("step", state)
            b.setIcon(step_icon(state, i + 1, error))
            w.setText(word)
            w.setProperty("state", state)
            w.setProperty("error", "true" if error else "false")
            b.setAccessibleDescription(f"Шаг {i + 1} из {len(self.buttons)}: {word}")
            _repolish(b)
            _repolish(w)
        self.reason_label.setText(self.reason)
        self.reason_label.setToolTip(self.reason)

    def state_of(self, i):
        return self.states[i][0]

    def word_of(self, i):
        return self.states[i][1]
