"""Ground-only check: does the drone get a mat position after the calibrate step?

Mission = calibrate (5 s) -> RGB blue (marker, so the checksum is not 0). No takeoff step.
If z ever rises above 10 cm the emergency landing is sent at once.

usage: python drone_calib.py --pc 192.168.13.100 --drone 192.168.13.108
"""
import argparse
import struct
import time

import drone_probe as dp
import drone_hop as hop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", required=True)
    ap.add_argument("--drone", required=True)
    args = ap.parse_args()

    steps = [(0, 50, [0] * 12), (50, 60, [5, 0, 2, 255, 0, 0, 255, 0, 0, 0, 0, 0])]  # G=0 R=0 B=255
    frames = [dp.frame([19, 0, 3, 2, len(steps), 0, i, 0, t & 255, t >> 8, cmd, *data])
              for i, (cmd, t, data) in enumerate(steps, 1)]
    expected = sum(c for c, _, _ in steps)

    link = hop.Link(args.pc, args.drone)
    started = False
    try:
        time.sleep(1.5)
        s = link.snapshot()
        print(f"[calib] before: {s}")
        if s.get("z", 0) > 5 or s.get("running"):
            raise SystemExit("drone is not idle on the ground")
        link.send(dp.frame([1, 0, 3, 0, 1]))
        time.sleep(0.3)
        for f in frames:
            link.send(f)
            time.sleep(0.02)
        time.sleep(1.2)
        got = link.snapshot().get("checksum")
        print(f"[calib] drone checksum {got} ({'OK' if got == expected else 'MISMATCH'})")
        if got != expected:
            raise SystemExit("mission not accepted as sent")
        clock = link.snapshot().get("clock")
        start = 0.1 * (clock + 300) if clock else dp.CLOCK[0] + 30
        link.send(dp.frame([5, 0, 2, 8, 1, *struct.pack("<I", int(start))]))
        started = True
        print("[calib] START sent")
        last, deadline, seen = None, time.time() + 12, False
        while time.time() < deadline and not link.lost:
            s = link.snapshot()
            if s.get("z", 0) > 10:
                print("[calib] z rose, landing")
                break
            state = (s.get("running"), s.get("z"), s.get("x"), s.get("y"))
            if state != last:
                last = state
                print(f"[calib] running={state[0]} z={state[1]} x={state[2]} y={state[3]}")
            seen |= bool(s.get("running"))
            if seen and not s.get("running"):
                break
            time.sleep(0.1)
        time.sleep(1)
        print(f"[calib] after: {link.snapshot()}")
    finally:
        if started and (link.snapshot().get("z") or 0) > 3:
            for _ in range(3):
                try:
                    link.send(hop.ALL_AUTOLAND)
                except OSError:
                    break
                time.sleep(0.1)
            print("[calib] all_autoLand sent")
        link.stop.set()


if __name__ == "__main__":
    main()
