"""Reference packers for LiteBee Go formation steps (12 data bytes + step time).

Everything here is a Python port of code found in the installed LiteBee Go app
(C:/Users/serzh/AppData/Local/Programs/LiteBee Go/resources):

  * GUI side   : gui/lib.min.js, extensions "litebeeWingFormation" and "litebeeStars"
                 (block -> array [cmdId, ...bytes] sent to the main process)
  * main side  : app.asar, formation handler `handle(e)` + class with appendCmdAndTime
  * 3D simulator: formation/3D/.../Managed/Assembly-CSharp.dll (the vendor's own decoder of the
                 same 12 data bytes; used here as an independent cross-check, see sim_decode())

Only cmds 0,1,2,3,5,50 are verified on a live drone.  Every other layout here is "certain from the
app code" (what LiteBee Go would put on the wire) but NOT verified against the drone firmware.

Conventions
  * time is in 0.1 s ticks; a step carries the CUMULATIVE end time of the drone's program
  * u16/i16 are little endian (JS Int16Array on x86 in the GUI, Uint16Array in the main process)
  * a mat cell is code = col + 12 * row, 40 cm; "row_cm" = 40*row is the FIRST position field,
    "col_cm" = 40*col the SECOND (verified live for moveXY)
  * every packer returns `bytes` of length 12 (data) and, where the step has its own time,
    a Step(cmd, dt_ticks, data) with dt_ticks the time the step ADDS to the program clock

Run `python step_packers.py` to execute the self-test and print the worked examples.
"""
import math
import struct
from collections import namedtuple

# ----------------------------------------------------------------------------------------------
# command ids (app.asar: class with `o.cmd={calibrate:0,...}`)
CMD = dict(calibrate=0, takeOff=1, autoLand=2, moveXY=3, speed=4, moveZ=5, yaw=6, local360=7,
           flip=8, jump=9, moveXYZ=10, atti=11, circle=12, circleAlt=13, RGB=50, int=51)
CMD_AROUND_D = 14      # known ONLY to the 3D simulator (TaskType.AroundD); the app never emits it

# GUI -> main process message ids (gui/lib.min.js `formation_*`)
MSG = dict(formation_flightNum=100, formation_calibration=101, formation_takeOff=102,
           formation_autoland=103, formation_move=104, formation_setZ=105, formation_sendMission=150,
           formation_start=151, formation_stop=152, formation_moveXYZ=153, formation_circle=154,
           formation_circleAlt=155, formation_RGB=156, formation_notCode_XYZ=157,
           formation_circle_XYZ=158, formation_moveN=159, formation_triangle=160,
           formation_square=161, formation_clear=162, formation_showFlightNum=163,
           formation_RGB_N=164, formation_RGB_value=165, formation_local360=166)

CELL_CM, GRID_W = 40, 12
Step = namedtuple("Step", "cmd dt_ticks data")          # data: 12 bytes; dt_ticks: time added to the clock


# ----------------------------------------------------------------------------------------------
# low level helpers (JS semantics)

def js_floor_ticks(seconds):
    """GUI: Math.floor(10 * seconds)  (same IEEE double arithmetic as JS)."""
    return math.floor(10 * seconds)


def i16_le(v):
    """GUI `_16To8` element: Int16Array([v]) -> 2 bytes LE.  Non-integers truncate, ints wrap mod 2^16."""
    v = int(v)                                    # truncation toward zero, like ToInt16
    return struct.pack("<H", v & 0xFFFF)


def gui_16to8(values):
    """gui/lib.min.js `_16To8`: list of numbers -> flat list of byte values (Int16Array bytes, LE)."""
    out = []
    for v in values:
        out.extend(i16_le(v))
    return out


def u16_from_bytes(lo, hi):
    """main process `u.arr8ToU16([lo, hi])[0]`."""
    return lo | (hi << 8)


def trans_pos(cell):
    """GUI `_transPos`: cell -> [40*parseInt(cell/12), (cell%12)*40] = [row_cm, col_cm]."""
    cell = int(cell)
    return [CELL_CM * (cell // GRID_W), (cell % GRID_W) * CELL_CM]


def circle_centre_cm(cell1, cell2):
    """GUI circle/circleZ: centre = floor(0.5*(a+b)) per axis over the two cells' [row_cm, col_cm]."""
    (l, u), (h, p) = trans_pos(cell1), trans_pos(cell2)
    return [math.floor(0.5 * (l + h)), math.floor(0.5 * (u + p))]


def _dir(rotate):
    """GUI ROTATE menu: 'cw' -> 0, 'ccw' -> 1 (d=['cw','ccw'], d.indexOf)."""
    if rotate in ("cw", 0):
        return 0
    if rotate in ("ccw", 1):
        return 1
    raise ValueError("rotate must be 'cw'/'ccw' (0/1)")


def _check_count(count):
    if not (isinstance(count, int) and 1 <= count <= 255):
        raise ValueError("count (half turns) must be an integer 1..255 (it is one data byte)")


def _pad(b):
    b = bytes(b)
    assert len(b) <= 12
    return b + bytes(12 - len(b))


# ----------------------------------------------------------------------------------------------
# verified steps (kept here so that tests can compare the unverified ones against them)

def pack_move_xy(row_cm, col_cm):
    """cmd 3 moveXY (VERIFIED LIVE): u16 row_cm, u16 col_cm, 8 zero bytes."""
    return _pad(i16_le(row_cm) + i16_le(col_cm))


def pack_height(z_cm):
    """cmd 1 takeOff / cmd 5 moveZ (VERIFIED LIVE): u16 z_cm, 10 zero bytes."""
    return _pad(i16_le(z_cm))


# ----------------------------------------------------------------------------------------------
# cmd 10  moveXYZ     (GUI block "move to QR code [CODE], meanwhile fly to the height [Z]", codeZ)

def pack_move_xyz(row_cm, col_cm, z_cm):
    """cmd 10 moveXYZ data: i16 row_cm, i16 col_cm, i16 z_cm (ABSOLUTE height), 6 zero bytes.

    Source: main `formation_moveXYZ`: data=[e3..e8]+6 zeros, e=[153,Tlo,Thi, GUI _16To8([row,col,z])].
    """
    return _pad(i16_le(row_cm) + i16_le(col_cm) + i16_le(z_cm))


def step_move_xyz_cell(cell, z_cm, seconds):
    """Scratch codeZ(CODE=cell, Z=z_cm, TIME=seconds) -> Step(10, floor(10*seconds), data)."""
    row, col = trans_pos(cell)
    return Step(CMD["moveXYZ"], js_floor_ticks(seconds), pack_move_xyz(row, col, z_cm))


def step_move_xyz_xy(x_cm, y_cm, z_cm, seconds):
    """litebeeStars moveXYZ(X, Y, Z, TIME): GUI sends _16To8([T, Y, X, Z]) -> row_cm=Y, col_cm=X."""
    return Step(CMD["moveXYZ"], js_floor_ticks(seconds), pack_move_xyz(y_cm, x_cm, z_cm))


def step_not_code_xyz(seconds_int, row_cm, col_cm, z_cm):
    """main `formation_notCode_XYZ` (157): time = 10*e[1] (whole seconds!), data=[e2..e7]+zeros.
    No block in the installed GUI emits it; the 6 bytes are assumed to be the same 3 x i16 as moveXYZ
    (inferred)."""
    return Step(CMD["moveXYZ"], 10 * int(seconds_int), pack_move_xyz(row_cm, col_cm, z_cm))


# ----------------------------------------------------------------------------------------------
# cmd 12  circle      (GUI block "[ROTATE] circle [COUNT] semicycle, centre between [CODE1] and [CODE2],
#                      execute for [TIME] seconds")

def pack_circle(centre_row_cm, centre_col_cm, half_turn_ticks, count, direction):
    """cmd 12 circle data (12 bytes):
        0-1 i16 centre row_cm      2-3 i16 centre col_cm
        4-5 u16 T = ticks of ONE half turn (the Scratch TIME x 10)
        6   u8  count (number of half turns)      7  0
        8   u8  direction (0 = cw, 1 = ccw)       9-11 zeros
    Source: main `formation_circle`: ie=[e5,e6,e7,e8,e3,e4,e2,0,e1,0,0,0]."""
    _check_count(count)
    return _pad(i16_le(centre_row_cm) + i16_le(centre_col_cm) + struct.pack("<H", half_turn_ticks & 0xFFFF)
                + bytes([count, 0, _dir(direction)]))


def step_circle(cell1, cell2, count, seconds, rotate="cw"):
    """Scratch circle(CODE1, CODE2, ROTATE, COUNT, TIME).

    IMPORTANT (main process): the step adds T*count ticks to the program clock, T = floor(10*TIME);
    i.e. TIME is the duration of ONE half turn, the whole step lasts COUNT x TIME."""
    cr, cc = circle_centre_cm(cell1, cell2)
    t = js_floor_ticks(seconds)
    return Step(CMD["circle"], t * count, pack_circle(cr, cc, t, count, rotate))


def step_circle_xy(x_cm, y_cm, count, seconds, rotate="cw"):
    """litebeeStars circleXY(X, Y, ROTATE, COUNT, TIME): GUI sends _16To8([T, Y, X]) -> centre row=Y, col=X."""
    t = js_floor_ticks(seconds)
    return Step(CMD["circle"], t * count, pack_circle(y_cm, x_cm, t, count, rotate))


# ----------------------------------------------------------------------------------------------
# cmd 13  circleAlt   (GUI block "[ROTATE] circle a semicycle, centre between [CODE1] and [CODE2],
#                      meanwhile fly to the height [Z], execute for [TIME] seconds", circleZ)

def pack_circle_alt(centre_row_cm, centre_col_cm, ticks, z_cm, direction):
    """cmd 13 circleAlt data (12 bytes):
        0-1 i16 centre row_cm   2-3 i16 centre col_cm
        4-5 u16 T = ticks of the (single) half turn = the whole step
        6-7 i16 target height z_cm (ABSOLUTE per the 3D simulator; the Chinese doc says "rise by")
        8   u8  direction (0 = cw, 1 = ccw)       9-11 zeros
    Source: main `formation_circleAlt`: se=[e4,e5,e6,e7,e2,e3,e8,e9,e1,0,0,0]."""
    return _pad(i16_le(centre_row_cm) + i16_le(centre_col_cm) + struct.pack("<H", ticks & 0xFFFF)
                + i16_le(z_cm) + bytes([_dir(direction)]))


def step_circle_alt(cell1, cell2, z_cm, seconds, rotate="cw"):
    """Scratch circleZ(CODE1, CODE2, ROTATE, Z, TIME): exactly ONE half turn, step time = floor(10*TIME)."""
    cr, cc = circle_centre_cm(cell1, cell2)
    t = js_floor_ticks(seconds)
    return Step(CMD["circleAlt"], t, pack_circle_alt(cr, cc, t, z_cm, rotate))


def step_circle_alt_xy(x_cm, y_cm, z_cm, seconds, rotate="cw"):
    """litebeeStars circleXYZ(X, Y, ROTATE, Z, TIME): GUI _16To8([T, Y, X, Z]) -> same as circleAlt."""
    t = js_floor_ticks(seconds)
    return Step(CMD["circleAlt"], t, pack_circle_alt(y_cm, x_cm, t, z_cm, rotate))


def step_circle_xyz_158(ticks, direction, centre_row_cm, centre_col_cm, z_cm):
    """main `formation_circle_XYZ` (158): cmd 13, time = e[1] (raw ticks, NOT x10), same data as circleAlt.
    No block of the installed GUI emits it (inferred argument meaning)."""
    return Step(CMD["circleAlt"], int(ticks), pack_circle_alt(centre_row_cm, centre_col_cm, ticks, z_cm, direction))


# ----------------------------------------------------------------------------------------------
# cmd 14 (simulator only)

def pack_around_d(centre_row_cm, centre_col_cm, ticks, z_cm, direction, degree):
    """cmd 14 as the 3D simulator decodes it: circleAlt layout + i16 degree at bytes 9-10.
    The app never emits it; whether the firmware has it is unknown.  DO NOT FLY."""
    return _pad(pack_circle_alt(centre_row_cm, centre_col_cm, ticks, z_cm, direction)[:9] + i16_le(degree))


# ----------------------------------------------------------------------------------------------
# cmd 7  local360     (method local360 exists in the Wing extension but has NO block; litebeeStars neither)

def pack_local360(direction):
    """cmd 7 data: byte0 = direction (0 cw / 1 ccw), 11 zero bytes.  Source: main `formation_local360`."""
    return _pad(bytes([_dir(direction)]))


def step_local360(rotate, seconds):
    """GUI local360(ROTATE, TIME) -> main: time = u16(e2,e3) = floor(10*TIME); meaning of the turn is inferred."""
    return Step(CMD["local360"], js_floor_ticks(seconds), pack_local360(rotate))


# ----------------------------------------------------------------------------------------------
# steps with NO producer in the app: speed 4, yaw 6, flip 8, jump 9, atti 11

def pack_unknown(name):
    raise NotImplementedError(
        f"cmd '{name}': neither the GUI nor the main process of LiteBee Go ever builds this step, and the "
        f"3D simulator decodes it as a parameterless no-op.  The data layout cannot be derived from the app.")


for _n in ("speed", "yaw", "flip", "jump", "atti"):
    globals()[f"pack_{_n}"] = (lambda n: (lambda *a, **k: pack_unknown(n)))(_n)


# ----------------------------------------------------------------------------------------------
# RGB / int ("ext" steps): they are NOT part of the motion clock; the app collects them in a separate list,
# gives them time = (motion clock at that moment) - 3 (or -5) ticks (0 if the clock <= 8) and appends them
# AFTER all motion steps with indices continuing the motion steps' numbering.

COLOR_NAMES = ["black", "red", "green", "yellow", "blue", "purple", "cyan", "white"]


def rgb_bits(index):
    """GUI colour menu index 0..7 -> (r, g, b) with bit0=R, bit1=G, bit2=B -> 255 each."""
    return (255 if index & 1 else 0, 255 if index & 2 else 0, 255 if index & 4 else 0)


def pack_rgb_wing(r, g, b):
    """cmd 50 RGB, Wing layout (VERIFIED LIVE): [5,0,2,255,g,r,b,0,0,0,0,0] -- NOTE order g, r, b.
    Source: main `formation_RGB_value` with e[1]==1 (the Wing GUI always sends 1)."""
    return _pad(bytes([5, 0, 2, 255, g, r, b]))


def pack_rgb_n_layout(r, g, b):
    """Layout [10,0,3,r,g,b,255 x6]  (order r, g, b).  Used by main `formation_RGB_N` and by
    `formation_RGB_value` with e[1]!=1 (litebeeStars GUI sends 0).  cmd id = 50, or 51 (`int`) when
    sendMission was called with flag 1 (litebeeStars).  NOT verified."""
    return _pad(bytes([10, 0, 3, r, g, b, 255, 255, 255, 255, 255, 255]))


def pack_rgb_test(which):
    """main `formation_RGB` (156) with e[1]=254/255 (hidden test blocks): [5,0,2,2,128,33,46|47,0...]."""
    if which not in (254, 255):
        raise ValueError
    return _pad(bytes([5, 0, 2, 2, 128, 33, 46 if which == 254 else 47]))


def rgb_ext_time(motion_clock_ticks, variant="value"):
    """Time field of an ext step: clock>8 ? clock-3 : 0 for RGB_value / RGB_N, clock-5 for formation_RGB."""
    off = 5 if variant == "rgb156" else 3
    return motion_clock_ticks - off if motion_clock_ticks > 8 else 0


# ----------------------------------------------------------------------------------------------
# A port of the app's program builder: motion list + ext list, and the frames sent on missionSend

class AppProgram:
    """Mimics `formation.appendCmdAndTime`, the ext (RGB) lists and the `formation_sendMission` loop
    for ONE drone.  frames() returns the 19-byte step records [total,0,idx,0,tlo,thi,cmd,*data]."""

    def __init__(self, stars_int_flag=False):
        self.steps = []          # (cmd, cumulative_end_ticks, data)
        self.ext = []            # (time, data, kind)
        self.clock = 0
        self.stars_int_flag = stars_int_flag      # sendMission flag 1 -> ext cmd 51

    def add(self, step):
        self.clock += step.dt_ticks
        self.steps.append((step.cmd, self.clock, bytes(step.data)))
        return self

    def rgb_value_wing(self, r, g, b):
        self.ext.append((rgb_ext_time(self.clock), pack_rgb_wing(r, g, b)))
        return self

    def rgb_wing_index(self, index):
        return self.rgb_value_wing(*rgb_bits(index))

    def frames(self):
        total = len(self.steps) + len(self.ext)
        out = []
        for i, (cmd, t, data) in enumerate(self.steps, 1):
            out.append([total, 0, i, 0, t % 256, t // 256, cmd, *data])
        ext_cmd = CMD["int"] if self.stars_int_flag else CMD["RGB"]
        for j, (t, data) in enumerate(self.ext, 1):
            out.append([total, 0, len(self.steps) + j, 0, t % 256, t // 256, ext_cmd, *data])
        return out


# ----------------------------------------------------------------------------------------------
# GUI emulation -> `e` arrays, and a port of the main-process switch (cross-check of the packers)

def gui_codeZ(cell, z, seconds):
    row, col = trans_pos(cell)
    return [MSG["formation_moveXYZ"]] + gui_16to8([js_floor_ticks(seconds), row, col, z])


def gui_circle(cell1, cell2, count, seconds, rotate):
    cr, cc = circle_centre_cm(cell1, cell2)
    return [MSG["formation_circle"], _dir(rotate), count] + gui_16to8([js_floor_ticks(seconds), cr, cc])


def gui_circleZ(cell1, cell2, z, seconds, rotate):
    cr, cc = circle_centre_cm(cell1, cell2)
    return [MSG["formation_circleAlt"], _dir(rotate)] + gui_16to8([js_floor_ticks(seconds), cr, cc, z])


def gui_local360(seconds, rotate):
    return [MSG["formation_local360"], _dir(rotate)] + gui_16to8([js_floor_ticks(seconds)])


def gui_stars_moveXYZ(x, y, z, seconds):
    return [MSG["formation_moveXYZ"]] + gui_16to8([js_floor_ticks(seconds), y, x, z])


def gui_stars_circleXY(x, y, rotate, count, seconds):
    return [MSG["formation_circle"], _dir(rotate), count] + gui_16to8([js_floor_ticks(seconds), y, x])


def gui_stars_circleXYZ(x, y, rotate, z, seconds):
    return [MSG["formation_circleAlt"], _dir(rotate)] + gui_16to8([js_floor_ticks(seconds), y, x, z])


def main_handle(e):
    """Port of the relevant `case`s of the main-process `handle(e)`; returns Step (cmd, dt, data)."""
    k = e[0]
    if k == MSG["formation_moveXYZ"]:
        t = u16_from_bytes(e[1], e[2])
        return Step(CMD["moveXYZ"], t, bytes([e[3], e[4], e[5], e[6], e[7], e[8]] + [0] * 6))
    if k == MSG["formation_notCode_XYZ"]:
        return Step(CMD["moveXYZ"], 10 * e[1], bytes([e[2], e[3], e[4], e[5], e[6], e[7]] + [0] * 6))
    if k == MSG["formation_circle"]:
        t = u16_from_bytes(e[3], e[4])
        return Step(CMD["circle"], t * e[2], bytes([e[5], e[6], e[7], e[8], e[3], e[4], e[2], 0, e[1], 0, 0, 0]))
    if k == MSG["formation_circleAlt"]:
        t = u16_from_bytes(e[2], e[3])
        return Step(CMD["circleAlt"], t, bytes([e[4], e[5], e[6], e[7], e[2], e[3], e[8], e[9], e[1], 0, 0, 0]))
    if k == MSG["formation_circle_XYZ"]:
        ue = gui_16to8([e[1]])
        return Step(CMD["circleAlt"], e[1], bytes([e[3], e[4], e[5], e[6], ue[0], ue[1], e[7], e[8], e[2], 0, 0, 0]))
    if k == MSG["formation_local360"]:
        return Step(CMD["local360"], u16_from_bytes(e[2], e[3]), bytes([e[1]] + [0] * 11))
    if k == MSG["formation_move"]:
        return Step(CMD["moveXY"], u16_from_bytes(e[1], e[2]), bytes([e[3], e[4], e[5], e[6]] + [0] * 8))
    raise NotImplementedError(k)


# ----------------------------------------------------------------------------------------------
# the vendor's 3D simulator decoder (Assembly-CSharp.dll, FormationUtility.GetTaskData & co)

def _i16(b, off):
    v = b[off] | (b[off + 1] << 8)
    return v - 65536 if v >= 32768 else v


def sim_decode(cmd, data):
    """What the vendor simulator reads from the 12 data bytes (cm, with Unity axes x=col, z=row, y=height)."""
    d = bytes(data)
    if cmd in (1, 2, 5):
        return {"height_cm": _i16(d, 0)}
    if cmd in (3, 10):
        r = {"row_cm": _i16(d, 0), "col_cm": _i16(d, 2)}
        if cmd == 10:
            r["height_cm"] = _i16(d, 4)        # for cmd 3 the simulator ignores bytes 4-5 (keeps its height)
        return r
    if cmd in (12, 13, CMD_AROUND_D):
        r = {"centre_row_cm": _i16(d, 0), "centre_col_cm": _i16(d, 2), "clockwise": d[8] == 0}
        if cmd == 12:
            r["half_turns"] = _i16(d, 6)       # bytes 4-5 (T) are ignored by the simulator
        else:
            r["target_height_cm"] = _i16(d, 6)
        if cmd == CMD_AROUND_D:
            r["degree"] = _i16(d, 9)
        return r
    return {}


# ----------------------------------------------------------------------------------------------
# self-test

def _hx(b):
    return " ".join(f"{x:02x}" for x in b)


def _check(name, step, want_cmd, want_dt, want_hex, show=True):
    want = bytes.fromhex(want_hex.replace(" ", ""))
    assert len(want) == 12, name
    assert step.cmd == want_cmd, (name, step.cmd, want_cmd)
    assert step.dt_ticks == want_dt, (name, step.dt_ticks, want_dt)
    assert bytes(step.data) == want, (name, _hx(step.data), _hx(want))
    if show:
        print(f"  OK  {name:<58} cmd={step.cmd:<2} +{step.dt_ticks:>4} ticks  data={_hx(step.data)}")


def self_test(verbose=True):
    p = print if verbose else (lambda *a, **k: None)

    p("moveXYZ (cmd 10)")
    # cell 85 = row 7, col 1 -> row_cm 280 (0x0118), col_cm 40 (0x28), z 130 (0x82); shows: code_z(85,130,2)
    _check("codeZ(85, z=130, 2 s)", step_move_xyz_cell(85, 130, 2), 10, 20,
           "18 01 28 00 82 00 00 00 00 00 00 00", verbose)
    # cell 111 = row 9, col 3 -> 360 (0x168), 120 (0x78), z 80 (0x50); shows: code_z(111,80,2)
    _check("codeZ(111, z=80, 2 s)", step_move_xyz_cell(111, 80, 2), 10, 20,
           "68 01 78 00 50 00 00 00 00 00 00 00", verbose)
    # cell 0 z=120 3 s (my_people_my_country_5)
    _check("codeZ(0, z=120, 3 s)", step_move_xyz_cell(0, 120, 3), 10, 30,
           "00 00 00 00 78 00 00 00 00 00 00 00", verbose)
    # fractional seconds floor like JS: 2.5 s -> 25
    _check("codeZ(94, z=120, 2.5 s)", step_move_xyz_cell(94, 120, 2.5), 10, 25,
           "18 01 90 01 78 00 00 00 00 00 00 00", verbose)       # 94 = row 7, col 10 -> 280, 400
    # Stars: X=100 (col), Y=200 (row), Z=150 -> row first
    _check("Stars moveXYZ(X=100,Y=200,Z=150, 4 s)", step_move_xyz_xy(100, 200, 150, 4), 10, 40,
           "c8 00 64 00 96 00 00 00 00 00 00 00", verbose)

    p("circle (cmd 12)  -- step time = T * count")
    # show: circle(2, 66, 77, 13, 'cw'): centre ((200+240)/2, (240+200)/2) = (220, 220); T=130; 2 half turns => 260 ticks
    _check("circle(66,77,'cw',count=2,TIME=13)", step_circle(66, 77, 2, 13, "cw"), 12, 260,
           "dc 00 dc 00 82 00 02 00 00 00 00 00", verbose)
    # show: circle(1, 89, 89, 8, 'cw'): cell 89 = row 7, col 5 -> (280, 200); T=80; 1 half turn
    _check("circle(89,89,'cw',count=1,TIME=8)", step_circle(89, 89, 1, 8, "cw"), 12, 80,
           "18 01 c8 00 50 00 01 00 00 00 00 00", verbose)
    # show: circle(2, 66, 77, 6, 'ccw'): T=60, dir byte = 1
    _check("circle(66,77,'ccw',count=2,TIME=6)", step_circle(66, 77, 2, 6, "ccw"), 12, 120,
           "dc 00 dc 00 3c 00 02 00 01 00 00 00", verbose)
    # show: circle(2, 66, 66, 10, 'cw'): centre = cell 66 itself = (row 200, col 240)
    _check("circle(66,66,'cw',count=2,TIME=10)", step_circle(66, 66, 2, 10, "cw"), 12, 200,
           "c8 00 f0 00 64 00 02 00 00 00 00 00", verbose)
    # official doc example: litebeeWingFormation_circle([66, 77, 0, 2, 15])
    _check("doc example circle(66,77,cw,2,15)", step_circle(66, 77, 2, 15, 0), 12, 300,
           "dc 00 dc 00 96 00 02 00 00 00 00 00", verbose)

    p("circleAlt (cmd 13)  -- one half turn, step time = T")
    # official doc example: litebeeWingFormation_circleZ([66, 77, 0, 150, 15])
    _check("doc example circleZ(66,77,cw,Z=150,15 s)", step_circle_alt(66, 77, 150, 15, "cw"), 13, 150,
           "dc 00 dc 00 96 00 96 00 00 00 00 00", verbose)
    _check("circleZ(66,77,ccw,Z=100,10 s)", step_circle_alt(66, 77, 100, 10, "ccw"), 13, 100,
           "dc 00 dc 00 64 00 64 00 01 00 00 00", verbose)
    _check("Stars circleXYZ(X=240,Y=200,cw,Z=120,8 s)", step_circle_alt_xy(240, 200, 120, 8, "cw"), 13, 80,
           "c8 00 f0 00 50 00 78 00 00 00 00 00", verbose)

    p("local360 (cmd 7)")
    _check("local360(cw, 5 s)", step_local360("cw", 5), 7, 50, "00 00 00 00 00 00 00 00 00 00 00 00", verbose)
    _check("local360(ccw, 3 s)", step_local360("ccw", 3), 7, 30, "01 00 00 00 00 00 00 00 00 00 00 00", verbose)

    p("RGB / ext steps (cmd 50 verified; the rest NOT)")
    assert pack_rgb_wing(255, 0, 0) == bytes.fromhex("050002ff00ff00 0000000000".replace(" ", ""))
    assert pack_rgb_wing(0, 255, 0) == bytes.fromhex("050002ffff00000000000000")
    assert pack_rgb_wing(100, 20, 30) == bytes([5, 0, 2, 255, 20, 100, 30, 0, 0, 0, 0, 0])
    p("  OK  Wing RGB red  :", _hx(pack_rgb_wing(255, 0, 0)))
    p("  OK  Wing RGB green:", _hx(pack_rgb_wing(0, 255, 0)))
    assert pack_rgb_n_layout(1, 2, 3) == bytes([10, 0, 3, 1, 2, 3, 255, 255, 255, 255, 255, 255])
    assert pack_rgb_n_layout(255, 0, 0) == bytes.fromhex("0a0003ff0000ffffffffffff")
    p("  OK  RGB_N layout  :", _hx(pack_rgb_n_layout(255, 0, 0)))
    assert pack_rgb_test(254) == bytes([5, 0, 2, 2, 128, 33, 46, 0, 0, 0, 0, 0])
    assert rgb_ext_time(8) == 0 and rgb_ext_time(9) == 6 and rgb_ext_time(50) == 47
    assert rgb_ext_time(50, "rgb156") == 45
    p("  OK  rgb ext time: clock 50 -> 47 (RGB_value), 45 (formation_RGB); clock<=8 -> 0")

    p("cross-check: GUI array -> main switch == direct packers, and the vendor 3D decoder reads the inputs back")
    cases = [
        (gui_codeZ(85, 130, 2), step_move_xyz_cell(85, 130, 2)),
        (gui_codeZ(111, 80, 2), step_move_xyz_cell(111, 80, 2)),
        (gui_circle(66, 77, 2, 13, "cw"), step_circle(66, 77, 2, 13, "cw")),
        (gui_circle(89, 89, 1, 8, "cw"), step_circle(89, 89, 1, 8, "cw")),
        (gui_circle(66, 66, 2, 10, "ccw"), step_circle(66, 66, 2, 10, "ccw")),
        (gui_circleZ(66, 77, 150, 15, "cw"), step_circle_alt(66, 77, 150, 15, "cw")),
        (gui_circleZ(66, 77, 100, 10, "ccw"), step_circle_alt(66, 77, 100, 10, "ccw")),
        (gui_local360(5, "ccw"), step_local360("ccw", 5)),
        (gui_stars_moveXYZ(100, 200, 150, 4), step_move_xyz_xy(100, 200, 150, 4)),
        (gui_stars_circleXY(240, 200, "cw", 2, 7), step_circle_xy(240, 200, 2, 7, "cw")),
        (gui_stars_circleXYZ(240, 200, "ccw", 120, 8), step_circle_alt_xy(240, 200, 120, 8, "ccw")),
    ]
    for e, direct in cases:
        via_main = main_handle(e)
        assert via_main == direct, (e, via_main, direct)
    p(f"  OK  {len(cases)} GUI->main round trips identical")

    s = step_move_xyz_cell(85, 130, 2)
    assert sim_decode(10, s.data) == {"row_cm": 280, "col_cm": 40, "height_cm": 130}
    s = step_circle(66, 77, 2, 13, "ccw")
    assert sim_decode(12, s.data) == {"centre_row_cm": 220, "centre_col_cm": 220, "clockwise": False, "half_turns": 2}
    s = step_circle_alt(66, 77, 150, 15, "cw")
    assert sim_decode(13, s.data) == {"centre_row_cm": 220, "centre_col_cm": 220, "clockwise": True,
                                      "target_height_cm": 150}
    assert sim_decode(14, pack_around_d(220, 220, 100, 100, "cw", 90))["degree"] == 90
    p("  OK  vendor 3D-simulator decode of the bytes returns the packer inputs")

    p("verified steps for reference (must match litebee/mission.py)")
    assert pack_move_xy(280, 40) == bytes.fromhex("1801 2800 0000000000000000".replace(" ", ""))
    assert pack_height(100) == bytes([100, 0] + [0] * 10)
    p("  OK  moveXY / takeOff / moveZ")

    p("unverified-and-underivable steps")
    for n in ("speed", "yaw", "flip", "jump", "atti"):
        try:
            globals()[f"pack_{n}"]()
        except NotImplementedError:
            p(f"  OK  pack_{n} -> NotImplementedError (no producer in the app)")
        else:
            raise AssertionError(n)

    p("whole-program order check (calibrate, takeOff, RGB, codeZ, circle, RGB, land): app puts RGB steps last")
    prog = AppProgram()
    prog.add(Step(0, 50, bytes(12))).add(Step(1, 50, pack_height(100)))
    prog.rgb_wing_index(2)                                          # green, clock = 100 -> ext time 97
    prog.add(step_move_xyz_cell(85, 130, 2))
    prog.add(step_circle(66, 77, 2, 13, "cw"))
    prog.rgb_wing_index(4)                                          # blue, clock = 100+20+260 = 380 -> 377
    prog.add(Step(2, 0, bytes(12)))
    fr = prog.frames()
    assert [f[2] for f in fr] == [1, 2, 3, 4, 5, 6, 7]
    assert [f[6] for f in fr] == [0, 1, 10, 12, 2, 50, 50]
    assert fr[3][4] + fr[3][5] * 256 == 380 and fr[5][4] + fr[5][5] * 256 == 97 and fr[6][4] + fr[6][5] * 256 == 377
    assert all(f[0] == 7 for f in fr)
    p("  OK  program frames: step times (ticks) =", [f[4] + 256 * f[5] for f in fr], " cmds =", [f[6] for f in fr])
    p("      checksum (sum of cmd bytes) =", sum(f[6] for f in fr))
    return True


if __name__ == "__main__":
    ok = self_test(True)
    print("\nALL SELF-TESTS PASSED" if ok else "FAILED")
