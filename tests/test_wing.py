"""Wing flight through the remote: exact bytes, limits, pre-flight refusals, the order of a flight, emergency landings.

Everything runs on FakeRemote; no serial port is opened and no drone is touched."""
import pytest

from fake_remote import FakeRemote, make_data
from litebee import cli, remote as r, wing
from litebee.safety import SafetyError

FAST = wing.WingTiming(calibrate_s=0.05, takeoff_s=0.05, height_s=0.05, settle_s=0.03, move_s=0.02, land_s=0.05,
                       step_s=0.01)
LINKED = dict(drone_linked=True, version=(123, 111))
MOVES = [(0, 10), (10, 0)]          # short moves, fast speed: the test does not wait long


def hexes(fake):
    return [c.hex(" ") for c in fake.commands]


def flight(fake, tmp_path, *, allow=True, speed=25, **kw):
    link = r.RemoteLink(fake, allow_commands=allow)
    return wing.WingFlight(link, land_flag=str(tmp_path / "LAND_NOW"), timing=FAST, speed_cm_s=speed,
                           log=lambda m: None, **kw)


def test_message_bytes_are_the_ones_litebee_go_sends():
    assert wing.calibrate_msg().hex(" ") == "0a"
    assert wing.takeoff_msg().hex(" ") == "10"
    assert wing.land_msg().hex(" ") == "11"
    assert wing.hold_msg().hex(" ") == "1d 02 00 00 00 00 00 00 00 00"
    assert wing.height_msg(80).hex(" ") == "1e 02 00 00 00 00 50 00"
    assert wing.velocity_msg(15, 0).hex(" ") == "1b 02 00 0f 00 00"          # forward
    assert wing.velocity_msg(0, 15).hex(" ") == "1b 02 00 00 0f 00"          # right
    assert wing.velocity_msg(-10, -10).hex(" ") == "1b 02 00 f6 f6 00"       # backward, left: two's complement
    assert wing.velocity_msg().hex(" ") == "1b 02 00 00 00 00"               # stop
    assert wing.move_msg(0, 30).hex(" ") == "1e 04 00 00 1e 00"              # legacy: did not move the drone


def test_plan_move_is_distance_over_speed():
    assert wing.plan_move(0, 30, 15) == (15, 0, 2.0)
    assert wing.plan_move(30, 0, 15) == (0, 15, 2.0)
    fwd, right, seconds = wing.plan_move(30, 30, 15)
    assert (fwd, right) == (11, 11) and seconds == pytest.approx(2.83, abs=0.01)
    assert wing.plan_move(-20, 0, 10)[:2] == (0, -10)


@pytest.mark.parametrize("call", [
    lambda: wing.plan_move(0, 0),
    lambda: wing.plan_move(0, 51),
    lambda: wing.plan_move(0.5, 10),
    lambda: wing.plan_move(0, 30, 4),
    lambda: wing.plan_move(0, 30, 26),
    lambda: wing.plan_move(50, 50, 5),                 # 14 s: longer than a step may take
    lambda: wing.velocity_msg(26, 0),
    lambda: wing.velocity_msg(0, 10.5),
    lambda: wing.height_msg(29),
    lambda: wing.height_msg(121),
    lambda: wing.check_plan([]),
    lambda: wing.check_plan([(0, 10)] * 7),
])
def test_limits(call):
    with pytest.raises(SafetyError):
        call()


def test_battery_threshold_cannot_go_below_the_floor(tmp_path):
    with pytest.raises(SafetyError):
        flight(FakeRemote(**LINKED), tmp_path, min_volts=6.9)


@pytest.mark.parametrize("fake_kwargs, text", [
    (dict(drone_linked=True, version=(0, 111)), "не видит дрон"),
    (dict(drone_linked=False, version=(123, 111)), "нулевой"),
    (dict(drone_linked=True, version=(123, 111), packet=make_data(volts=7.0)), "Батарея"),
    (dict(drone_linked=True, version=(123, 111), packet=make_data(roll=25)), "не ровно"),
    (dict(drone_linked=True, version=(123, 111), ack=False), "не ответил"),
])
def test_preflight_refuses(tmp_path, fake_kwargs, text):
    fake = FakeRemote(**fake_kwargs)
    with pytest.raises(SafetyError, match=text):
        flight(fake, tmp_path).fly(MOVES)
    assert fake.commands == []                          # nothing but read-only messages were sent


def test_preflight_refuses_when_the_land_flag_exists(tmp_path):
    (tmp_path / "LAND_NOW").write_text("")
    fake = FakeRemote(**LINKED)
    with pytest.raises(SafetyError, match="LAND_NOW"):
        flight(fake, tmp_path).fly(MOVES)
    assert fake.commands == []


def test_a_normal_flight_has_this_order(tmp_path):
    fake = FakeRemote(**LINKED)
    flight(fake, tmp_path).fly(MOVES)
    assert hexes(fake) == [
        "0a",                                                  # calibrate
        "10",                                                  # take off
        "1e 02 00 00 00 00 50 00",                             # height 80 cm
        "1d 02 00 00 00 00 00 00 00 00",                       # hold
        "1b 02 00 19 00 00", "1b 02 00 00 00 00",              # 10 cm forward at 25 cm/s, stop
        "1b 02 00 00 19 00", "1b 02 00 00 00 00",              # 10 cm right, stop
        "1b 02 00 00 00 00", "11", "11", "11",                 # stop, then land three times
    ]
    assert set(fake.written) - set(fake.commands) <= r.READ_ONLY_WRITES | {bytes([0xFD, 0xFD, len(c)]) + c
                                                                          for c in fake.commands}


def test_without_permission_nothing_is_sent(tmp_path):
    fake = FakeRemote(**LINKED)
    with pytest.raises(r.RemoteError):
        flight(fake, tmp_path, allow=False).fly(MOVES)
    assert fake.commands == []


def test_land_flag_after_take_off_lands(tmp_path):
    def hook(f, payload):
        if payload == wing.takeoff_msg():
            (tmp_path / "LAND_NOW").write_text("")
    fake = FakeRemote(**LINKED, on_command=hook)
    with pytest.raises(wing.FlightAbort, match="LAND_NOW"):
        flight(fake, tmp_path).fly(MOVES)
    assert hexes(fake) == ["0a", "10", "1b 02 00 00 00 00", "11", "11", "11"]


def test_tilt_over_30_degrees_lands(tmp_path):
    def hook(f, payload):
        if payload == wing.height_msg(80):
            f.packet = make_data(roll=35)
    fake = FakeRemote(**LINKED, on_command=hook)
    with pytest.raises(wing.FlightAbort, match="наклон"):
        flight(fake, tmp_path).fly(MOVES)
    assert hexes(fake)[-3:] == ["11", "11", "11"] and "1d 02 00 00 00 00 00 00 00 00" not in hexes(fake)


def test_height_over_the_ceiling_lands(tmp_path):
    def hook(f, payload):
        if payload == wing.takeoff_msg():
            f.packet = make_data(pos=(0, 0, 150))
    fake = FakeRemote(**LINKED, on_command=hook)
    with pytest.raises(wing.FlightAbort, match="потолка"):
        flight(fake, tmp_path).fly(MOVES)
    assert hexes(fake)[-3:] == ["11", "11", "11"]


def test_silent_data_lands(tmp_path, monkeypatch):
    monkeypatch.setattr(wing, "SILENCE_S", 0.15)

    def hook(f, payload):
        if payload == wing.takeoff_msg():
            f.streaming = False
    fake = FakeRemote(**LINKED, on_command=hook)
    with pytest.raises(wing.FlightAbort, match="поток данных"):
        flight(fake, tmp_path).fly(MOVES)
    assert hexes(fake)[-3:] == ["11", "11", "11"]


def test_low_battery_in_flight_lands(tmp_path):
    def hook(f, payload):
        if payload == wing.takeoff_msg():
            f.packet = make_data(volts=6.2)
    fake = FakeRemote(**LINKED, on_command=hook)
    with pytest.raises(wing.FlightAbort, match="батарея"):
        flight(fake, tmp_path).fly(MOVES)
    assert hexes(fake)[-3:] == ["11", "11", "11"]


def test_an_error_while_flying_lands(tmp_path):
    def hook(f, payload):
        if payload.startswith(bytes([27, 2, 0, 25])):       # the first move
            raise RuntimeError("boom")
    fake = FakeRemote(**LINKED, on_command=hook)
    with pytest.raises(RuntimeError):
        flight(fake, tmp_path).fly(MOVES)
    assert hexes(fake)[-3:] == ["11", "11", "11"]


# ---- the command line ------------------------------------------------------------------------------------------

@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "LAND_FLAG", str(tmp_path / "LAND_NOW"))
    monkeypatch.setattr(wing, "DEFAULT_TIMING", FAST)
    box = {}

    def open_link(port=None, **kw):
        box["kw"] = kw
        box["fake"] = FakeRemote(**LINKED)
        return r.RemoteLink(box["fake"], allow_commands=kw.get("allow_commands", False))
    monkeypatch.setattr(r, "open_link", open_link)
    return box, str(tmp_path / "LAND_NOW")


def test_cli_dry_run_sends_no_commands(cli_env, capsys):
    box, flag = cli_env
    assert cli.main(["wing-fly", "--land-flag", flag]) == 0
    assert box["kw"] == {"allow_commands": False} and box["fake"].commands == []
    assert "Команды НЕ отправлены" in capsys.readouterr().out


def test_cli_go_flies_the_plan(cli_env, capsys, tmp_path):
    box, flag = cli_env
    assert cli.main(["wing-fly", "--go", "--forward", "10", "--right", "10", "--speed", "25", "--land-flag", flag]) == 0
    assert box["kw"] == {"allow_commands": True}
    assert hexes(box["fake"])[:2] == ["0a", "10"] and hexes(box["fake"])[-3:] == ["11", "11", "11"]
    assert "Готово" in capsys.readouterr().out
    assert list((tmp_path / "flight_logs").glob("wing_*.txt"))          # the flight log is written


def test_cli_refuses_a_bad_plan_before_touching_the_remote(cli_env, capsys):
    box, flag = cli_env
    assert cli.main(["wing-fly", "--go", "--forward", "80", "--land-flag", flag]) == 1
    assert "kw" not in box and "больше предела" in capsys.readouterr().out
    assert cli.main(["wing-fly", "--go", "--forward", "0", "--right", "0", "--land-flag", flag]) == 1
