"""Loads app/theme.qss: the single place where colours are defined, plus the shared fonts."""
import os
import re

from PySide6.QtGui import QColor, QFont, QFontDatabase

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme.qss")


def _read():
    with open(_PATH, encoding="utf-8") as f:
        text = f.read()
    tokens = dict(re.findall(r"^@(\w+)\s+(#[0-9A-Fa-f]{6})\s*$", text, re.M))
    return text, tokens


_TEXT, TOKENS = _read()

# design names of the palette (docs/UI_DESIGN.md) -> token keys
NAMES = {"Tarmac": "bg", "Slate": "panel", "Carbon": "stage", "Grid": "grid", "Marker ink": "qr",
         "Chalk": "text", "Dust": "text2", "Beacon": "accent"}


def stylesheet() -> str:
    # longest names first so @on_accent is not clobbered by @accent
    css = _TEXT
    for name in sorted(TOKENS, key=len, reverse=True):
        css = re.sub(rf"@{name}\b(?!\s+#)", TOKENS[name], css)
    return css


def color(name: str) -> QColor:
    return QColor(TOKENS[name])


def alpha(name: str, a: int) -> QColor:
    """A token colour with alpha 0-255 (grid dimming, scrims)."""
    c = QColor(TOKENS[name])
    c.setAlpha(a)
    return c


# Fonts. Bahnschrift ships with Windows (variable DIN-like face with Cyrillic). Qt maps a variable
# font's weights to its named instances: Normal -> Regular, DemiBold -> SemiBold; there is no Medium
# instance, so emphasis is always DemiBold. Numbers that must align use Consolas.
UI_FAMILIES = ["Bahnschrift", "Segoe UI"]
MONO_FAMILIES = ["Consolas", "Cascadia Mono"]
EMPHASIS = QFont.Weight.DemiBold


def _first(candidates, fallback):
    have = set(QFontDatabase.families())
    return next((f for f in candidates if f in have), fallback)


def ui_family() -> str:
    return _first(UI_FAMILIES, "sans-serif")


def mono_family() -> str:
    return _first(MONO_FAMILIES, "monospace")


def ui_font(px: int, emphasis: bool = False) -> QFont:
    f = QFont(ui_family())
    f.setPixelSize(int(px))
    f.setWeight(EMPHASIS if emphasis else QFont.Weight.Normal)
    return f


def mono_font(px: int, emphasis: bool = False) -> QFont:
    f = QFont(mono_family())
    f.setPixelSize(int(px))
    f.setWeight(EMPHASIS if emphasis else QFont.Weight.Normal)
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def luminance(hex_color: str) -> float:
    v = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    v = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def readable(c: QColor, on: str = "stage", ratio: float = 3.0) -> QColor:
    """`c` darkened until it has at least `ratio` contrast against the token `on`: a white or yellow LED colour
    stays visible as a path or an outline on the light mat."""
    out = QColor(c)
    for _ in range(12):
        if contrast(out.name(), TOKENS[on]) >= ratio:
            break
        out = out.darker(115)
    return out


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio of two #RRGGBB colours."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)
