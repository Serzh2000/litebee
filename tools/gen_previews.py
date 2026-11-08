"""Routes of every example show, for the thumbnails of the new-project wizard.

Writes desktop/src/renderer/src/data/previews.json: {show id: [[#rrggbb, [x0, y0, x1, y1, ...]], ...]}, one entry
per drone, the route in tenths of a cell (cell = 40 cm; the origin is the middle of cell 0), the colour of the
first lit LED of the drone. Run from the repository root: python tools/gen_previews.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from litebee.loader import run_show_source  # noqa: E402

CATALOG = os.path.join(ROOT, "desktop", "src", "renderer", "src", "data", "catalog.json")
OUT = os.path.join(ROOT, "desktop", "src", "renderer", "src", "data", "previews.json")


def source_path(item, kind):
    base = os.path.join(ROOT, "shows", "gallery" if kind == "gallery" else "")
    return os.path.join(base, item["id"] + ".py")


def lit(rgb):
    return max(rgb) > 40


def route(drone):
    pts = []
    for t0, t1, p0, p1, kind, idx in drone.path():
        if not pts:
            pts.append(p0)
        pts.append(p1)
    out = []
    last = None
    for x, y, _z in pts:
        q = (round(x / 4), round(y / 4))  # tenths of a cell
        if q != last:
            out += [q[0], q[1]]
            last = q
    return out


def colour(drone):
    for s in drone.steps:
        if s.kind == "rgb" and lit(s.args["rgb"]):
            r, g, b = s.args["rgb"]
            return "#%02x%02x%02x" % (r, g, b)
    return "#7a8794"


def main():
    catalog = json.load(open(CATALOG, encoding="utf8"))
    previews = {}
    for kind in ("gallery", "classic"):
        for item in catalog[kind]:
            path = source_path(item, kind)
            show = run_show_source(open(path, encoding="utf8").read(), path)
            previews[item["id"]] = [[colour(d), route(d)] for _n, d in sorted(show.drones.items())]
    with open(OUT, "w", encoding="utf8") as f:
        json.dump(previews, f, separators=(",", ":"), ensure_ascii=False)
    print(len(previews), "shows,", os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    main()
