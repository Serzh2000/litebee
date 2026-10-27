"""Convert a LiteBee Go .lbg project (Scratch 3 zip) into a Python show file.

usage: python lbg_to_py.py "Z:/FM10 sets-My Dream.lbg" shows/my_dream.py
"""
import json
import re
import sys
import zipfile

PREFIX = "litebeeWingFormation_"
# drone 1 starts on the green flag, the others on a broadcast from the previous drone
HATS = ("event_whenflagclicked", "event_whenbroadcastreceived")


def field(block, name):
    return block["fields"][name][0]


def num(blocks, block, name):
    raw = block["inputs"][name][1]
    if isinstance(raw, list):
        return raw[1]
    return blocks[raw]["fields"][next(iter(blocks[raw]["fields"]))][0]


def stack(blocks, bid, indent, out):
    pad = "    " * indent
    while bid:
        b = blocks[bid]
        op = b["opcode"].removeprefix(PREFIX)
        n = lambda k: num(blocks, b, k)
        if op == "calibration":
            out.append(f"{pad}d.calibrate({n('TIME')})")
        elif op == "takeOff":
            out.append(f"{pad}d.takeoff({n('Z')}, {n('TIME')})")
        elif op == "RGB":
            out.append(f"{pad}d.rgb({field(blocks[b['inputs']['COLOR'][1]], 'colorParam')!r})")
        elif op == "code":
            out.append(f"{pad}d.code({n('CODE')}, {n('TIME')})")
        elif op == "codeZ":
            out.append(f"{pad}d.code_z({n('CODE')}, {n('Z')}, {n('TIME')})")
        elif op == "setZ":
            out.append(f"{pad}d.set_z({n('Z')}, {n('TIME')})")
        elif op == "circle":
            out.append(f"{pad}d.circle({n('COUNT')}, {n('CODE1')}, {n('CODE2')}, {n('TIME')}, {field(b, 'ROTATE')!r})")
        elif op == "autoLand":
            out.append(f"{pad}d.land()")
        elif op == "control_repeat":
            out.append(f"{pad}for _ in range({n('TIMES')}):")
            body = len(out)
            stack(blocks, b["inputs"]["SUBSTACK"][1], indent + 1, out)
            if len(out) == body:
                out.append(f"{pad}    pass")
        # flightNum, say, broadcast, wait, missionSend/Start ... are app-side
        bid = b.get("next")


def convert(src, dst):
    project = json.loads(zipfile.ZipFile(src).read("project.json"))
    title = re.sub(r"^FM10 sets-|\.lbg$", "", src.replace("\\", "/").split("/")[-1])
    out = ["from litebee_show import Show", "", f"show = Show({title!r})", ""]
    for t in project["targets"]:
        if t["isStage"]:
            continue
        blocks = t["blocks"]
        start = next(
            (bid for bid, b in blocks.items()
             if isinstance(b, dict) and b["opcode"] in HATS), None)
        number = next((int(num(blocks, b, "NUM")) for b in blocks.values()
                       if isinstance(b, dict) and b["opcode"] == PREFIX + "flightNum"), int(t["name"]))
        out += [f"d = show.drone({number})"]
        stack(blocks, blocks[start]["next"], 0, out)
        out.append("")
    out += ["if __name__ == '__main__':", "    print(show.report())", ""]
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
