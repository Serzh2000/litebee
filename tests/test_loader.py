"""Running show source in a worker process: time limit, step limit, results across the boundary."""
import os
import threading
import time

import pytest

from litebee.loader import (SHOW_TIMEOUT_S, ShowLoadError, ShowRun, ShowTimeoutError, load_show,
                            load_show_source, run_show_source)
from litebee.show import MAX_SHOW_STEPS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEAD = "from litebee import Show\nshow = Show('t')\nd = show.drone(1)\n"
LOOP = "from litebee import Show\nwhile True:\n    pass\n"


def steps(show):
    return {n: [(s.kind, s.seconds, s.args, s.line) for s in d.steps] for n, d in show.drones.items()}


def test_default_timeout_is_five_seconds():
    assert SHOW_TIMEOUT_S == 5


def test_normal_show_loads_and_matches_in_process():
    src = HEAD + "d.calibrate(5)\nd.takeoff(100, 5)\nd.rgb('green')\nd.code(25, 4)\nd.land()\nshow.drone(2).rgb((1, 2, 3))\n"
    via_worker = load_show_source(src, "x.py")
    in_proc = run_show_source(src, "x.py")
    assert via_worker.name == "t" and sorted(via_worker.drones) == [1, 2]
    assert steps(via_worker) == steps(in_proc)                 # including source lines and tuple colours
    assert via_worker.drones[1].color_at(10)[1] == (0, 255, 0)
    assert via_worker.drones[2].steps[0].args["rgb"] == (1, 2, 3)
    assert via_worker.closest_approaches() == in_proc.closest_approaches()


def test_old_import_name_works_in_worker():
    show = load_show_source("from litebee_show import Show\nshow = Show('old')\nshow.drone(1).takeoff(50, 2)\n")
    assert show.name == "old" and show.drones[1].steps[0].args["z"] == 50


def test_real_show_equals_in_process():
    path = os.path.join(ROOT, "shows", "my_dream.py")
    src = open(path, encoding="utf-8").read()
    assert steps(load_show(path)) == steps(run_show_source(src, path))


def test_infinite_loop_times_out_without_hanging():
    t0 = time.time()
    with pytest.raises(ShowTimeoutError) as e:
        load_show_source(LOOP, timeout=1.0)
    assert time.time() - t0 < 1.0 + 2
    assert str(e.value) == "Шоу выполняется дольше 1 с. Проверьте циклы в коде"
    assert isinstance(e.value, ShowLoadError)


def test_default_limit_message_and_worker_is_killed():
    run = ShowRun(LOOP)                                          # default limit
    t0 = time.time()
    with pytest.raises(ShowTimeoutError) as e:
        run.run()
    assert time.time() - t0 < SHOW_TIMEOUT_S + 2
    assert str(e.value) == "Шоу выполняется дольше 5 с. Проверьте циклы в коде"
    assert run._proc.poll() is not None                           # the worker process is gone


def test_sleeping_and_busy_loops_both_time_out():
    with pytest.raises(ShowTimeoutError):
        load_show_source("import time\ntime.sleep(60)\n", timeout=0.8)
    with pytest.raises(ShowTimeoutError):
        load_show_source("import threading\nthreading.Thread(target=lambda: 1 / 0).start()\nwhile 1: pass\n",
                         timeout=0.8)


def test_timeout_none_runs_in_process():
    show = load_show_source(HEAD + "d.takeoff(80, 2)\n", timeout=None)
    assert show.drones[1].steps[0].args["z"] == 80


def test_too_many_steps_is_an_error_with_line():
    with pytest.raises(ShowLoadError) as e:
        load_show_source(HEAD + "for i in range(10001):\n    d.set_z(100, 0.1)\n", timeout=20)
    assert str(e.value).startswith(f"Шоу содержит больше {MAX_SHOW_STEPS} шагов. Проверьте циклы в коде")
    assert e.value.line == 5
    assert MAX_SHOW_STEPS == 10000


def test_exactly_the_maximum_is_allowed():
    show = load_show_source(HEAD + "for i in range(10000):\n    d.set_z(100, 0.1)\n", timeout=20)
    assert len(show.drones[1].steps) == 10000 and show.step_count == 10000


def test_total_steps_over_all_drones_is_limited():
    src = HEAD + "for n in range(1, 12):\n    for i in range(1000):\n        show.drone(n).set_z(100, 0.1)\n"
    with pytest.raises(ShowLoadError, match="Шоу содержит больше 10000 шагов"):
        load_show_source(src, timeout=20)
    with pytest.raises(ShowLoadError, match="Шоу содержит больше 10000 шагов"):      # also in-process
        load_show_source(src, timeout=None)


def test_errors_cross_the_process_boundary():
    with pytest.raises(ShowLoadError, match="строка 2") as e:
        load_show_source("from litebee import Show\nshow = Show('x'); show.drone(1).rgb('pink')\n")
    assert e.value.line == 2 and "pink" in str(e.value)
    with pytest.raises(ShowLoadError) as e:
        load_show_source("def (:")
    assert e.value.line == 1 and "Синтаксическая ошибка" in str(e.value)
    with pytest.raises(ShowLoadError, match="show"):
        load_show_source("x = 1")
    with pytest.raises(ShowLoadError, match="SystemExit"):               # sys.exit() must not close the app
        load_show_source("import sys\nsys.exit(2)\n")
    with pytest.raises(ShowLoadError, match="аварийно"):                 # worker dies without a result
        load_show_source("import os\nos._exit(7)\n")


def test_prints_of_the_show_do_not_break_the_result():
    show = load_show_source(HEAD + "print('x' * 200000)\nd.takeoff(60, 1)\n")
    assert show.drones[1].steps[0].args["z"] == 60


def test_works_from_another_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_show_source(HEAD + "d.takeoff(60, 1)\n").name == "t"


def test_cancel_kills_the_worker():
    run = ShowRun(LOOP, timeout=30)
    out = []

    def work():
        try:
            run.run()
        except ShowLoadError as e:
            out.append(e)

    th = threading.Thread(target=work)
    t0 = time.time()
    th.start()
    time.sleep(0.8)
    run.cancel()
    th.join(5)
    assert not th.is_alive() and time.time() - t0 < 5
    assert out and "отменена" in str(out[0]) and not isinstance(out[0], ShowTimeoutError)


def test_load_show_file_has_the_limit_too(tmp_path):
    p = tmp_path / "loop.py"
    p.write_text(LOOP, encoding="utf-8")
    t0 = time.time()
    with pytest.raises(ShowTimeoutError):
        load_show(p, timeout=1.0)
    assert time.time() - t0 < 3
