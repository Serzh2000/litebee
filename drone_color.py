"""Light the LED of one LiteBee Wing drone, without flying.

Sends a mission containing a single RGB step and starts it, as LiteBee Go does
for a show. The script refuses to build a mission with any other step type.

usage: python drone_color.py --pc 192.168.13.100 --drone 192.168.13.108 --color green
"""
import argparse
import socket
import struct
import threading
import time

import drone_probe as dp

CMD_RGB = 50  # the only step type this script may send
COLORS = {"black": (0, 0, 0), "red": (255, 0, 0), "green": (0, 255, 0), "yellow": (255, 255, 0),
          "blue": (0, 0, 255), "purple": (255, 0, 255), "cyan": (0, 255, 255), "white": (255, 255, 255)}


def rgb_mission(r, g, b):
    """One RGB step, packed like LiteBee Go: [total, 0, index, 0, t_lo, t_hi, cmd] + 12 data bytes."""
    step = [1, 0, 1, 0, 0, 0, CMD_RGB] + [5, 0, 2, 255, g, r, b, 0, 0, 0, 0, 0]
    assert step[6] == CMD_RGB and len(step) == 19
    return [dp.frame([19, 0, 3, 2, *step])], CMD_RGB  # frames, expected checksum (sum of cmd bytes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", required=True)
    ap.add_argument("--drone", required=True)
    ap.add_argument("--color", choices=COLORS, default="green")
    ap.add_argument("--hold", type=float, default=8, help="seconds to watch before stopping")
    args = ap.parse_args()

    stop = threading.Event()
    threading.Thread(target=dp.announce, args=(args.pc, args.drone, stop), daemon=True).start()
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.pc, dp.TCP_PORT))
    server.listen()
    server.settimeout(30)
    print("[color] waiting for the drone to connect...")
    conn, addr = server.accept()
    print(f"[color] drone connected from {addr[0]}")
    conn.settimeout(0.2)
    conn.sendall(dp.frame([2, 0, 2, 1, 8, 10]))

    latest, lock, beat = {}, threading.Lock(), [0]

    def heartbeat():
        while not stop.is_set():
            try:
                conn.sendall(dp.frame([1, 0, 0, 3, beat[0]]))
            except OSError:
                return
            beat[0] = (beat[0] + 1) % 256
            time.sleep(0.05)

    def reader():
        buf = bytearray()
        while not stop.is_set():
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
                if (group, ident) == (1, 8) and len(data) >= 20:
                    with lock:
                        latest.update(running=data[7], checksum=data[8] + 256 * data[9],
                                      clock=struct.unpack_from("<I", data, 16)[0],
                                      z=struct.unpack_from("<3h", data, 0)[2], volts=data[6] / 10)

    threading.Thread(target=heartbeat, daemon=True).start()
    threading.Thread(target=reader, daemon=True).start()
    time.sleep(1)

    frames, expected = rgb_mission(*COLORS[args.color])
    print(f"[color] clear old mission, send RGB step {args.color}, expected checksum {expected}")
    conn.sendall(dp.frame([1, 0, 3, 0, 1]))
    time.sleep(0.3)
    for f in frames:
        conn.sendall(f)
    time.sleep(1.2)
    with lock:
        print(f"[color] drone reports checksum {latest.get('checksum')} ({'OK' if latest.get('checksum') == expected else 'MISMATCH'})")
    if latest.get("checksum") != expected:
        print("[color] not starting: the drone did not accept the mission as expected")
    else:
        # same rule as LiteBee Go: from the drone's clock if it reports one, else our own counter + 3 s
        start = 0.1 * (latest["clock"] + 300) if latest.get("clock") else dp.CLOCK[0] + 30
        conn.sendall(dp.frame([5, 0, 2, 8, 1, *struct.pack("<I", int(start))]))
        print(f"[color] start sent (t={int(start)}), watching {args.hold:.0f} s")
        end, last = time.time() + args.hold, None
        while time.time() < end:
            with lock:
                state = (latest.get("running"), latest.get("z"))
            if state != last:
                last = state
                print(f"[color] running={state[0]} z={state[1]}")
            time.sleep(0.2)
    conn.sendall(dp.frame([1, 0, 2, 8, 0]))  # stop
    print("[color] stop sent")
    time.sleep(0.5)
    stop.set()


if __name__ == "__main__":
    main()
