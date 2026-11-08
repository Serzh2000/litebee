import glob
import json
import os
import sys
import zipfile

import pytest

from litebee.lbg import lbg_to_show, lbg_to_source
from litebee.loader import ShowLoadError, load_show, load_show_source
from litebee.mission import (CMD_CIRCLE, CMD_MOVEXY, CMD_MOVEXYZ, CMD_MOVEZ, CMD_RGB, CMD_TAKEOFF,
                             DEFAULT_MAX_HEIGHT_CM, PROVEN_CMDS, xy_data,
                             HARD_MAX_HEIGHT_CM, MIN_TAKEOFF_CM, Mission, MissionStep, hop_mission,
                             resolve_max_height, z_data)
from litebee.safety import (MAX_HEIGHT_CM, MAX_LEG_SPEED_CM_S, MAX_START_DISTANCE_CM, NO_FIX_MESSAGE, Finding,
                            SafetyError, check_mission, check_position, check_show, position_problem, preflight)
from litebee.show import Show, UploadUnsupported, cell_xy, drone_to_mission

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the two real shows of the kit (ten drones each); the other files of shows/ are examples written for the app
SHOWS = [os.path.join(ROOT, "shows", name) for name in ("my_dream.py", "my_people_my_country_5.py")]


def test_cell_xy():
    assert cell_xy(0) == (0, 0) and cell_xy(13) == (40, 40) and cell_xy(143) == (440, 440)


@pytest.mark.parametrize("path", SHOWS, ids=os.path.basename)
def test_real_shows_have_ten_drones(path):
    show = load_show(path)
    assert len(show.drones) == 10
    assert "дронов 10" in show.report()
    assert show.duration > 100


@pytest.mark.parametrize("path", SHOWS, ids=os.path.basename)
def test_simulation_matches_original_litebee_show(path):
    """The port must give the same closest approaches as the original module."""
    sys.path.insert(0, ROOT)
    try:
        import litebee_show
    except ImportError:
        pytest.skip("original litebee_show.py not present")
    src = open(path, encoding="utf-8").read()
    ns = {"__name__": "x"}
    exec(compile(src, path, "exec"), ns)       # imports the ORIGINAL litebee_show
    assert isinstance(ns["show"], litebee_show.Show)
    new = load_show(path)
    assert new.closest_approaches() == ns["show"].closest_approaches()


def test_loader_errors():
    with pytest.raises(ShowLoadError, match="строка 2"):
        load_show_source("from litebee import Show\nshow = Show('x'); show.drone(1).rgb('pink')\n")
    with pytest.raises(ShowLoadError):
        load_show_source("def (:")
    with pytest.raises(ShowLoadError, match="show"):
        load_show_source("x = 1")


def test_dsl_extras_and_position():
    s = Show("t")
    d = s.drone(1)
    d.calibrate(1).takeoff(100, 2).code_s("1 2", 4).rgb_value(1, 2, 3).circle_z(14, 16, 50, 4).land()
    assert [st.kind for st in d.steps].count("code") == 2
    pos = d.position_at(3.0)
    assert pos[2] == 100
    assert d.color_at(8)[1] == (1, 2, 3) and d.color_at(0.5)[1] == (0, 0, 0)
    assert d.steps[0].line == 1 or d.steps[0].line is None or isinstance(d.steps[0].line, int)
    assert d.position_at(d.duration)[2] == 0


def test_compile_to_mission():
    s = load_show_source(
        "from litebee import Show\nshow = Show('x')\nd = show.drone(1)\n"
        "d.calibrate(5); d.takeoff(100, 5); d.rgb('green'); d.set_z(100, 3); d.land()\n")
    m = drone_to_mission(s.drones[1])
    assert [x.cmd for x in m.steps] == [0, 1, 50, 5, 2]
    assert [x.t_end for x in m.steps] == [50, 100, 100, 130, 130]
    assert m.checksum == 0 + 1 + 50 + 5 + 2
    assert CMD_RGB in m.cmds


def test_cell_moves_are_uploadable_but_code_z_and_circles_are_not():
    s = Show("x")
    s.drone(1).takeoff(100, 5).code(25, 4)
    m = drone_to_mission(s.drones[1])
    assert [x.cmd for x in m.steps] == [CMD_TAKEOFF, CMD_MOVEXY] and m.steps[1].cell == 25
    for build in (lambda d: d.code_z(25, 100, 4), lambda d: d.circle(2, 66, 77, 13),
                  lambda d: d.circle_z(14, 16, 50, 4)):
        s = Show("x")
        d = s.drone(1)
        d.takeoff(100, 5)
        build(d)
        with pytest.raises(UploadUnsupported, match="не проверен"):
            drone_to_mission(d)
    s = Show("x")
    s.drone(1).takeoff(100, 5).code(144, 4)
    with pytest.raises(UploadUnsupported, match="вне коврика"):
        drone_to_mission(s.drones[1])


def test_check_show_findings():
    s = Show("x")
    s.drone(1).takeoff(100, 5).code(25, 4).set_z(160, 2)
    s.drone(2).takeoff(100, 5).code(26, 4)        # 40 cm from drone 1: too close
    s.drone(3).takeoff(100, 5).code(999, 4)        # outside the mat
    levels = {(f.level, f.drone) for f in check_show(s)}
    assert ("error", 1) in levels            # 160 cm > limit
    assert ("error", 3) in levels            # cell 999
    assert any(f.level == "warn" for f in check_show(s))
    assert all(isinstance(f, Finding) for f in check_show(s))
    assert MAX_HEIGHT_CM == 150


def test_real_show_report_non_empty():
    findings = check_show(load_show(SHOWS[0]))
    assert any("загрузка в дрон недоступна" in f.message for f in findings)


# ---- .lbg import ----------------------------------------------------------

P = "litebeeWingFormation_"


def _num(v):
    return [1, [4, str(v)]]


def make_lbg(path):
    blocks = {
        "hat": {"opcode": "event_whenflagclicked", "next": "b1", "fields": {}, "inputs": {}},
        "fn": {"opcode": P + "flightNum", "fields": {}, "inputs": {"NUM": _num(3)}},
        "b1": {"opcode": P + "calibration", "next": "b2", "fields": {}, "inputs": {"TIME": _num(5)}},
        "b2": {"opcode": P + "takeOff", "next": "b3", "fields": {}, "inputs": {"Z": _num(100), "TIME": _num(5)}},
        "b3": {"opcode": P + "RGB", "next": "b4", "fields": {}, "inputs": {"COLOR": [1, "col"]}},
        "col": {"opcode": "x", "fields": {"colorParam": ["green", None]}, "inputs": {}},
        "b4": {"opcode": "control_repeat", "next": "b6", "fields": {},
               "inputs": {"TIMES": _num(2), "SUBSTACK": [2, "s1"]}},
        "s1": {"opcode": P + "setZ", "next": "s2", "fields": {}, "inputs": {"Z": _num(120), "TIME": _num(2.5)}},
        "s2": {"opcode": P + "code", "fields": {}, "inputs": {"CODE": _num(25), "TIME": _num(4)}},
        "b6": {"opcode": P + "circle", "next": "b7", "fields": {"ROTATE": ["cw", None]},
               "inputs": {"COUNT": _num(2), "CODE1": _num(66), "CODE2": _num(77), "TIME": _num(13)}},
        "b7": {"opcode": P + "codeZ", "next": "b8", "fields": {},
               "inputs": {"CODE": _num(85), "Z": _num(130), "TIME": _num(2)}},
        "b8": {"opcode": P + "autoLand", "fields": {}, "inputs": {}},
        "var": [12, 3],
    }
    project = {"targets": [{"isStage": True, "name": "Stage", "blocks": {}},
                           {"isStage": False, "name": "1", "blocks": blocks}]}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("project.json", json.dumps(project))


def test_lbg_matches_original_converter(tmp_path):
    src = str(tmp_path / "FM10 sets-Test.lbg")
    make_lbg(src)
    mine = lbg_to_source(src, import_line="from litebee_show import Show")
    assert "d = show.drone(3)" in mine and "show = Show('Test')" in mine
    sys.path.insert(0, ROOT)
    try:
        import lbg_to_py
    except ImportError:
        pytest.skip("original lbg_to_py.py not present")
    dst = str(tmp_path / "orig.py")
    lbg_to_py.convert(src, dst)
    assert mine == open(dst, encoding="utf-8").read()


def test_lbg_show_equals_source_show(tmp_path):
    src = str(tmp_path / "FM10 sets-Test.lbg")
    make_lbg(src)
    direct = lbg_to_show(src)
    via_source = load_show_source(lbg_to_source(src))
    d1, d2 = direct.drones[3], via_source.drones[3]
    assert [(s.kind, s.seconds, s.args) for s in d1.steps] == [(s.kind, s.seconds, s.args) for s in d2.steps]
    assert len(d1.steps) == 3 + 2 * 2 + 3     # calibrate, takeoff, rgb, 2x(setZ, code), circle, codeZ, land
    assert load_show(src).name == "Test"


def test_lbg_rejects_code_injection(tmp_path):
    src = str(tmp_path / "evil.lbg")
    make_lbg(src)
    with zipfile.ZipFile(src) as z:
        project = json.loads(z.read("project.json"))
    project["targets"][1]["blocks"]["b1"]["inputs"]["TIME"] = [1, [4, "__import__('os').system('x')"]]
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("project.json", json.dumps(project))
    with pytest.raises(ShowLoadError):
        load_show(src)


# ---- configurable height limit -------------------------------------------------

def _tall_show(z=160):
    s = Show("tall")
    s.drone(1).calibrate(2).takeoff(100, 5).set_z(z, 2).land()
    return s


def _height_errors(findings):
    return [f for f in findings if f.level == "error" and "больше лимита" in f.message]


def test_default_limit_flags_160_and_limit_170_passes():
    assert DEFAULT_MAX_HEIGHT_CM == 150 and HARD_MAX_HEIGHT_CM == 200
    s = _tall_show(160)
    errs = _height_errors(check_show(s))
    assert len(errs) == 1 and "160" in errs[0].message and "лимита 150 см" in errs[0].message
    assert len(_height_errors(check_show(s, max_height_cm=150))) == 1
    assert _height_errors(check_show(s, max_height_cm=170)) == []
    assert _height_errors(check_show(s, max_height_cm=160)) == []         # the limit itself is allowed
    errs = _height_errors(check_show(_tall_show(171), max_height_cm=170))
    assert len(errs) == 1 and "лимита 170 см" in errs[0].message


def test_limit_above_ceiling_or_below_floor_is_refused():
    s = _tall_show(160)
    for bad in (201, 250, 19, 0, -5, 170.5, "abc", True):
        with pytest.raises(SafetyError):
            check_show(s, max_height_cm=bad)
    check_show(s, max_height_cm=200)
    check_show(s, max_height_cm=MIN_TAKEOFF_CM)
    assert resolve_max_height(None) == 150 and resolve_max_height(170) == 170 and resolve_max_height(170.0) == 170
    with pytest.raises(SafetyError):
        hop_mission(100, 3, max_height_cm=201)
    with pytest.raises(SafetyError):
        check_mission(hop_mission(100, 3), 201)
    with pytest.raises(SafetyError):
        preflight(hop_mission(100, 3), ip="127.0.0.1", whitelist={"127.0.0.1"}, volts=8.0, max_height_cm=250)


def test_raising_the_limit_does_not_bypass_other_checks():
    s = Show("x")
    s.drone(1).takeoff(100, 5).code(25, 4).set_z(160, 2)
    s.drone(2).takeoff(100, 5).code(26, 4)                  # 40 cm from drone 1: too close
    s.drone(3).takeoff(100, 5).code(999, 4)                 # outside the mat
    s.drone(4).takeoff(100, 5).set_z(201, 2)                # above even the 200 cm ceiling
    findings = check_show(s, max_height_cm=200)
    assert [f.drone for f in _height_errors(findings)] == [4]
    assert any(f.level == "error" and f.drone == 3 and "вне коврика" in f.message for f in findings)
    assert any(f.level == "warn" and "сближаются" in f.message for f in findings)
    assert any(f.level == "info" and "загрузка в дрон недоступна" in f.message for f in findings)
    # a mission: hover limit and unproven steps are still checked at the highest limit
    long_hover = Mission([MissionStep(CMD_TAKEOFF, 50, z_data(100)), MissionStep(CMD_MOVEZ, 160, z_data(100))])
    assert any("Зависание" in f.message for f in check_mission(long_hover, 200))
    for cmd in (CMD_MOVEXYZ,):                              # still not proven: refused at any limit (circle was flown, see PROVEN_CMDS)
        unproven = Mission([MissionStep(cmd, 50, bytes(12))])
        assert any("не проверен" in f.message for f in check_mission(unproven, 200))
    assert not _height_errors(check_mission(hop_mission(160, 3, max_height_cm=170), 170))


def test_check_mission_and_hop_mission_use_the_limit():
    m = hop_mission(160, 3, max_height_cm=170)
    assert m.max_height_cm == 160
    assert _height_errors(check_mission(m)) != []                    # default 150 flags it
    assert _height_errors(check_mission(m, 170)) == []
    with pytest.raises(SafetyError, match="20-150"):
        hop_mission(160, 3)                                          # default limit stays 150
    with pytest.raises(SafetyError, match="20-170"):
        hop_mission(171, 3, max_height_cm=170)
    assert hop_mission(200, 3, max_height_cm=200).max_height_cm == 200
    preflight(m, ip="127.0.0.1", whitelist={"127.0.0.1"}, volts=8.0, max_height_cm=170)
    with pytest.raises(SafetyError, match="Высота"):
        preflight(m, ip="127.0.0.1", whitelist={"127.0.0.1"}, volts=8.0)


# ---- moveXY: cell moves ---------------------------------------------------------------

GOLDEN = [  # calibrate 5 s / takeOff 50 cm 5 s / moveXY to cell 97 in 4 s / autoLand, verified on live drones
    "fa130003020400010032000000000000000000000000000058f9",
    "fa13000302040002006400013200000000000000000000008c71",
    "fa13000302040003008c00034001280000000000000000000b29",
    "fa13000302040004008c0002000000000000000000000000e69b",
]


def test_golden_frames_of_a_cell_move_mission():
    s = load_show_source("from litebee import Show\nshow = Show('g')\nd = show.drone(1)\n"
                         "d.calibrate(5)\nd.takeoff(50, 5)\nd.code(97, 4)\nd.land()\n")
    m = drone_to_mission(s.drones[1])
    assert [f.hex() for f in m.frames()] == GOLDEN
    assert m.checksum == 6
    by_hand = Mission([MissionStep(0, 50, bytes(12)), MissionStep(1, 100, z_data(50)),
                       MissionStep(CMD_MOVEXY, 140, xy_data(97)), MissionStep(2, 140, bytes(12))])
    assert [f.hex() for f in by_hand.frames()] == GOLDEN
    step = m.steps[2]
    assert step.data == bytes.fromhex("4001" "2800") + bytes(8)        # row 320 cm first, column 40 cm second
    assert step.xy_cm == (40, 320) and step.cell == 97 and m.first_move_xy == (40, 320) and m.has_moves


def test_xy_data_covers_the_mat_and_refuses_the_rest():
    import struct
    assert xy_data(0) == bytes(12)
    assert xy_data(11) == struct.pack("<HH", 0, 440) + bytes(8)        # last column of row 0: x = 440
    assert xy_data(12) == struct.pack("<HH", 40, 0) + bytes(8)         # first column of row 1: y = 40
    assert xy_data(143) == struct.pack("<HH", 440, 440) + bytes(8)
    for bad in (-1, 144, 999, 1.5, True):
        with pytest.raises(ValueError):
            xy_data(bad)


def test_only_proven_steps_can_be_packed():
    assert PROVEN_CMDS == {0, 1, 2, 3, 5, 12, 50}      # calibrate, takeOff, autoLand, moveXY, moveZ, circle, RGB
    off_cell = Mission([MissionStep(CMD_MOVEXY, 50, bytes([1, 0, 40, 0]) + bytes(8))])   # y = 1 cm
    assert any("не лежит на клетке" in f.message for f in check_mission(off_cell))
    assert check_mission(Mission([MissionStep(CMD_TAKEOFF, 50, z_data(50)), MissionStep(CMD_MOVEXY, 90, xy_data(97))])) == []


def _legs_show(*moves):
    s = Show("legs")
    d = s.drone(1)
    d.takeoff(100, 5)
    for cell, seconds in moves:
        d.code(cell, seconds)
    return s


def _speed_warnings(show):
    return [f for f in check_show(show, max_height_cm=150) if f.level == "warn" and "порога" in f.message]


def test_fast_leg_gets_a_warning_not_an_error():
    assert MAX_LEG_SPEED_CM_S == 100
    s = _legs_show((0, 3), (11, 2))                 # 440 cm in 2 s = 220 cm/s
    warns = _speed_warnings(s)
    assert len(warns) == 1 and warns[0].drone == 1 and "клетку 11" in warns[0].message and "220 см/с" in warns[0].message
    assert warns[0].line is not None
    assert not [f for f in check_show(s) if f.level == "error"]
    assert len(_speed_warnings(_legs_show((0, 3), (11, 4)))) == 1       # 110 cm/s is still above 100
    assert _speed_warnings(_legs_show((0, 3), (11, 5))) == []           # 88 cm/s
    assert _speed_warnings(_legs_show((0, 3), (5, 2))) == []            # 200 cm in 2 s: exactly 100 cm/s is allowed
    assert len(_speed_warnings(_legs_show((0, 3), (1, 0)))) == 1        # 40 cm in no time


def test_short_legs_and_standing_still_are_fine():
    assert _speed_warnings(_legs_show((5, 2), (5, 0.5), (6, 1))) == []  # same cell, then one 40 cm cell in 1 s
    assert _speed_warnings(_legs_show((5, 2), (6, 1), (5, 1))) == []


def test_cell_moves_get_an_info_about_the_start_position():
    f = [x for x in check_show(_legs_show((25, 3))) if x.level == "info"]
    assert len(f) == 1 and "клетку 25" in f[0].message and "50 см" in f[0].message
    assert not [x for x in check_show(_legs_show((25, 3))) if "загрузка в дрон недоступна" in x.message]


def test_position_problem_rules():
    assert MAX_START_DISTANCE_CM == 200
    first = 97                                       # x = 40, y = 320
    assert position_problem(first, 0, 0) == NO_FIX_MESSAGE
    assert "нет позиции" in NO_FIX_MESSAGE and "50 см" in NO_FIX_MESSAGE
    assert position_problem(first, 40, 320) is None
    assert position_problem(first, 240, 320) is None                    # exactly 200 cm
    why = position_problem(first, 241, 320)
    assert why and "клетке 97" in why and "на клетке 102" in why        # round(241/40) = 6, row 8
    assert "вне коврика" in position_problem(first, 900, 320)
    assert "на клетке 0" in position_problem(first, 0, 1)               # y = 1 is a fix, but 322 cm away
