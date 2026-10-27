"""Read-only probe for LiteBee Wing drones in formation mode.

Does what LiteBee Go does on connect (announce the PC's IP over UDP, accept the
drone's TCP connection, send heartbeats) and prints the telemetry the drone
sends back. It sends no flight or LED commands.

usage: python drone_probe.py --pc 192.168.13.100 --drone 192.168.13.108 --seconds 30
"""
import argparse
import socket
import struct
import threading
import time

TCP_PORT, UDP_LOCAL, UDP_REMOTE = 18001, 6000, 13146

CLOCK = [0]  # time-sync counter (0.1 s ticks) shared with scripts that import this module
CRC_TABLE_HEAD =[0, 4489, 8978, 12955]  # first entries of the table in LiteBee Go


def crc16(data):
    """CRC-16/MCRF4XX: init 0xFFFF, reflected 0x8408, no final xor, low byte first."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return bytes((crc & 0xFF, crc >> 8))


def table_entry(i):
    crc = i
    for _ in range(8):
        crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc


assert [table_entry(i) for i in range(4)] == CRC_TABLE_HEAD, "CRC variant does not match the app"


def frame(payload):
    """payload = [len, 0, group, id, *data] -> 0xFA + payload + crc."""
    return bytes([0xFA]) + bytes(payload) + crc16(bytes(payload))


def parse_frames(buf):
    """Yield (group, id, data) for each valid frame; leave the remainder in buf."""
    while True:
        start = buf.find(0xFA)
        if start < 0:
            buf.clear()
            return
        del buf[:start]
        if len(buf) < 2:
            return
        n = buf[1]
        if n >= 128:
            del buf[0]
            continue
        total = 1 + 4 + n + 2
        if len(buf) < total:
            return
        payload = bytes(buf[1:5 + n])
        if crc16(payload) == bytes(buf[5 + n:total]):
            yield payload[2], payload[3], payload[4:]
            del buf[:total]
        else:
            del buf[0]


def telemetry(data):
    if len(data) < 20:
        return None
    y, x, z = struct.unpack_from("<3h", data, 0)
    return dict(x=x, y=y, z=z, battery_v=data[6] / 10, running=data[7],
                drone_id="".join(map(str, data[12:16])),
                clock=struct.unpack_from("<I", data, 16)[0])


def announce(pc_ip, drone_ip, stop):
    bcast = pc_ip.rsplit(".", 1)[0] + ".255"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind((pc_ip, UDP_LOCAL))
    except OSError:  # port 6000 can be held by another service; sending doesn't need it
        sock.bind((pc_ip, 0))
        print(f"[udp] port {UDP_LOCAL} busy, sending from {sock.getsockname()[1]}")
    pkt = frame([4, 0, 3, 3, *map(int, pc_ip.split("."))])
    tick = 0
    while not stop.is_set():
        if tick % 10 == 0:  # IP announcement once a second
            sock.sendto(pkt, (bcast, UDP_REMOTE))
            sock.sendto(pkt, (drone_ip, UDP_REMOTE))
        tick += 1  # time sync 10x a second, like the app
        CLOCK[0] = tick
        clock = frame([4, 0, 2, 9, *struct.pack("<I", tick)])
        sock.sendto(clock, (bcast, UDP_REMOTE))
        time.sleep(0.1)


def serve_client(conn, addr, stop):
    print(f"[tcp] drone connected from {addr[0]}:{addr[1]}")
    conn.settimeout(0.2)
    conn.sendall(frame([2, 0, 2, 1, 8, 10]))  # "set pilot callback", as the app does
    beat, last_print, buf, seen = 0, 0.0, bytearray(), set()

    def heartbeat():
        nonlocal beat
        while not stop.is_set():
            try:
                conn.sendall(frame([1, 0, 0, 3, beat]))
            except OSError:
                return
            beat = (beat + 1) % 256
            time.sleep(0.05)

    threading.Thread(target=heartbeat, daemon=True).start()
    while not stop.is_set():
        try:
            chunk = conn.recv(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
        for group, ident, data in parse_frames(buf):
            if (group, ident) == (1, 8) and (t := telemetry(data)):
                if "raw" not in seen:
                    seen.add("raw")
                    print(f"[raw telemetry] {len(data)} bytes: {data.hex(' ')}")
                if time.time() - last_print > 1:
                    last_print = time.time()
                    print(f"[telemetry {addr[0]}] {t}")
            elif (group, ident) not in seen:
                seen.add((group, ident))
                print(f"[frame] group={group} id={ident} data={data.hex(' ')}")
    print("[tcp] connection closed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc", required=True)
    ap.add_argument("--drone", required=True)
    ap.add_argument("--seconds", type=float, default=30)
    args = ap.parse_args()

    stop = threading.Event()
    threading.Thread(target=announce, args=(args.pc, args.drone, stop), daemon=True).start()
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.pc, TCP_PORT))
    server.listen()
    server.settimeout(0.5)
    print(f"[probe] listening on {args.pc}:{TCP_PORT}, announcing to {args.drone}")
    deadline = time.time() + args.seconds
    while time.time() < deadline:
        try:
            conn, addr = server.accept()
        except socket.timeout:
            continue
        threading.Thread(target=serve_client, args=(conn, addr, stop), daemon=True).start()
    stop.set()
    time.sleep(0.5)
    print("[probe] done")


if __name__ == "__main__":
    main()
