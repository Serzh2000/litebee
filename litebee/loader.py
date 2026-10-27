"""Load a Show from a Python show file (or source text) or from an .lbg project.

Show source is the user's own program and can contain an endless loop, so
`load_show_source` runs it in a separate worker process (`litebee.show_worker`)
with a time limit and kills the process when the limit expires. The worker
sends back plain JSON data (the steps of every drone); the parent rebuilds the
Show from it. `timeout=None` runs the source in-process, as before.
"""
import json
import os
import subprocess
import sys
import threading
import types

from . import show as show_module
from .show import MAX_SHOW_STEPS, Drone, Show, ShowTooLarge, Step

SHOW_TIMEOUT_S = 5.0                         # default time limit for running show source
RESULT_MARK = b"\x00LITEBEE-RESULT\x00"      # precedes the JSON result on the worker's stdout


class ShowLoadError(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.line = line


class ShowTimeoutError(ShowLoadError):
    """Running the show source took longer than the time limit (the worker was killed)."""


def _error_line(e, filename):
    line, tb = None, e.__traceback__
    while tb:
        if tb.tb_frame.f_code.co_filename == filename:
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def run_show_source(source: str, filename: str = "<show>") -> Show:
    """Execute show source in THIS process and return its module-level `show`.

    Existing show files do `from litebee_show import Show`; that name is
    provided here as an alias of litebee.show for the duration of the run.
    The code is the user's own program and runs with their privileges.
    No time limit: use load_show_source for that.
    """
    alias = types.ModuleType("litebee_show")
    alias.__dict__.update(show_module.__dict__)
    saved = sys.modules.get("litebee_show")
    sys.modules["litebee_show"] = alias
    try:
        ns = {"__name__": "litebee_show_program", "__file__": filename}
        try:
            exec(compile(source, filename, "exec"), ns)
        except SyntaxError as e:
            raise ShowLoadError(f"Синтаксическая ошибка в строке {e.lineno}: {e.msg}", e.lineno) from e
        except Exception as e:
            line = _error_line(e, filename)
            where = f" (строка {line})" if line else ""
            if isinstance(e, ShowTooLarge):
                raise ShowLoadError(f"{e}{where}", line) from e
            raise ShowLoadError(f"{type(e).__name__}: {e}{where}", line) from e
    finally:
        if saved is None:
            sys.modules.pop("litebee_show", None)
        else:
            sys.modules["litebee_show"] = saved
    show = ns.get("show")
    if not isinstance(show, Show):
        raise ShowLoadError("В файле нет переменной show = Show('имя')")
    if show.step_count > MAX_SHOW_STEPS:
        raise ShowLoadError(str(ShowTooLarge()))
    return show


# ---- crossing the process boundary: the Show as plain data ----------------------

def show_to_data(show: Show) -> dict:
    return {"name": str(show.name),
            "drones": [[n, [[s.kind, s.seconds, s.args, s.line] for s in d.steps]]
                       for n, d in show.drones.items()]}


def show_from_data(data: dict) -> Show:
    show = Show(data["name"])
    for number, steps in data["drones"]:
        d = show.drones.setdefault(number, Drone(number))
        for kind, seconds, args, line in steps:
            if "rgb" in args:
                args["rgb"] = tuple(args["rgb"])      # JSON turns tuples into lists
            d.steps.append(Step(kind, float(seconds), args, line))
    return show


class ShowRun:
    """One run of show source in a worker process. `run()` blocks; `cancel()` kills the worker."""

    def __init__(self, source: str, filename: str = "<show>", timeout: float = SHOW_TIMEOUT_S):
        self.source, self.filename, self.timeout = source, filename, timeout
        self._proc = None
        self._cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            self._cancelled = True
            if self._proc is not None:
                self._proc.kill()

    def run(self) -> Show:
        payload = json.dumps({"source": self.source, "filename": self.filename,
                              "timeout": self.timeout}).encode("utf-8")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in (root, os.environ.get("PYTHONPATH")) if p),
                   PYTHONIOENCODING="utf-8")
        try:                                  # keep the worker's stderr (user prints) when there is a real one
            sys.stderr.fileno()
            err = None
        except Exception:
            err = subprocess.DEVNULL
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with self._lock:
            if self._cancelled:
                raise ShowLoadError("Проверка отменена")
            try:
                self._proc = subprocess.Popen(
                    [sys.executable, "-X", "utf8", "-m", "litebee.show_worker"], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=err, env=env, creationflags=flags)
            except OSError as e:
                raise ShowLoadError(f"Не удалось запустить проверку шоу: {e}") from e
        proc = self._proc
        try:
            out, _ = proc.communicate(payload, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise ShowTimeoutError(f"Шоу выполняется дольше {self.timeout:g} с. Проверьте циклы в коде") from None
        except BaseException:
            proc.kill()
            raise
        if self._cancelled:
            raise ShowLoadError("Проверка отменена")
        i = out.rfind(RESULT_MARK)
        if i < 0:
            raise ShowLoadError(f"Шоу завершилось аварийно (код {proc.returncode}). Проверьте код")
        try:
            result = json.loads(out[i + len(RESULT_MARK):].decode("utf-8"))
        except ValueError as e:
            raise ShowLoadError(f"Не удалось прочитать результат шоу: {e}") from e
        if "error" in result:
            raise ShowLoadError(result["error"], result.get("line"))
        return show_from_data(result["ok"])


def load_show_source(source: str, filename: str = "<show>", timeout=SHOW_TIMEOUT_S) -> Show:
    """Run show source and return its module-level `show`.

    By default the source runs in a worker process and is killed after `timeout`
    seconds (ShowTimeoutError, a ShowLoadError). `timeout=None` runs it in-process.
    """
    if timeout is None:
        return run_show_source(source, filename)
    return ShowRun(source, filename, timeout).run()


def load_show(path, timeout=SHOW_TIMEOUT_S) -> Show:
    path = os.fspath(path)
    if path.lower().endswith(".lbg"):
        from .lbg import LbgError, lbg_to_show
        try:
            return lbg_to_show(path)
        except LbgError as e:
            raise ShowLoadError(str(e)) from e
    with open(path, encoding="utf-8") as f:
        return load_show_source(f.read(), path, timeout)
