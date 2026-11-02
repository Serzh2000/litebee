"""Export the DSL reference (litebee/reference.py) to JSON for the Electron app's help panel.

    python tools/export_reference.py desktop/src/renderer/src/data/reference.json
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from litebee import reference  # noqa: E402


def export(path: str):
    entries = [{
        "owner": e.owner, "name": e.name, "kind": e.kind, "signature": e.signature, "summary": e.summary,
        "topic": e.topic, "status": e.status, "icon": e.icon,
        "params": [{"name": p.name, "unit": p.unit, "text": p.text} for p in e.params],
        "example": e.example.rstrip("\n"), "context": e.context, "notes": list(e.notes), "command": e.command,
    } for e in reference.ENTRIES if e.dsl]
    data = {"topics": [{"id": i, "title": t} for i, t in reference.TOPICS], "statusHint": reference.STATUS_HINT,
            "entries": entries}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"{len(entries)} entries -> {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    export(sys.argv[1])
