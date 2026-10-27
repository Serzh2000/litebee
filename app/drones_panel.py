"""Fleet rail: one compact chip per connected drone (icon, show drone number, IP, cell, battery, state, participation)."""
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

from litebee.safety import MIN_VOLTS, WARN_VOLTS

from . import theme
from .drone_art import DroneIcon
from .session import (ARMED, ERROR, FLYING, LANDING, LOADED, NO_LINK, READY, DroneView)

# colour of the state word and of the LED on the little drone icon; the word always comes with a glyph
STATE_COLOR = {NO_LINK: "text2", READY: "ok", LOADED: "text", ARMED: "warn", FLYING: "text",
               LANDING: "warn", ERROR: "danger"}
STATE_LED = {READY: "ok", LOADED: "accent", ARMED: "warn", FLYING: "accent", LANDING: "warn", ERROR: "danger"}
STATE_GLYPH = {NO_LINK: "○", READY: "●", LOADED: "◆", ARMED: "▲", FLYING: "▶", LANDING: "▼", ERROR: "✖"}
CHIP_H = 34


def fmt_volts(v):
    return "—" if v is None else f"{v:.1f}".replace(".", ",") + " В"


def cell_text(v):
    """Where the drone stands on the mat, from its telemetry."""
    if not v.has_fix:
        return "Нет позиции"
    return f"Клетка {v.cell}" if v.cell is not None else "Вне коврика"


class Toggle(QCheckBox):
    """A small switch with a label: the knob sits on the right when on, on the left when off (position, not colour alone)."""
    TRACK_W, TRACK_H, GAP = 26, 14, 7

    def sizeHint(self):
        fm = self.fontMetrics()
        return QSize(self.TRACK_W + self.GAP + fm.horizontalAdvance(self.text()) + 2, max(self.TRACK_H + 6, fm.height() + 4))

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = (self.height() - self.TRACK_H) / 2
        track = QRectF(1, y, self.TRACK_W - 2, self.TRACK_H)
        on, enabled = self.isChecked(), self.isEnabled()
        ink = theme.color("accent") if on and enabled else theme.color("text2")
        p.setPen(QPen(ink, 1.3))
        p.setBrush(theme.color("accent") if on and enabled else Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(track, self.TRACK_H / 2, self.TRACK_H / 2)
        r = self.TRACK_H - 6
        kx = track.right() - 3 - r if on else track.left() + 3
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.color("on_accent") if on and enabled else theme.color("text2"))
        p.drawEllipse(QRectF(kx, y + 3, r, r))
        p.setPen(theme.color("text") if enabled else theme.color("text2"))
        p.setFont(self.font())
        p.drawText(QRectF(self.TRACK_W + self.GAP, 0, self.width() - self.TRACK_W - self.GAP, self.height()),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        if self.hasFocus():
            p.setPen(QPen(theme.color("accent"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()).adjusted(1, 1, -1, -1), 4, 4)


class BatteryBar(QWidget):
    """Thin bar: red below 7.0 V, amber below 7.4 V, green otherwise (4.2 V*2 cell = 8.4 V full)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.volts = None
        self.setFixedSize(40, 6)

    def set_volts(self, v):
        self.volts = v
        self.update()

    def level_color(self):
        v = self.volts
        if v is None:
            return "text2"
        return "danger" if v < MIN_VOLTS else "warn" if v < WARN_VOLTS else "ok"

    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.color("border"))
        p.drawRect(r)
        if self.volts is not None:
            frac = min(max((self.volts - 6.0) / (8.4 - 6.0), 0.05), 1.0)
            p.setBrush(theme.color(self.level_color()))
            p.drawRect(r.adjusted(0, 0, -int(r.width() * (1 - frac)), 0))


class DroneCard(QFrame):
    """One chip of the rail. Clicking it focuses the show drone it flies as."""
    include_changed = Signal(str, bool)
    role_changed = Signal(str, int)
    clicked = Signal(str)               # ip

    def __init__(self, ip, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.setObjectName("chip")
        self.setFixedHeight(CHIP_H)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(8)
        self.icon = DroneIcon(26)
        lay.addWidget(self.icon)
        self.role = QComboBox()
        self.role.setAccessibleName(f"Номер дрона в шоу для {ip}")
        self.role.setToolTip("Какой дрон шоу выполняет эта машина")
        self.role.setMinimumContentsLength(2)
        self.role.currentIndexChanged.connect(lambda _: self.role_changed.emit(self.ip, self.role_number()))
        lay.addWidget(self.role)
        self.ip_label = QLabel(ip)
        self.ip_label.setProperty("role", "mono")
        lay.addWidget(self.ip_label)
        self.cell = QLabel("Нет позиции")
        self.cell.setProperty("role", "secondary")
        self.cell.setToolTip("Клетка коврика под дроном по телеметрии. Без позиции дрон не выполнит движение по клеткам: "
                             "поставьте его на коврик и сделайте короткий взлёт на 50 см")
        lay.addWidget(self.cell)
        self.bar = BatteryBar()
        self.volts = QLabel("—")
        self.volts.setProperty("role", "mono")
        lay.addWidget(self.bar)
        lay.addWidget(self.volts)
        self.state = QLabel()
        lay.addWidget(self.state)
        self.include = Toggle("в полёте")
        self.include.setAccessibleName("Дрон участвует в полёте")
        self.include.setToolTip("Снимите флажок, если этот дрон не должен лететь")
        self.include.setChecked(True)
        self.include.toggled.connect(lambda c: self.include_changed.emit(self.ip, c))
        lay.addWidget(self.include)

    def role_number(self):
        return self.role.currentData() or 0

    def set_roles(self, numbers, current=None):
        self.role.blockSignals(True)
        self.role.clear()
        for n in numbers:
            self.role.addItem(f"Дрон {n}", n)
        if current in numbers:
            self.role.setCurrentIndex(numbers.index(current))
        self.role.blockSignals(False)

    def set_selected(self, on):
        if bool(self.property("selected")) != on:
            self.setProperty("selected", on)
            self.style().unpolish(self)
            self.style().polish(self)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.ip)

    def update_view(self, v: DroneView):
        color = theme.TOKENS[STATE_COLOR[v.state]]
        self.state.setText(f'<span style="color:{color}">{STATE_GLYPH[v.state]}</span> {v.state}')
        self.icon.set_led(STATE_LED.get(v.state))                # the LED mirrors the state; no LED without a link
        low = v.volts is not None and v.volts < WARN_VOLTS
        self.volts.setText(("▲ " if low else "") + fmt_volts(v.volts))
        self.volts.setToolTip("Батарея ниже 7,4 В: лучше заменить" if low else "")
        self.bar.set_volts(v.volts)
        self.cell.setText(cell_text(v))
        self.setAccessibleName(f"Дрон {self.ip}: {v.state}, батарея {fmt_volts(v.volts)}, {cell_text(v).lower()}")


class DronesPanel(QWidget):
    selection_changed = Signal()
    drone_clicked = Signal(object)        # show drone number of the clicked chip

    EMPTY = "Ждём дроны. Включите питание"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = {}
        self.roles = []
        self.focus = None
        self.simulation_text = "Дронов нет: симуляция и проверки работают, полёта нет"
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.empty = QLabel(self.simulation_text)
        self.empty.setProperty("role", "secondary")
        self.empty.setContentsMargins(2, 0, 0, 0)
        outer.addWidget(self.empty, 0, Qt.AlignmentFlag.AlignVCenter)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        holder.setObjectName("cards")
        self.row = QHBoxLayout(holder)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(0)
        self.row.addStretch()
        self.scroll.setWidget(holder)
        outer.addWidget(self.scroll)
        self.scroll.hide()
        self.setMinimumHeight(CHIP_H + 8)

    def set_roles(self, numbers):
        self.roles = list(numbers)
        for c in self.cards.values():
            c.set_roles(self.roles, c.role_number())
        self._mark_selected()

    def update_drones(self, views, link_up: bool):
        ips = [v.ip for v in views]
        for ip in list(self.cards):
            if ip not in ips and not link_up:
                self.cards.pop(ip).deleteLater()
        for v in views:
            card = self.cards.get(v.ip)
            if card is None:
                card = DroneCard(v.ip)
                card.set_roles(self.roles, self.roles[len(self.cards)] if len(self.cards) < len(self.roles) else None)
                card.include_changed.connect(lambda *_: self.selection_changed.emit())
                card.role_changed.connect(lambda *_: (self._mark_selected(), self.selection_changed.emit()))
                card.clicked.connect(self._on_chip_clicked)
                self.cards[v.ip] = card
                self.row.insertWidget(self.row.count() - 1, card)
                self.selection_changed.emit()
            card.update_view(v)
        has = bool(self.cards)
        self.scroll.setVisible(has)
        self.empty.setVisible(not has)
        self.empty.setText(self.EMPTY if link_up else self.simulation_text)
        self._mark_selected()

    # ---- focus mode ------------------------------------------------------------------------------

    def set_focus(self, n):
        self.focus = n
        self._mark_selected()

    def _mark_selected(self):
        for c in self.cards.values():
            c.set_selected(self.focus is not None and c.role_number() == self.focus)

    def _on_chip_clicked(self, ip):
        n = self.cards[ip].role_number() if ip in self.cards else 0
        if n:
            self.drone_clicked.emit(None if n == self.focus else n)

    def roles_by_ip(self):
        """{ip: show drone number chosen on the card}, for the labels on the mat map."""
        return {ip: c.role_number() for ip, c in self.cards.items()}

    def included(self):
        """[(ip, show drone number)] of cards that are ticked."""
        return [(ip, c.role_number()) for ip, c in self.cards.items() if c.include.isChecked()]
