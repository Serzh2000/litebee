"""A fake LiteBee drone that speaks the protocol over 127.0.0.1 only.

It listens for the UDP announce on an ephemeral loopback port, connects to the
announced address on the given TCP port, answers with telemetry frames and
computes the mission checksum like the real drone does (sum of the cmd bytes of
all steps, whatever they are).

Position: like a freshly powered real drone it reports x = y = 0 (NO fix on the
mat) unless `fix=(x, y)` cm is given. `fix_after_flight=(x, y)` models the real
behaviour that a short hop gives the drone a fix that stays after landing.
`set_fix(None)` takes the fix away again.
"""
import socket
import struct
import threading
import time

from litebee import protocol as proto
from litebee.mission import CMD_AUTOLAND, CMD_MOVEZ, CMD_TAKEOFF

HOST = "127.0.0.1"


def free_port():
    s = socket.socket()
    s.bind((HOST, 0))
    port = s.getsockname()[1]
    s.close()
    return port


class FakeDrone:
    def __init__(self, tcp_port, *, volts=7.5, time_scale=20.0, id_bytes=(0x80, 0x84, 0x1A, 0x55),
                 auto_connect=True, fix=None, fix_after_flight=None):
        assert tcp_port not in proto.REAL_PORTS
        self.tcp_port, self.volts, self.time_scale, self.id_bytes = tcp_port, volts, time_scale, id_bytes
        self.auto_connect = auto_connect
        self.x, self.y = fix if fix else (0, 0)
        self.fix_after_flight = fix_after_flight
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind((HOST, 0))
        self.udp.settimeout(0.1)
        self.udp_port = self.udp.getsockname()[1]
        self.stop_event = threading.Event()
        self.sock = None
        self.frames = []            # every TCP frame received, as proto.Frame
        self.announces = []         # IPs seen in announce frames
        self.timesyncs = 0
        self.steps = {}             # index -> 19 step bytes
        self.cleared = 0
        self.starts = []
        self.stops = 0
        self.lands = 0              # all_autoLand frames received
        self.running = 0
        self.z = 0
        self._run_end = 0.0
        self._run_height = 0
        self._threads = []
        self._lock = threading.Lock()

    # ---- derived state -----------------------------------------------------

    @property
    def checksum(self):
        return sum(s[6] for s in self.steps.values()) & 0xFFFF

    def set_fix(self, fix):
        """Report position (x, y) cm from now on; None means no fix (x = y = 0)."""
        with self._lock:
            self.x, self.y = fix if fix else (0, 0)

    @property
    def connected(self):
        return self.sock is not None

    # ---- lifecycle ---------------------------------------------------------

    def start(self):
        t = threading.Thread(target=self._udp_loop, daemon=True)
        t.start()
        self._threads.append(t)
        return self

    def stop(self):
        self.stop_event.set()
        self.drop_connection()
        self.udp.close()
        for t in self._threads:
            t.join(timeout=1)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    def drop_connection(self):
        s, self.sock = self.sock, None
        if s:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()

    def wait_connected(self, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            if self.connected:
                return True
            time.sleep(0.02)
        return False

    def wait_for(self, predicate, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            if predicate():
                return True
            time.sleep(0.02)
        return False

    # ---- UDP side ----------------------------------------------------------

    def _udp_loop(self):
        buf = bytearray()
        while not self.stop_event.is_set():
            try:
                data, addr = self.udp.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                return
            assert addr[0] == HOST, "fake drone must only hear loopback"
            buf += data
            for f in proto.parse_frames(buf):
                if (f.group, f.id) == (3, 3) and len(f.data) == 4:
                    ip = ".".join(map(str, f.data))
                    self.announces.append(ip)
                    if self.auto_connect and not self.connected and ip.startswith("127."):
                        self._connect(ip)
                elif (f.group, f.id) == (2, 9):
                    self.timesyncs += 1

    def _connect(self, ip):
        try:
            s = socket.create_connection((ip, self.tcp_port), timeout=2)
        except OSError:
            return
        s.settimeout(0.1)
        self.sock = s
        for fn in (self._tcp_loop, self._telemetry_loop):
            t = threading.Thread(target=fn, args=(s,), daemon=True)
            t.start()
            self._threads.append(t)

    # ---- TCP side ----------------------------------------------------------

    def _tcp_loop(self, s):
        buf = bytearray()
        while not self.stop_event.is_set() and self.sock is s:
            try:
                chunk = s.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            for f in proto.parse_frames(buf):
                self._handle(f)

    def _handle(self, f):
        with self._lock:
            if (f.group, f.id) != (0, 3):  # do not log heartbeats
                self.frames.append(f)
            if (f.group, f.id) == (3, 0):            # clear mission
                self.steps.clear()
                self.cleared += 1
            elif (f.group, f.id) == (3, 2) and len(f.data) == 19:   # mission step
                self.steps[f.data[2]] = bytes(f.data)
            elif (f.group, f.id) == (2, 8):
                if f.data[:1] == b"\x01":              # start
                    self.starts.append(struct.unpack_from("<I", f.data, 1)[0])
                    self._begin_run()
                else:                                  # stop
                    self.stops += 1
                    self.running, self.z = 0, 0
            elif (f.group, f.id) == (2, 3) and f.data[:1] == b"\x04":   # all_autoLand
                self.lands += 1
                self.running, self.z = 0, 0

    def _begin_run(self):
        steps = [self.steps[i] for i in sorted(self.steps)]
        total = ((steps[-1][4] | steps[-1][5] << 8) / 10) if steps else 0
        self._run_height = max((struct.unpack_from("<H", s, 7)[0] for s in steps
                                if s[6] in (CMD_TAKEOFF, CMD_MOVEZ)), default=0)
        self._run_end = time.time() + max(total / self.time_scale, 0.5)
        if self.fix_after_flight and any(s[6] == CMD_TAKEOFF for s in steps):
            self.x, self.y = self.fix_after_flight
        self.running = 1

    def _telemetry_loop(self, s):
        n = 0
        while not self.stop_event.is_set() and self.sock is s:
            with self._lock:
                if self.running and time.time() >= self._run_end:
                    self.running, self.z = 0, 0
                elif self.running:
                    self.z = self._run_height
                payload = proto.encode_telemetry(x=self.x, y=self.y, z=self.z, volts=self.volts, running=self.running,
                                                 checksum=self.checksum, id_bytes=self.id_bytes)
            try:
                s.sendall(proto.frame([len(payload), 0, 1, 8, *payload]))
            except OSError:
                return
            n += 1
            time.sleep(0.1)
