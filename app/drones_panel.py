"""Drone cards: role number, IP, battery bar, height, state, and an include checkbox."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout,
                               QWidget)

from litebee.safety import MIN_VOLTS, WARN_VOLTS

from . import theme
from .drone_art import DroneIcon
from .session import (ARMED, ERROR, FLYING, LANDING, LOADED, NO_LINK, READY, DroneView)

STATE_COLOR = {NO_LINK: "text2", READY: "ok", LOADED: "accent", ARMED: "warn", FLYING: "accent",
               LANDING: "warn", ERROR: "danger"}
STATE_GLYPH = {NO_LINK: "○", READY: "●", LOADED: "◆", ARMED: "▲", FLYING: "▶", LANDING: "▼", ERROR: "✖"}


def fmt_volts(v):
    return "—" if v is None else f"{v:.1f}".replace(".", ",") + " В"


def cell_text(v):
    """Where the drone stands on the mat, from its telemetry."""
    if not v.has_fix:
        return "Нет позиции"
    return f"Клетка {v.cell}" if v.cell is not None else "Вне коврика"


class BatteryBar(QWidget):
    """Thin bar: red below 7.0 V, amber below 7.4 V, green otherwise (4.2 V*2 cell = 8.4 V full)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.volts = None
        self.setFixedHeight(8)

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
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.color("border"))
        p.drawRoundedRect(r, 4, 4)
        if self.volts is not None:
            frac = min(max((self.volts - 6.0) / (8.4 - 6.0), 0.05), 1.0)
            p.setBrush(theme.color(self.level_color()))
            p.drawRoundedRect(r.adjusted(0, 0, -int(r.width() * (1 - frac)), 0), 4, 4)


class DroneCard(QFrame):
    include_changed = Signal(str, bool)
    role_changed = Signal(str, int)

    def __init__(self, ip, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.setObjectName("card")
        self.setFixedWidth(210)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)
        top = QHBoxLayout()
        self.icon = DroneIcon(30)
        top.addWidget(self.icon)
        self.role = QComboBox()
        self.role.setAccessibleName(f"Номер дрона в шоу для {ip}")
        self.role.setToolTip("Какой дрон шоу выполняет эта машина")
        self.role.currentIndexChanged.connect(lambda _: self.role_changed.emit(self.ip, self.role_number()))
        top.addWidget(QLabel("Дрон"))
        top.addWidget(self.role)
        top.addStretch()
        self.state = QLabel()
        top.addWidget(self.state)
        lay.addLayout(top)
        where = QHBoxLayout()
        self.ip_label = QLabel(ip)
        self.ip_label.setProperty("role", "mono")
        self.cell = QLabel("Нет позиции")
        self.cell.setProperty("role", "secondary")
        self.cell.setToolTip("Клетка коврика под дроном по телеметрии. Без позиции дрон не выполнит движение по клеткам: "
                             "поставьте его на коврик и сделайте короткий взлёт на 50 см")
        where.addWidget(self.ip_label)
        where.addStretch()
        where.addWidget(self.cell)
        lay.addLayout(where)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.bar = BatteryBar()
        self.volts = QLabel("—")
        self.height = QLabel("— см")
        self.height.setProperty("role", "secondary")
        row.addWidget(self.bar, 1)
        row.addWidget(self.volts)
        row.addWidget(self.height)
        lay.addLayout(row)
        self.include = QCheckBox("Участвует в полёте")
        self.include.setChecked(True)
        self.include.toggled.connect(lambda c: self.include_changed.emit(self.ip, c))
        lay.addWidget(self.include)

    def role_number(self):
        return self.role.currentData() or 0

    def set_roles(self, numbers, current=None):
        self.role.blockSignals(True)
        self.role.clear()
        for n in numbers:
            self.role.addItem(str(n), n)
        if current in numbers:
            self.role.setCurrentIndex(numbers.index(current))
        self.role.blockSignals(False)

    def update_view(self, v: DroneView):
        color = theme.TOKENS[STATE_COLOR[v.state]]
        self.state.setText(f'<span style="color:{color}">{STATE_GLYPH[v.state]}</span> {v.state}')
        self.icon.set_led(None if v.state == NO_LINK else STATE_COLOR[v.state])      # the LED mirrors the state
        self.volts.setText(fmt_volts(v.volts))
        self.height.setText("— см" if v.z is None else f"{v.z} см")
        self.bar.set_volts(v.volts)
        self.cell.setText(cell_text(v))
        self.setAccessibleName(f"Дрон {self.ip}: {v.state}, батарея {fmt_volts(v.volts)}, {cell_text(v).lower()}")


class DronesPanel(QWidget):
    selection_changed = Signal()

    EMPTY = "Ждём дроны. Включите питание"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = {}
        self.roles = []
        self.simulation_text = "Дронов нет: симуляция и проверки работают, полёта нет"
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.empty = QLabel(self.simulation_text)
        self.empty.setProperty("role", "secondary")
        self.empty.setWordWrap(True)
        outer.addWidget(self.empty)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        holder.setObjectName("cards")
        self.row = QHBoxLayout(holder)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(8)
        self.row.addStretch()
        self.scroll.setWidget(holder)
        outer.addWidget(self.scroll)
        self.scroll.hide()

    def set_roles(self, numbers):
        self.roles = list(numbers)
        for c in self.cards.values():
            c.set_roles(self.roles, c.role_number())

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
                card.role_changed.connect(lambda *_: self.selection_changed.emit())
                self.cards[v.ip] = card
                self.row.insertWidget(self.row.count() - 1, card)
                self.selection_changed.emit()
            card.update_view(v)
        has = bool(self.cards)
        self.scroll.setVisible(has)
        self.empty.setVisible(not has)
        self.empty.setText(self.EMPTY if link_up else self.simulation_text)

    def roles_by_ip(self):
        """{ip: show drone number chosen on the card}, for the labels on the mat map."""
        return {ip: c.role_number() for ip, c in self.cards.items()}

    def included(self):
        """[(ip, show drone number)] of cards that are ticked."""
        return [(ip, c.role_number()) for ip, c in self.cards.items() if c.include.isChecked()]
