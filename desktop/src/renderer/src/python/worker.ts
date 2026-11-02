/// <reference lib="webworker" />
import { loadPyodide, type PyodideInterface } from 'pyodide'
// The DSL is the one the Python app uses: these three files of the repository run here unchanged.
import missionPy from '../../../../../litebee/mission.py?raw'
import protocolPy from '../../../../../litebee/protocol.py?raw'
import showPy from '../../../../../litebee/show.py?raw'

/**
 * Runs show source (Python) in Pyodide inside a worker, so a runaway loop in the user's code is stopped by
 * terminating the worker. Mirrors litebee.loader.run_show_source: `from litebee_show import Show` keeps working.
 */
const RUNNER = `
import json, sys, types

def run(source, filename):
    import litebee.show as show_module
    alias = types.ModuleType("litebee_show")
    alias.__dict__.update(show_module.__dict__)
    sys.modules["litebee_show"] = alias
    ns = {"__name__": "litebee_show_program", "__file__": filename}
    try:
        exec(compile(source, filename, "exec"), ns)
    except SyntaxError as e:
        return json.dumps({"error": f"Синтаксическая ошибка в строке {e.lineno}: {e.msg}", "line": e.lineno})
    except BaseException as e:
        line, tb = None, e.__traceback__
        while tb:
            if tb.tb_frame.f_code.co_filename == filename:
                line = tb.tb_lineno
            tb = tb.tb_next
        where = f" (строка {line})" if line else ""
        return json.dumps({"error": f"{type(e).__name__}: {e}{where}", "line": line})
    finally:
        sys.modules.pop("litebee_show", None)
    show = ns.get("show")
    if not isinstance(show, show_module.Show):
        return json.dumps({"error": "В файле нет переменной show = Show('имя')", "line": None})
    if show.step_count > show_module.MAX_SHOW_STEPS:
        return json.dumps({"error": str(show_module.ShowTooLarge()), "line": None})
    drones = {str(n): [{"kind": s.kind, "seconds": s.seconds, "args": s.args, "line": s.line} for s in d.steps]
              for n, d in sorted(show.drones.items())}
    return json.dumps({"ok": {"name": str(show.name), "drones": drones}}, default=str)
`

let ready: Promise<PyodideInterface> | null = null

function boot(indexURL: string): Promise<PyodideInterface> {
  ready ??= (async () => {
    const py = await loadPyodide({ indexURL })
    py.FS.mkdir('/litebee')
    py.FS.writeFile('/litebee/__init__.py', '"""The DSL part of litebee, for the show editor."""\n')
    py.FS.writeFile('/litebee/protocol.py', protocolPy)
    py.FS.writeFile('/litebee/mission.py', missionPy)
    py.FS.writeFile('/litebee/show.py', showPy)
    py.runPython("import sys; sys.path.insert(0, '/')")
    py.runPython(RUNNER)
    return py
  })()
  return ready
}

interface Request {
  id: number
  indexURL: string
  source: string
  filename: string
}

self.onmessage = async (e: MessageEvent<Request>) => {
  const { id, indexURL, source, filename } = e.data
  try {
    const py = await boot(indexURL)
    const run = py.globals.get('run')
    const text = run(source, filename) as string
    run.destroy()
    self.postMessage({ id, result: JSON.parse(text) })
  } catch (err) {
    self.postMessage({ id, result: { error: `Внутренняя ошибка Python: ${err instanceof Error ? err.message : String(err)}`, line: null } })
  }
}

self.postMessage({ id: 0, ready: true })
