"""USB link to the hand-held remote of a LiteBee Wing (the Wing's own radio path, not the formation Wi-Fi).

The remote shows up as a serial port (CP210x or CH340, 115200 baud). The conversation is the one LiteBee Go
has on connect (docs/PROTOCOL_SINGLE.md, "USB-пульт"):

  PC -> remote   FD FD len payload          remote -> PC   FC FC len payload
  hello          [E9]                       ack            [E9, 03]
  ask versions   [0D]                       versions       [0D, FV, RV, ?]
  ask data       [0E]                       data package   [0E] + 30 bytes, about 20 times a second
  heartbeat      one byte 00 every 500 ms

By default the link is READ-ONLY: only the four messages above can be written. `send_message` (movement,
take-off, ...) raises until the caller passes `allow_commands=True`. Nothing in this package passes it yet.
"""
import struct
import time
from typing import Callable, List, NamedTuple, Optional

BAUD = 115200
USB_IDS = frozenset({(0x10C4, 0xEA60), (0x1A86, 0x7523)})      # CP210x, CH340: the ports LiteBee Go looks for
HEARTBEAT_S = 0.5

TYPE_ACK, TYPE_VERSION, TYPE_DATA = 0xE9, 0x0D, 0x0E


class RemoteError(Exception):
    pass


def to_remote(payload) -> bytes:
    """FD FD len payload."""
    payload = bytes(payload)
    if not 0 < len(payload) < 256:
        raise RemoteError("Сообщение пульту пустое или длиннее 255 байт")
    return bytes([0xFD, 0xFD, len(payload)]) + payload


def from_remote(payload) -> bytes:
    """FC FC len payload (what the remote sends; used by the test double)."""
    payload = bytes(payload)
    return bytes([0xFC, 0xFC, len(payload)]) + payload


HELLO = to_remote([TYPE_ACK])
ASK_VERSION = to_remote([TYPE_VERSION])
ASK_DATA = to_remote([TYPE_DATA])
HEARTBEAT = b"\x00"
READ_ONLY_WRITES = frozenset({HELLO, ASK_VERSION, ASK_DATA, HEARTBEAT})


class RemoteParser:
    """Cuts the byte stream of the remote into payloads (FC FC len payload). Garbage is skipped."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes) -> List[bytes]:
        self.buf += data
        out = []
        while True:
            i = self.buf.find(b"\xfc\xfc")
            if i < 0:
                del self.buf[:max(len(self.buf) - 1, 0)]      # keep a lone trailing FC: it may start a frame
                return out
            del self.buf[:i]
            if len(self.buf) < 3:
                return out
            n = self.buf[2]
            if len(self.buf) < 3 + n:
                return out
            out.append(bytes(self.buf[3:3 + n]))
            del self.buf[:3 + n]


def _dotted(value: int) -> str:
    text = str(value)
    return ".".join(text) if len(text) == 3 else text


class Version(NamedTuple):
    fv: int      # LiteBee Go calls it FV and treats 0 as "no version"; live: 0 while no drone is linked
    rv: int      # RV; live remote: 111, shown as 1.1.1

    @property
    def fv_text(self) -> Optional[str]:
        return _dotted(self.fv) if self.fv else None

    @property
    def rv_text(self) -> str:
        return _dotted(self.rv)


def decode_version(payload: bytes) -> Optional[Version]:
    if len(payload) < 3 or payload[0] != TYPE_VERSION:
        return None
    return Version(payload[1], payload[2])


DATA_LEN = 30


class DataPackage(NamedTuple):
    """The 30 bytes after the 0E marker. Layout as LiteBee Go reads it (main.js `remoteDataHandle`):
    int16 x3 position, int16 x3 angles in 0.1 degree, byte 12 volts x10, byte 15 mode, int8 x3 speeds at 16-18,
    bytes 19-28 extension modules (line, tags, colour, AI, distance sensors; not decoded), byte 29 mission.
    The first two position values are what LiteBee Go calls pos.x and pos.y (row and column of the mat, cm)."""
    raw: bytes

    @property
    def is_empty(self) -> bool:
        """All zero: the remote is there but sees no drone (live observation: remote not linked to a drone)."""
        return not any(self.raw)

    @property
    def pos(self):
        return struct.unpack_from("<3h", self.raw, 0)

    @property
    def roll_deg(self) -> float:
        return struct.unpack_from("<h", self.raw, 6)[0] / 10

    @property
    def pitch_deg(self) -> float:
        return struct.unpack_from("<h", self.raw, 8)[0] / 10

    @property
    def yaw_deg(self) -> float:
        return struct.unpack_from("<h", self.raw, 10)[0] / 10

    @property
    def voltage(self) -> float:
        return self.raw[12] / 10

    @property
    def mode(self) -> int:
        return self.raw[15]

    @property
    def speed(self):
        return struct.unpack_from("<3b", self.raw, 16)

    @property
    def mission(self) -> int:
        return self.raw[29]


def decode_data(payload: bytes) -> Optional[DataPackage]:
    if len(payload) < 1 + DATA_LEN or payload[0] != TYPE_DATA:
        return None
    return DataPackage(bytes(payload[1:1 + DATA_LEN]))


class SerialTransport:
    """pyserial wrapped to the three calls RemoteLink needs. DTR and RTS stay off."""

    def __init__(self, port: str):
        import serial
        self._ser = serial.Serial()
        self._ser.port = port
        self._ser.baudrate = BAUD
        self._ser.timeout = 0
        self._ser.write_timeout = 1
        self._ser.dtr = False
        self._ser.rts = False
        try:
            self._ser.open()
        except serial.SerialException as e:
            raise RemoteError(f"Не удалось открыть {port}: {e}. Закройте LiteBee Go и повторите") from e

    def write(self, data: bytes):
        self._ser.write(data)

    def read_available(self) -> bytes:
        n = self._ser.in_waiting
        return self._ser.read(n) if n else b""

    def close(self):
        if self._ser.is_open:
            self._ser.close()


def find_ports() -> List[str]:
    """Serial ports whose USB ids are the ones LiteBee Go accepts."""
    from serial.tools import list_ports
    return [p.device for p in list_ports.comports() if (p.vid, p.pid) in USB_IDS]


class RemoteLink:
    def __init__(self, transport, *, allow_commands: bool = False, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, log: Callable[[str], None] = lambda m: None):
        self.t = transport
        self.allow_commands = allow_commands
        self._clock, self._sleep, self.log = clock, sleep, log
        self.parser = RemoteParser()
        self.acked = False
        self.version: Optional[Version] = None
        self.last_data: Optional[DataPackage] = None
        self.data_count = 0
        self._next_beat = None

    # ---- writing ---------------------------------------------------------------------------------------

    def _write(self, data: bytes):
        if data not in READ_ONLY_WRITES:
            raise RemoteError("Запись вне списка «только чтение» заблокирована")
        self.t.write(data)

    def send_message(self, payload):
        """A command for the drone via the remote (take-off, speed, ...). Blocked unless allow_commands=True."""
        if not self.allow_commands:
            raise RemoteError("Отправка команд пульту выключена (allow_commands=False)")
        self.t.write(to_remote(payload))

    # ---- reading ---------------------------------------------------------------------------------------

    def _handle(self, payload: bytes):
        kind = payload[0] if payload else None
        if kind == TYPE_ACK:
            self.acked = True
        elif kind == TYPE_VERSION:
            self.version = decode_version(payload) or self.version
        elif kind == TYPE_DATA:
            pkg = decode_data(payload)
            if pkg:
                self.last_data, self.data_count = pkg, self.data_count + 1

    def pump(self) -> int:
        """Read what has arrived; returns how many messages were handled."""
        got = self.parser.feed(self.t.read_available())
        for payload in got:
            self._handle(payload)
        return len(got)

    def _wait(self, cond, timeout: float) -> bool:
        end = self._clock() + timeout
        while True:
            self.pump()
            if cond():
                return True
            if self._clock() >= end:
                return False
            self._sleep(0.005)

    # ---- the connect conversation ----------------------------------------------------------------------

    def handshake(self, timeout: float = 1.0) -> bool:
        self._write(HELLO)
        return self._wait(lambda: self.acked, timeout)

    def request_version(self, timeout: float = 1.0) -> Optional[Version]:
        self._write(ASK_VERSION)
        self._wait(lambda: self.version is not None, timeout)
        return self.version

    def request_data(self, timeout: float = 1.0) -> Optional[DataPackage]:
        """Ask once; the remote then streams data packages. Heartbeats keep it going (see `run`)."""
        self._write(ASK_DATA)
        self._next_beat = self._clock() + HEARTBEAT_S
        self._wait(lambda: self.last_data is not None, timeout)
        return self.last_data

    def run(self, seconds: float):
        """Keep the link alive for `seconds`: read, and send the 500 ms heartbeat."""
        end = self._clock() + seconds
        if self._next_beat is None:
            self._next_beat = self._clock() + HEARTBEAT_S
        while self._clock() < end:
            self.pump()
            if self._clock() >= self._next_beat:
                self._write(HEARTBEAT)
                self._next_beat += HEARTBEAT_S
            self._sleep(0.005)

    def close(self):
        self.t.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def open_link(port: Optional[str] = None, **kw) -> RemoteLink:
    """Open the remote on `port`, or on the only CP210x/CH340 port found."""
    if port is None:
        ports = find_ports()
        if not ports:
            raise RemoteError("Пульт не найден: подключите его по USB (порт CP210x или CH340)")
        if len(ports) > 1:
            raise RemoteError(f"Найдено несколько портов {', '.join(ports)}: укажите --serial")
        port = ports[0]
    return RemoteLink(SerialTransport(port), **kw)
