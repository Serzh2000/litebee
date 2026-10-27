"""Loads app/theme.qss: the single place where colours are defined."""
import os
import re

from PySide6.QtGui import QColor

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme.qss")


def _read():
    with open(_PATH, encoding="utf-8") as f:
        text = f.read()
    tokens = dict(re.findall(r"^@(\w+)\s+(#[0-9A-Fa-f]{6})\s*$", text, re.M))
    return text, tokens


_TEXT, TOKENS = _read()


def stylesheet() -> str:
    # longest names first so @on_accent is not clobbered by @accent
    css = _TEXT
    for name in sorted(TOKENS, key=len, reverse=True):
        css = re.sub(rf"@{name}\b(?!\s+#)", TOKENS[name], css)
    return css


def color(name: str) -> QColor:
    return QColor(TOKENS[name])


MONO_FAMILIES = ["Cascadia Mono", "Consolas"]
