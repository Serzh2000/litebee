"""One-cell move test on the QR mat for a single LiteBee Wing drone.

Mission = calibrate -> takeOff -> moveXY (to a neighbouring mat cell) -> autoLand.
moveXY data layout (read from LiteBee Go): [y_lo, y_hi, x_lo, x_hi] + 8 zero bytes,
y = 40 * row, x = 40 * col of the target cell (cell = col + 12 * row), absolute
mat coordinates in cm; the step time is the cumulative END time in 0.1 s.

Without --go the mission is only uploaded and its checksum verified; the motors
are not started. Only cells within one step of --from are accepted.

usage: python drone_move.py --pc 192.168.13.100 --drone 192.168.13.104 --from-cell 96 --to-cell 97 [--go]
"""
import argparse
import os
import struct
import time

import drone_probe as dp
import drone_hop as hop

CMD_CALIBRATE, CMD_TAKEOFF, CMD_AUTOLAND, CMD_MOVEXY = 0, 1, 2, 3
ALLOWED = {CMD_CALIBRATE, CMD_TAKEOFF, CMD_AUTOLAND, CMD_MOVEXY}


def cell_rc(cell):
    return divmod(cell, 12)  # (row, col)


def build_mission(from_cell, to_cell, height_cm, move_s, calibrate_s=5, takeoff_s=5):
    assert 0 <= from_cell < 144 and 0 <= to_cell < 144
    (r0, c0), (r1, c1) = cell_rc(from_cell), cell_rc(to_cell)
    assert abs(r1 - r0) + abs(c1 - c0) == 1, "target must be an adjacent cell"
    assert 20 <= height_cm <= hop.MAX_HEIGHT_CM and 2 <= move_s <= 8
    z = list(struct.pack("<H", int(height_cm)))
    target = list(struct.pack("<HH", 40 * r1, 40 * c1)) + [0] * 8
    steps, now = [], 0
    for cmd, secs, data in (
        (CMD_CALIBRATE, calibrate_s, [0] * 12),
        (CMD_TAKEOFF, takeoff_s, z + [0] * 10),
        (CMD_MOVEXY, move_s, target),
        (CMD_AUTOLAND, 0, [0] * 12),
    ):
        now += int(secs * 10)
        steps.append((cmd, now, data))
    assert {c for c, _, _ in steps} <= ALLOWED
    frames = []
    for i, (cmd, t, data) in enumerate(steps, 1):
        step = [len(steps), 0, i, 0, t & 255, t >> 8, cmd, *data]
        assert len(step) == 19
        frames.append(dp.frame([19, 0, 3, 2, *step]))
    return frames, sum(c for c, _, _ in steps), now / 10, (40 * r1, 40 * c1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", required=True)
    ap.add_argument("--drone", required=True)
    ap.add_argument("--from-cell", type=int, required=True)
    ap.add_argument("--to-cell", type=int, required=True)
    ap.add_argument("--height", type=int, default=50)
    ap.add_argument("--move", type=float, default=4, help="seconds for the move")
    ap.add_argument("--min-volts", type=float, default=7.4)
    ap.add_argument("--go", action="store_true")
    args = ap.parse_args()

    frames, expected, total, (ty, tx) = build_mission(
        args.from_cell, args.to_cell, args.height, args.move)
    print(f"[move] cell {args.from_cell} -> {args.to_cell}: target y={ty} x={tx} cm, "
          f"~{total:.0f} s, height {args.height} cm, expected checksum {expected}")
    if os.path.exists(hop.LAND_FLAG):
        os.remove(hop.LAND_FLAG)

    fy, fx = 40 * cell_rc(args.from_cell)[0], 40 * cell_rc(args.from_cell)[1]
    link = hop.Link(args.pc, args.drone)
    started = finished = landed_by_itself = False
    try:
        time.sleep(1.5)
        t = link.snapshot()
        print(f"[move] telemetry: {t}")
        if not t or t["volts"] < args.min_volts:
            raise SystemExit(f"battery {t.get('volts')} V is below {args.min_volts} V, not flying")
        link.send(dp.frame([1, 0, 3, 0, 1]))
        time.sleep(0.3)
        for f in frames:
            link.send(f)
            time.sleep(0.02)
        time.sleep(1.2)
        got = link.snapshot().get("checksum")
        print(f"[move] drone checksum {got} ({'OK' if got == expected else 'MISMATCH'})")
        if got != expected:
            raise SystemExit("mission was not accepted as sent, not starting")
        if not args.go:
            print("[move] upload verified; motors NOT started (no --go)")
            return
        clock = link.snapshot().get("clock")
        start = 0.1 * (clock + 300) if clock else dp.CLOCK[0] + 30
        link.send(dp.frame([5, 0, 2, 8, 1, *struct.pack("<I", int(start))]))
        started = True
        print("[move] START sent")
        deadline, seen_running, last = time.time() + total + 20, False, None
        while time.time() < deadline and not link.lost:
            if os.path.exists(hop.LAND_FLAG):
                print("[move] LAND_NOW found")
                break
            s = link.snapshot()
            state = (s.get("running"), s.get("z"), s.get("volts"), s.get("x"), s.get("y"))
            if state != last:
                last = state
                print(f"[move] running={state[0]} z={state[1]} volts={state[2]} x={state[3]} y={state[4]}")
            seen_running |= bool(s.get("running"))
            # fenced area: the two cells +-70 cm; leaving it (once a fix exists) means land now
            if s.get("z", 0) > 25 and (s.get("x") or s.get("y")):
                lo_y, hi_y = min(fy, ty) - 70, max(fy, ty) + 70
                lo_x, hi_x = min(fx, tx) - 70, max(fx, tx) + 70
                if not (lo_y <= s["y"] <= hi_y and lo_x <= s["x"] <= hi_x):
                    print(f"[move] OUT OF FENCE x={s['x']} y={s['y']}, landing")
                    break
            if seen_running and not s.get("running"):
                print("[move] mission finished")
                finished = True
                break
            time.sleep(0.1)
        if finished:  # the mission ends while the drone is still landing: let it land by itself first
            end = time.time() + 12
            while time.time() < end and not link.lost and (link.snapshot().get("z") or 0) > 3:
                time.sleep(0.2)
            s = link.snapshot()
            print(f"[move] after mission: z={s.get('z')} x={s.get('x')} y={s.get('y')} running={s.get('running')}")
            landed_by_itself = (s.get("z") or 0) <= 3
        if link.lost:
            print("[move] connection to the drone was lost")
    finally:
        if started and not (finished and landed_by_itself):
            for _ in range(3):
                try:
                    link.send(hop.ALL_AUTOLAND)
                except OSError:
                    break
                time.sleep(0.1)
            print("[move] all_autoLand sent as a safety net")
            time.sleep(2)
        elif started:
            print("[move] drone landed by itself, no extra land command sent")
        link.stop.set()


if __name__ == "__main__":
    main()
