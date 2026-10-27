"""Import LiteBee Go .lbg projects (a zip with a Scratch 3 project.json).

Ported from lbg_to_py.py. The project is first walked into a neutral list of
calls (validated numbers only, so a hostile .lbg cannot inject code), which is
then either rendered as Python source or applied to a Show directly.
"""
import json
import re
import zipfile
from typing import Any, List, Tuple

from .mission import COLORS
from .show import Show

PREFIX = "litebeeWingFormation_"
# drone 1 starts on the green flag, the others on a broadcast from the previous drone
HATS = ("event_whenflagclicked", "event_whenbroadcastreceived")

Op = Tuple  # ("call", method, args) | ("repeat", times, [ops])


class LbgError(Exception):
    pass


def _field(block, name):
    return block["fields"][name][0]


def _raw(blocks, block, name):
    raw = block["inputs"][name][1]
    if isinstance(raw, list):
        return raw[1]
    return blocks[raw]["fields"][next(iter(blocks[raw]["fields"]))][0]


def _number(value):
    """Scratch stores numbers as strings; keep ints as ints, others as floats."""
    if isinstance(value, bool):
        raise LbgError(f"Ожидалось число, получено {value!r}")
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    try:
        return float(text)
    except ValueError:
        raise LbgError(f"Ожидалось число, получено {text!r}") from None


def _walk(blocks, bid, out: List[Op]):
    while bid:
        b = blocks[bid]
        op = b["opcode"].removeprefix(PREFIX)
        n = lambda k: _number(_raw(blocks, b, k))  # noqa: E731
        if op == "calibration":
            out.append(("call", "calibrate", (n("TIME"),)))
        elif op == "takeOff":
            out.append(("call", "takeoff", (n("Z"), n("TIME"))))
        elif op == "RGB":
            color = _field(blocks[b["inputs"]["COLOR"][1]], "colorParam")
            if color not in COLORS:
                raise LbgError(f"Неизвестный цвет {color!r}")
            out.append(("call", "rgb", (color,)))
        elif op == "code":
            out.append(("call", "code", (n("CODE"), n("TIME"))))
        elif op == "codeZ":
            out.append(("call", "code_z", (n("CODE"), n("Z"), n("TIME"))))
        elif op == "setZ":
            out.append(("call", "set_z", (n("Z"), n("TIME"))))
        elif op == "circle":
            rotate = _field(b, "ROTATE")
            if rotate not in ("cw", "ccw"):
                raise LbgError(f"Неизвестное направление круга {rotate!r}")
            out.append(("call", "circle", (n("COUNT"), n("CODE1"), n("CODE2"), n("TIME"), rotate)))
        elif op == "autoLand":
            out.append(("call", "land", ()))
        elif op == "control_repeat":
            body: List[Op] = []
            _walk(blocks, b["inputs"]["SUBSTACK"][1], body)
            out.append(("repeat", n("TIMES"), body))
        # flightNum, say, broadcast, wait, missionSend/Start ... are app-side
        bid = b.get("next")


def _title(src: str) -> str:
    return re.sub(r"^FM10 sets-|\.lbg$", "", str(src).replace("\\", "/").split("/")[-1])


def parse_lbg(src) -> Tuple[str, List[Tuple[int, List[Op]]]]:
    """Return (title, [(drone_number, ops), ...]) for an .lbg file."""
    try:
        project = json.loads(zipfile.ZipFile(src).read("project.json"))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as e:
        raise LbgError(f"Не удалось прочитать проект .lbg: {e}") from e
    drones = []
    for t in project["targets"]:
        if t["isStage"]:
            continue
        blocks = t["blocks"]
        start = next((bid for bid, b in blocks.items()
                      if isinstance(b, dict) and b["opcode"] in HATS), None)
        number = next((int(_number(_raw(blocks, b, "NUM"))) for b in blocks.values()
                       if isinstance(b, dict) and b["opcode"] == PREFIX + "flightNum"), int(t["name"]))
        ops: List[Op] = []
        if start is not None:
            _walk(blocks, blocks[start]["next"], ops)
        drones.append((number, ops))
    return _title(src), drones


def _apply(drone, ops):
    for op in ops:
        if op[0] == "call":
            getattr(drone, op[1])(*op[2])
        else:
            for _ in range(int(op[1])):
                _apply(drone, op[2])


def lbg_to_show(src) -> Show:
    """Build a Show straight from an .lbg file."""
    title, drones = parse_lbg(src)
    show = Show(title)
    for number, ops in drones:
        _apply(show.drone(number), ops)
    return show


def _emit(ops, indent, out):
    pad = "    " * indent
    for op in ops:
        if op[0] == "call":
            out.append(f"{pad}d.{op[1]}({', '.join(repr(a) for a in op[2])})")
        else:
            out.append(f"{pad}for _ in range({op[1]!r}):")
            body = len(out)
            _emit(op[2], indent + 1, out)
            if len(out) == body:
                out.append(f"{pad}    pass")


def lbg_to_source(src, import_line="from litebee import Show") -> str:
    """Render an .lbg project as a Python show file."""
    title, drones = parse_lbg(src)
    out = [import_line, "", f"show = Show({title!r})", ""]
    for number, ops in drones:
        out.append(f"d = show.drone({number})")
        _emit(ops, 0, out)
        out.append("")
    out += ["if __name__ == '__main__':", "    print(show.report())", ""]
    return "\n".join(out)


def convert(src, dst, import_line="from litebee import Show"):
    with open(dst, "w", encoding="utf-8") as f:
        f.write(lbg_to_source(src, import_line))
