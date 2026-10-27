"""Take one LiteBee Wing drone up to a height, hover briefly and land.

Mission = calibrate -> takeOff -> moveZ (hover) -> autoLand, packed the way
LiteBee Go packs formation steps (times are cumulative, in 0.1 s; heights in cm).

Without --go the mission is only uploaded and its checksum verified; the motors
are never started. With --go it is then started and watched.

Emergency landing (all_autoLand) is sent on any error, on Ctrl+C, when the
drone's connection drops, and when a file named LAND_NOW appears next to this
script.

usage: python drone_hop.py --pc 192.168.13.100 --drone 192.168.13.109 [--go]
"""
import argparse
import os
import socket
import struct
import threading
import time

import drone_probe as dp

CMD_CALIBRATE, CMD_TAKEOFF, CMD_AUTOLAND, CMD_MOVEZ = 0, 1, 2, 5
ALLOWED = {CMD_CALIBRATE, CMD_TAKEOFF, CMD_AUTOLAND, CMD_MOVEZ}
MAX_HEIGHT_CM, MAX_HOVER_S = 150, 10
ALL_AUTOLAND = dp.frame([9, 0, 2, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0])
LAND_FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "LAND_NOW")


def build_mission(height_cm, hover_s, calibrate_s=5, takeoff_s=5):
    """Return ([frames], expected_checksum, total_seconds)."""
    assert 20 <= height_cm <= MAX_HEIGHT_CM and 0 <= hover_s <= MAX_HOVER_S
    z = list(struct.pack("<H", int(height_cm)))
    steps, now = [], 0  # (cmd, cumulative time in 0.1 s, 12 data bytes)
    for cmd, secs, data in (
        (CMD_CALIBRATE, calibrate_s, [0] * 12),
        (CMD_TAKEOFF, takeoff_s, z + [0] * 10),
        (CMD_MOVEZ, hover_s, z + [0] * 10),
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
    return frames, sum(c for c, _, _ in steps), now / 10


class Link:
    """TCP link to exactly one drone; keeps it alive and tracks its telemetry."""

    def __init__(self, pc, drone):
        self.stop, self.latest, self.lock, self.lost = threading.Event(), {}, threading.Lock(), False
        threading.Thread(target=dp.announce, args=(pc, drone, self.stop), daemon=True).start()
        server = socket.socket()
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((pc, dp.TCP_PORT))
        server.listen()
        server.settimeout(1)
        print(f"[hop] waiting for {drone} ...")
        deadline = time.time() + 30
        while True:
            if time.time() > deadline:
                raise TimeoutError("drone did not connect")
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            if addr[0] == drone:
                break
            print(f"[hop] ignoring connection from {addr[0]}")
            conn.close()
        self.conn = conn
        conn.settimeout(0.2)
        conn.sendall(dp.frame([2, 0, 2, 1, 8, 10]))
        threading.Thread(target=self._heartbeat, daemon=True).start()
        threading.Thread(target=self._reader, daemon=True).start()
        print(f"[hop] drone {drone} connected")

    def send(self, data):
        self.conn.sendall(data)

    def _heartbeat(self):
        beat = 0
        while not self.stop.is_set():
            try:
                self.conn.sendall(dp.frame([1, 0, 0, 3, beat]))
            except OSError:
                self.lost = True
                return
            beat = (beat + 1) % 256
            time.sleep(0.05)

    def _reader(self):
        buf = bytearray()
        while not self.stop.is_set():
            try:
                chunk = self.conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                chunk = b""
            if not chunk:
                self.lost = True
                return
            buf += chunk
            for group, ident, data in dp.parse_frames(buf):
                if (group, ident) == (1, 8) and len(data) >= 20:
                    with self.lock:
                        self.latest.update(
                            x=struct.unpack_from("<3h", data, 0)[1], y=struct.unpack_from("<3h", data, 0)[0],
                            z=struct.unpack_from("<3h", data, 0)[2], volts=data[6] / 10, running=data[7],
                            checksum=data[8] + 256 * data[9], clock=struct.unpack_from("<I", data, 16)[0])

    def snapshot(self):
        with self.lock:
            return dict(self.latest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", required=True)
    ap.add_argument("--drone", required=True)
    ap.add_argument("--height", type=int, default=100, help="cm")
    ap.add_argument("--hover", type=float, default=3, help="seconds")
    ap.add_argument("--min-volts", type=float, default=7.0)
    ap.add_argument("--go", action="store_true", help="actually start the motors")
    args = ap.parse_args()

    frames, expected, total = build_mission(args.height, args.hover)
    print(f"[hop] mission: {len(frames)} steps, ~{total:.0f} s, height {args.height} cm, expected checksum {expected}")
    if os.path.exists(LAND_FLAG):
        os.remove(LAND_FLAG)

    link = Link(args.pc, args.drone)
    started = False
    try:
        time.sleep(1.5)
        t = link.snapshot()
        print(f"[hop] telemetry: {t}")
        if not t or t["volts"] < args.min_volts:
            raise SystemExit(f"battery {t.get('volts')} V is below {args.min_volts} V, not flying")
        link.send(dp.frame([1, 0, 3, 0, 1]))  # clear any old mission
        time.sleep(0.3)
        for f in frames:
            link.send(f)
            time.sleep(0.02)
        time.sleep(1.2)
        got = link.snapshot().get("checksum")
        print(f"[hop] drone checksum {got} ({'OK' if got == expected else 'MISMATCH'})")
        if got != expected:
            raise SystemExit("mission was not accepted as sent, not starting")
        if not args.go:
            print("[hop] upload verified; motors NOT started (no --go)")
            return
        clock = link.snapshot().get("clock")
        start = 0.1 * (clock + 300) if clock else dp.CLOCK[0] + 30
        link.send(dp.frame([5, 0, 2, 8, 1, *struct.pack("<I", int(start))]))
        started = True
        print("[hop] START sent")
        deadline, seen_running, last = time.time() + total + 20, False, None
        while time.time() < deadline and not link.lost:
            if os.path.exists(LAND_FLAG):
                print("[hop] LAND_NOW found")
                break
            s = link.snapshot()
            state = (s.get("running"), s.get("z"), s.get("volts"))
            if state != last:
                last = state
                print(f"[hop] running={state[0]} z={state[1]} volts={state[2]}")
            seen_running |= bool(s.get("running"))
            if seen_running and not s.get("running"):
                print("[hop] mission finished")
                break
            time.sleep(0.1)
        if link.lost:
            print("[hop] connection to the drone was lost")
    finally:
        if started:
            for _ in range(3):  # idempotent safety net: land (no-op if already on the ground)
                try:
                    link.send(ALL_AUTOLAND)
                except OSError:
                    break
                time.sleep(0.1)
            print("[hop] all_autoLand sent as a safety net")
            time.sleep(2)
        link.stop.set()


if __name__ == "__main__":
    main()
