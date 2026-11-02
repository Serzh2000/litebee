"""Export a show to JSON for the Electron app, plus golden values from the Python simulator.

    python tools/export_show.py shows/my_dream.py desktop/shows/my_dream.json desktop/tests/golden/my_dream.json

The JSON show is {name, drones: {"1": [{kind, seconds, args, line}, ...]}}. The golden file holds what the Python
simulator computes (duration, step count, positions and LED colours at sample times, path segments), so that the
TypeScript simulator can be checked against it number by number.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from litebee.loader import load_show  # noqa: E402


def export(show_path: str, json_path: str, golden_path: str, samples: int = 24):
    show = load_show(show_path)
    data = {"name": show.name,
            "drones": {str(n): [{"kind": s.kind, "seconds": s.seconds, "args": s.args, "line": s.line}
                                for s in d.steps] for n, d in sorted(show.drones.items())}}
    paths = show.paths()
    dur = show.duration
    times = [round(dur * i / (samples - 1), 3) for i in range(samples)] + [0.0, 12.0, 30.0]
    golden = {"name": show.name, "duration": dur, "step_count": show.step_count, "times": times, "drones": {}}
    for n, d in sorted(show.drones.items()):
        golden["drones"][str(n)] = {
            "duration": d.duration,
            "segments": len(paths[n]),
            "positions": [list(show.positions_at(t, paths)[n]) for t in times],
            "colors": [list(d.color_at(t)[1]) for t in times],
            "color_names": [d.color_at(t)[0] for t in times],
            "path_head": [[seg[0], seg[1], list(seg[2]), list(seg[3]), seg[4], seg[5]] for seg in paths[n][:6]],
        }
    from litebee.safety import check_show
    golden["findings"] = [{"level": f.level, "message": f.message, "drone": f.drone, "t": f.t, "line": f.line}
                          for f in check_show(show, 60, max_height_cm=150)]
    for p, obj in ((json_path, data), (golden_path, golden)):
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    print(f"{show.name}: {len(data['drones'])} drones, {show.step_count} steps, {dur:.1f} s -> {json_path}, {golden_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    export(*sys.argv[1:4])
