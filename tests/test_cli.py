import os
import subprocess
import sys
import tempfile
import threading

import pytest

from conftest import HOST, ROOT
from fake_drone import FakeDrone, free_port
from litebee import cli

SHOWS = os.path.join(ROOT, "shows")


def run_cli(*argv):
    return cli.main(list(argv))


FLAG = os.path.join(tempfile.gettempdir(), "litebee_test_LAND_NOW")   # never the project's real LAND_NOW


def net_args(port, drone):
    return ["--pc", HOST, "--drone", HOST, "--port", str(port), "--udp-port", str(drone.udp_port),
            "--land-flag", FLAG]


def test_cli_hop_dry_by_default(capsys):
    port = free_port()
    with FakeDrone(port) as drone:
        assert run_cli("hop", *net_args(port, drone)) == 0
        assert drone.checksum == 8 and drone.starts == []
    assert "НЕ запущены" in capsys.readouterr().out


def test_cli_hop_go(capsys):
    port = free_port()
    with FakeDrone(port) as drone:
        assert run_cli("hop", *net_args(port, drone), "--go") == 0
        assert len(drone.starts) == 1 and drone.lands >= 3


def test_cli_hop_refuses_bad_args(capsys):
    assert run_cli("hop", "--pc", HOST, "--drone", HOST, "--port", "5", "--land-flag", FLAG, "--height", "200") == 1
    assert run_cli("hop", "--pc", HOST, "--drone", HOST, "--port", "5", "--land-flag", FLAG, "--hover", "11") == 1
    assert run_cli("hop", "--pc", HOST, "--drone", HOST, "--port", "5", "--land-flag", FLAG, "--min-volts", "5") == 1


def test_cli_hop_low_battery(capsys):
    port = free_port()
    with FakeDrone(port, volts=6.5) as drone:
        assert run_cli("hop", *net_args(port, drone), "--go") == 1
        assert drone.starts == []


def test_cli_color(capsys):
    port = free_port()
    with FakeDrone(port) as drone:
        assert run_cli("color", *net_args(port, drone), "--color", "red", "--hold", "0.5") == 0
        assert drone.checksum == 50 and len(drone.starts) == 1 and drone.stops == 1


def test_cli_listen_is_read_only(capsys):
    port = free_port()
    with FakeDrone(port) as drone:
        assert run_cli("listen", "--pc", HOST, "--drone", HOST, "--port", str(port),
                       "--udp-port", str(drone.udp_port), "--seconds", "2") == 0
        sent = {(f.group, f.id) for f in drone.frames}
        assert sent <= {(2, 1)}                    # only the pilot callback (heartbeats are not logged)
        assert drone.steps == {} and drone.starts == []
    out = capsys.readouterr().out
    assert "сырая телеметрия" in out and "00 00 00 00 00 00 4b" in out


def test_cli_refuses_real_port_on_loopback():
    with pytest.raises(SystemExit):
        run_cli("listen", "--pc", HOST, "--seconds", "0.1")


def test_cli_simulate_and_import(tmp_path, capsys):
    assert run_cli("simulate", os.path.join(SHOWS, "my_dream.py")) in (0, 1)
    out = capsys.readouterr().out
    assert "дронов 10" in out and "Проверки безопасности" in out
    # import-lbg then simulate the result
    sys.path.insert(0, os.path.dirname(__file__))
    from test_show import make_lbg
    lbg = str(tmp_path / "FM10 sets-T.lbg")
    make_lbg(lbg)
    py = str(tmp_path / "t.py")
    assert run_cli("import-lbg", lbg, py, "--port", "5") == 0
    assert "from litebee import Show" in open(py, encoding="utf-8").read()
    assert run_cli("simulate", py) in (0, 1)
    assert run_cli("simulate", lbg) in (0, 1)


def test_python_dash_m_runs_simulate_in_subprocess():
    r = subprocess.run([sys.executable, "-m", "litebee", "simulate", os.path.join(SHOWS, "my_dream.py")],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert "дронов 10" in r.stdout, r.stderr


# ---- --max-height ---------------------------------------------------------------

def test_cli_parser_max_height():
    ap = cli.build_parser()
    assert ap.parse_args(["simulate", "x.py"]).max_height == 150
    assert ap.parse_args(["simulate", "x.py", "--max-height", "170"]).max_height == 170
    assert ap.parse_args(["hop", "--pc", HOST, "--drone", HOST, "--max-height", "180"]).max_height == 180


def test_cli_simulate_max_height(capsys):
    show = os.path.join(SHOWS, "my_dream.py")
    assert run_cli("simulate", show) == 1                           # 160 cm steps, default limit 150
    out = capsys.readouterr().out
    assert "Лимит высоты: 150 см" in out and "больше лимита 150 см" in out
    assert run_cli("simulate", show, "--max-height", "170") == 0
    out = capsys.readouterr().out
    assert "Лимит высоты: 170 см" in out and "больше лимита" not in out
    assert run_cli("simulate", show, "--max-height", "200") == 0
    capsys.readouterr()


def test_cli_simulate_refuses_limit_outside_range(capsys):
    show = os.path.join(SHOWS, "my_dream.py")
    for bad in ("201", "1000", "19", "0", "-1"):
        assert run_cli("simulate", show, "--max-height", bad) == 1
        out = capsys.readouterr().out
        assert "вне допустимых пределов (20-200 см)" in out and "дронов" not in out


def test_cli_hop_max_height(capsys):
    base = ["hop", "--pc", HOST, "--drone", HOST, "--port", "5", "--land-flag", FLAG]
    assert run_cli(*base, "--height", "160") == 1                     # default limit 150
    assert run_cli(*base, "--height", "160", "--max-height", "201") == 1       # ceiling
    assert run_cli(*base, "--height", "201", "--max-height", "200") == 1       # still above the limit
    capsys.readouterr()
    port = free_port()
    with FakeDrone(port) as drone:
        assert run_cli("hop", *net_args(port, drone), "--height", "160", "--max-height", "170") == 0
        assert drone.checksum == 8 and drone.starts == []
    out = capsys.readouterr().out
    assert "высота 160 см (лимит 170 см)" in out
