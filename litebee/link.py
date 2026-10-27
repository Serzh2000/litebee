"""Connection to LiteBee Wing drones: UDP announce + time sync, TCP server, heartbeats.

Does what LiteBee Go does on connect: announce the PC's IP over UDP, accept the
drone's TCP connection, answer with the pilot callback, then heartbeat every
50 ms and keep the latest telemetry per drone (connections keyed by peer IP).

Safety:
  * `whitelist` (set of IPs): connections from other IPs are closed. None
    means "accept any" and is only meant for read-only listening; flying
    requires a whitelist (see safety.preflight).
  * Loopback mode (pc_ip is 127.x): no broadcast, nothing is ever sent outside
    127.0.0.0/8, and the real ports (18001, 6000, 13146) are refused. This is
    what the tests use, together with a fake drone.
"""
import socket
import sys
import threading
import time
from typing import Callable, Dict, Iterable, Optional

from . import protocol as proto
from .protocol import ALL_AUTOLAND, REAL_PORTS, Telemetry


def is_loopback(ip: str) -> bool:
    return ip.startswith("127.")


class DroneConn:
    """TCP connection to one drone."""

    def __init__(self, ip: str, sock: socket.socket, port: int):
        self.ip, self.sock, self.port = ip, sock, port
        self.telemetry: Optional[Telemetry] = None
        self.last_rx = 0.0
        self.lost = False
        self.connected_at = time.time()
        self.frames_seen: Dict[tuple, bytes] = {}   # (group, id) -> first data seen
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()

    def send(self, data: bytes):
        with self._send_lock:
            self.sock.sendall(data)

    def snapshot(self) -> Optional[Telemetry]:
        with self._lock:
            return self.telemetry

    def _set_telemetry(self, t: Telemetry):
        with self._lock:
            self.telemetry = t
            self.last_rx = time.time()

    def close(self):
        self.lost = True
        try:
            self.sock.close()
        except OSError:
            pass


class Link:
    def __init__(self, pc_ip: str, *, tcp_port: int = proto.TCP_PORT,
                 udp_remote_port: int = proto.UDP_REMOTE, udp_local_port: int = proto.UDP_LOCAL,
                 whitelist: Optional[Iterable[str]] = None, announce_targets: Iterable[str] = (),
                 broadcast: Optional[bool] = None, log: Optional[Callable[[str], None]] = None):
        self.pc_ip = pc_ip
        self.loopback = is_loopback(pc_ip)
        if self.loopback and (REAL_PORTS & {tcp_port, udp_remote_port}):
            raise ValueError("Loopback mode refuses the real drone ports 18001/6000/13146")
        self.tcp_port, self.udp_remote_port = tcp_port, udp_remote_port
        self.udp_local_port = 0 if self.loopback else udp_local_port
        self.whitelist = None if whitelist is None else set(whitelist)
        self.announce_targets = list(announce_targets)
        self.broadcast = (not self.loopback) if broadcast is None else broadcast
        if self.loopback and self.broadcast:
            raise ValueError("Broadcast is not allowed in loopback mode")
        self._log = log or (lambda msg: None)
        self.drones: Dict[str, DroneConn] = {}
        self.stop_event = threading.Event()
        self.tick = 0            # time-sync counter (0.1 s ticks)
        self._server: Optional[socket.socket] = None
        self._threads = []
        self._lock = threading.Lock()

    def log(self, msg):
        self._log(msg)

    # ---- lifecycle ---------------------------------------------------------

    def start(self):
        """Bind the TCP server and start announcing. Raises OSError if the port is busy."""
        server = socket.socket()
        if sys.platform != "win32":     # on Windows SO_REUSEADDR would allow a second owner of the port
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((self.pc_ip, self.tcp_port))
        except OSError:
            server.close()
            raise
        server.listen()
        server.settimeout(0.5)
        self._server = server
        self.tcp_port = server.getsockname()[1]
        self._spawn(self._announce_loop)
        self._spawn(self._accept_loop)
        self.log(f"Слушаем {self.pc_ip}:{self.tcp_port}")
        return self

    def _spawn(self, fn, *args):
        t = threading.Thread(target=fn, args=args, daemon=True)
        t.start()
        self._threads.append(t)

    def close(self):
        self.stop_event.set()
        if self._server:
            try:
                self._server.close()
            except OSError:
                pass
        with self._lock:
            conns = list(self.drones.values())
        for c in conns:
            c.close()
        for t in self._threads:
            t.join(timeout=1)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()

    # ---- UDP ---------------------------------------------------------------

    def _sendto(self, sock, data, host, port):
        if self.loopback and not is_loopback(host):
            raise RuntimeError(f"Loopback mode must not send to {host}")
        sock.sendto(data, (host, port))

    def _announce_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.broadcast:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind((self.pc_ip, self.udp_local_port))
        except OSError:  # port 6000 can be held by another service; sending doesn't need it
            sock.bind((self.pc_ip, 0))
            self.log(f"UDP-порт {self.udp_local_port} занят, отправляем с {sock.getsockname()[1]}")
        pkt = proto.announce_frame(self.pc_ip)
        bcast = self.pc_ip.rsplit(".", 1)[0] + ".255"
        targets = list(self.announce_targets) or ([self.pc_ip] if self.loopback else [])
        tick = 0
        while not self.stop_event.is_set():
            try:
                if tick % 10 == 0:  # IP announcement once a second
                    if self.broadcast:
                        self._sendto(sock, pkt, bcast, self.udp_remote_port)
                    for host in targets:
                        self._sendto(sock, pkt, host, self.udp_remote_port)
                tick += 1  # time sync 10x a second, like the app
                self.tick = tick
                clock = proto.timesync_frame(tick)
                if self.broadcast:
                    self._sendto(sock, clock, bcast, self.udp_remote_port)
                else:
                    for host in targets:
                        self._sendto(sock, clock, host, self.udp_remote_port)
            except OSError as e:
                self.log(f"UDP: {e}")
            self.stop_event.wait(0.1)
        sock.close()

    # ---- TCP ---------------------------------------------------------------

    def _accept_loop(self):
        while not self.stop_event.is_set():
            try:
                conn, addr = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            ip = addr[0]
            if self.whitelist is not None and ip not in self.whitelist:
                self.log(f"Игнорируем соединение с {ip}: нет в белом списке")
                conn.close()
                continue
            conn.settimeout(0.2)
            dc = DroneConn(ip, conn, addr[1])
            with self._lock:
                old = self.drones.get(ip)
                self.drones[ip] = dc
            if old:
                old.close()
            try:
                dc.send(proto.pilot_callback_frame())  # "set pilot callback", as the app does
            except OSError:
                dc.close()
                continue
            self._spawn(self._heartbeat, dc)
            self._spawn(self._reader, dc)
            self.log(f"Дрон {ip} подключился")

    def _heartbeat(self, dc: DroneConn):
        beat = 0
        while not self.stop_event.is_set() and not dc.lost:
            try:
                dc.send(proto.heartbeat_frame(beat))
            except OSError:
                dc.lost = True
                return
            beat = (beat + 1) % 256
            time.sleep(0.05)

    def _reader(self, dc: DroneConn):
        buf = bytearray()
        while not self.stop_event.is_set() and not dc.lost:
            try:
                chunk = dc.sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                chunk = b""
            if not chunk:
                dc.lost = True
                self.log(f"Дрон {dc.ip} потерял связь")
                return
            buf += chunk
            for f in proto.parse_frames(buf):
                if (f.group, f.id) == (proto.TELEMETRY_GROUP, proto.TELEMETRY_ID):
                    t = proto.decode_telemetry(f.data)
                    if t:
                        dc.frames_seen.setdefault("raw", f.data)
                        dc._set_telemetry(t)
                        continue
                dc.frames_seen.setdefault((f.group, f.id), f.data)

    # ---- queries and commands ---------------------------------------------

    def connections(self) -> Dict[str, DroneConn]:
        with self._lock:
            return dict(self.drones)

    def get(self, ip: str) -> Optional[DroneConn]:
        with self._lock:
            return self.drones.get(ip)

    def wait_for(self, ip: Optional[str] = None, timeout: float = 30) -> DroneConn:
        """Wait until a drone (the given IP, or any) is connected."""
        end = time.time() + timeout
        while time.time() < end:
            for dip, dc in self.connections().items():
                if (ip is None or dip == ip) and not dc.lost:
                    return dc
            time.sleep(0.05)
        raise TimeoutError("Дрон не подключился")

    def emergency_land(self, ip: Optional[str] = None, repeats: int = 3) -> int:
        """Send all_autoLand to one drone (or all); idempotent, safe on the ground.
        Returns the number of drones the frame was written to."""
        sent = 0
        for dip, dc in self.connections().items():
            if ip is not None and dip != ip:
                continue
            ok = False
            for _ in range(repeats):
                try:
                    dc.send(ALL_AUTOLAND)
                    ok = True
                except OSError:
                    break
                time.sleep(0.1)
            sent += ok
        return sent
