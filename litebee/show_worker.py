"""Worker process of litebee.loader: runs show source and prints the result as JSON.

Started as `python -m litebee.show_worker`; reads {"source", "filename", "timeout"}
as JSON from stdin and writes RESULT_MARK + JSON ({"ok": show data} or
{"error": message, "line": n}) to stdout. Output of the user's own code goes to
stderr, so it cannot corrupt the result. The parent kills this process on timeout;
the watchdog below ends it anyway if the parent is gone. Never talks to a drone.
"""
import json
import os
import sys
import threading
import time


def _watchdog(seconds):
    time.sleep(seconds)
    os._exit(3)


def main():
    out = sys.stdout.buffer
    sys.stdout = sys.stderr
    from litebee.loader import RESULT_MARK, ShowLoadError, run_show_source, show_to_data
    try:
        req = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if req.get("timeout"):
            threading.Thread(target=_watchdog, args=(float(req["timeout"]) + 5,), daemon=True).start()
        try:
            result = {"ok": show_to_data(run_show_source(req["source"], req["filename"]))}
        except ShowLoadError as e:
            result = {"error": str(e), "line": e.line}
        except BaseException as e:                      # e.g. SystemExit in the user's code
            result = {"error": f"{type(e).__name__}: {e}"}
        data = json.dumps(result, default=str).encode("utf-8")
    except BaseException as e:
        data = json.dumps({"error": f"Внутренняя ошибка проверки: {type(e).__name__}: {e}"}).encode("utf-8")
    out.write(RESULT_MARK + data)
    out.flush()
    os._exit(0)           # do not wait for threads started by the user's code


if __name__ == "__main__":
    main()
