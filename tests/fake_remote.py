"""Test double of the USB remote: answers like the real one did on COM3, never touches a port."""
import struct

from litebee import remote as r


def make_data(pos=(0, 0, 0), roll=0.0, pitch=0.0, yaw=0.0, volts=7.7, mode=10, speed=(0, 0, 0), mission=5) -> bytes:
    """The 30 data bytes the way LiteBee Go reads them (see litebee.remote.DataPackage)."""
    raw = bytearray(30)
    struct.pack_into("<3h", raw, 0, *pos)
    struct.pack_into("<3h", raw, 6, round(roll * 10), round(pitch * 10), round(yaw * 10))
    raw[12] = round(volts * 10)
    raw[15] = mode
    struct.pack_into("<3b", raw, 16, *speed)
    raw[29] = mission
    return bytes(raw)


class FakeRemote:
    def __init__(self, *, drone_linked=False, ack=True, version=(0, 111), packet=None, on_command=None):
        self.drone_linked = drone_linked
        self.ack = ack
        self.version = version
        self.packet = packet if packet is not None else (make_data() if drone_linked else bytes(30))
        self.on_command = on_command          # called as on_command(fake, payload) for every non-read-only message
        self.written = []                     # every write call, as bytes
        self.commands = []                    # payloads of the messages that are not read-only
        self.closed = False
        self.streaming = False
        self._out = bytearray()

    def write(self, data: bytes):
        data = bytes(data)
        self.written.append(data)
        if data == r.HELLO and self.ack:
            self._out += r.from_remote([r.TYPE_ACK, 3])
        elif data == r.ASK_VERSION:
            self._out += r.from_remote([r.TYPE_VERSION, *self.version, 0])
        elif data == r.ASK_DATA:
            self.streaming = True
        elif data not in r.READ_ONLY_WRITES and data.startswith(b"\xfd\xfd"):
            payload = data[3:]
            self.commands.append(payload)
            if self.on_command:
                self.on_command(self, payload)

    def read_available(self) -> bytes:
        if self.streaming:                    # one data package per read, like the live ~20 per second
            self._out += r.from_remote([r.TYPE_DATA, *self.packet])
        out, self._out = bytes(self._out), bytearray()
        return out

    def close(self):
        self.closed = True
