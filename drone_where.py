"""Read-only: which QR-mat cell is each connected drone on (same formula as LiteBee Go).

LiteBee Go: code = round(x / 40) + 12 * round(y / 40), where y = first int16 and x = second
int16 of the telemetry. x = y = 0 means the drone has no position fix (not on the mat or the
fix has not started), not "cell 0".

usage: python drone_where.py --pc 192.168.13.100 [--seconds 10]
"""
import argparse
import socket
import threading
import time

import drone_probe as dp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", required=True)
    ap.add_argument("--seconds", type=float, default=10)
    args = ap.parse_args()
    stop, latest = threading.Event(), {}
    threading.Thread(target=dp.announce, args=(args.pc, args.pc.rsplit(".", 1)[0] + ".255", stop), daemon=True).start()
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.pc, dp.TCP_PORT))
    server.listen()
    server.settimeout(0.5)

    def serve(conn, ip):
        conn.settimeout(0.2)
        conn.sendall(dp.frame([2, 0, 2, 1, 8, 10]))
        buf = bytearray()
        beat = 0
        last = 0
        while not stop.is_set():
            if time.time() - last > 0.05:
                try:
                    conn.sendall(dp.frame([1, 0, 0, 3, beat]))
                except OSError:
                    return
                beat, last = (beat + 1) % 256, time.time()
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            for group, ident, data in dp.parse_frames(buf):
                if (group, ident) == (1, 8) and (t := dp.telemetry(data)):
                    latest[ip] = t

    deadline = time.time() + args.seconds
    while time.time() < deadline:
        try:
            conn, addr = server.accept()
        except socket.timeout:
            continue
        threading.Thread(target=serve, args=(conn, addr[0]), daemon=True).start()
    for ip, t in sorted(latest.items()):
        if t["x"] == 0 and t["y"] == 0:
            where = "нет позиции по коврику (x=0, y=0)"
        else:
            where = f"клетка {round(t['x'] / 40) + 12 * round(t['y'] / 40)} (x={t['x']}, y={t['y']})"
        print(f"{ip}: {where}, {t['battery_v']} В, z={t['z']} см")
    if not latest:
        print("дроны не подключились")
    stop.set()
    time.sleep(0.3)


if __name__ == "__main__":
    main()
