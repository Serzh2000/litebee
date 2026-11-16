"""Frames for the LiteBee 4-wire buzzer module (UART, 115200 8N1), found on a live module on 2026-11-07.

The buzzer answers the same frame family as the camera module:  AD FA <cmd> <data...> <sum8>,  sum8 = (cmd + data) & 0xFF.
Command 01 plays a note:  AD FA 01 <note> <duration> <sum8>
  * note: index of LiteBee Go's note table, 0 = B0, 1 = C1, 2 = C#1 ... (C3 = 25, E3 = 29, C4 = 37); tested 25..44
  * duration: one unit is about 0.05 s (LiteBee Go sends 10 * rhythm, "0.5 s per rhythm"); tested 5, 10, 20
Verified by ear: pitch follows the note byte, length follows the duration byte, a scale and a song played correctly.

Nothing here opens a port: the functions only build bytes. Docs: docs/firmware/BUZZER_EXTENSION.md.
"""
from typing import List, Optional, Tuple, Union

from . import protocol as proto

HEADER = bytes([0xAD, 0xFA])
CMD_NOTE = 0x01
UNIT_S = 0.05                       # seconds per duration unit (from LiteBee Go: 10 units = 0.5 s; the song sounded right)

_SEMITONES = ["C", "CS", "D", "DS", "E", "F", "FS", "G", "GS", "A", "AS", "B"]
NOTE_NAMES: List[str] = ["B0"] + [f"{n}{o}" for o in range(1, 9) for n in _SEMITONES][:-8]   # B0 ... DS8, as in LiteBee Go
MAX_NOTE = len(NOTE_NAMES) - 1


def note_index(name: str) -> int:
    """'C3' -> 25. Sharps are written like LiteBee Go: 'CS3' is C#3."""
    try:
        return NOTE_NAMES.index(name.strip().upper())
    except ValueError:
        raise ValueError(f"Нет такой ноты: {name!r} (от B0 до DS8, диез: CS3)")


def checksum(body: bytes) -> int:
    return sum(body) & 0xFF


def frame(note: Union[int, str], duration: int) -> bytes:
    """One note: AD FA 01 note duration sum8."""
    idx = note_index(note) if isinstance(note, str) else int(note)
    if not 0 <= idx <= MAX_NOTE:
        raise ValueError(f"Нота {idx} вне таблицы 0..{MAX_NOTE}")
    if not 1 <= duration <= 255:
        raise ValueError("Длительность 1..255 (единица около 0,05 с)")
    body = bytes([CMD_NOTE, idx, duration])
    return HEADER + body + bytes([checksum(body)])


def seconds(duration: int) -> float:
    return duration * UNIT_S


Song = List[Tuple[Optional[Union[int, str]], int]]


def parse_song(text: str) -> Song:
    """'C3:10 E3:10 R:5' -> [('C3', 10), ('E3', 10), (None, 5)]; R (or '-') is a rest."""
    song: Song = []
    for token in text.split():
        name, _, dur = token.partition(":")
        if not dur.isdigit():
            raise ValueError(f"Ожидалось нота:длительность, получено {token!r}")
        song.append((None if name.upper() in ("R", "-") else name, int(dur)))
    return song


def plan(song: Song, gap_s: float = 0.05) -> List[Tuple[bytes, float]]:
    """Frames with the pause to wait after each one: the note length plus a small gap, or the rest length."""
    out: List[Tuple[bytes, float]] = []
    for note, dur in song:
        if note is None:
            out.append((b"", seconds(dur)))
        else:
            out.append((frame(note, dur), seconds(dur) + gap_s))
    return out


RELAY_CMD = 0xFA
RELAY_PORT = 5555


def relay_frame(inner: bytes) -> bytes:
    """Wrap a frame for the module's relay command: AD FA FA 08 <8 bytes> sum8.

    The camera module copies these 8 bytes to its extension UART, i.e. to the buzzer (found in the drone's own code and
    checked by ear on 2026-11-07: AD FA FA 08 AD FA 01 19 0A 24 00 00 F1 played a note). The 6-byte note frame is padded
    with two zeros; sum8 covers FA, 08 and the 8 bytes.
    """
    if not 0 < len(inner) <= 8:
        raise ValueError("В кадр-реле помещается до 8 байт")
    data = bytes(inner) + bytes(8 - len(inner))
    body = bytes([RELAY_CMD, 8]) + data
    return HEADER + body + bytes([checksum(body)])


def play_udp(host: str, port: int, steps: List[Tuple[bytes, float]], send=None, sleep=None) -> None:
    """Send a plan() over UDP to the relay program running on the drone (tools/firmware/build_udp_tty_relay.py).

    send(bytes) and sleep(seconds) can be replaced in tests; by default a UDP socket and time.sleep are used.
    """
    import socket
    import time
    sock = None
    if send is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send = lambda data: sock.sendto(data, (host, port))        # noqa: E731
    sleep = sleep or time.sleep
    try:
        for fr, wait in steps:
            if fr:
                send(relay_frame(fr))
            sleep(wait)
    finally:
        if sock is not None:
            sock.close()


# ---- native Wi-Fi set_buzzer (group=2/sub=3/mode=27), confirmed live 2026-11-16 -------------
#
# ПРОЧТЕНО on a live drone+module+buzzer, over the same TCP 18001 link the formation protocol
# already uses (litebee.link.Link): `pilot`/`pilot_f` answers an awlink frame
# [9, 0, 2, 3, 27, 1, note, duration, 0, 0, 0, 0, 3] by playing that note on the buzzer wired to
# the position module -- no UDP relay, no ADB, works in CLIENT (the mode a show runs in).
# docs/firmware/BUZZER_EXTENSION.md section 6 has the session's notes.
#
# ВЫВОД (not re-measured carefully, just one evening of ear tests): the duration byte's unit is
# close to 0.05 s (ten back-to-back notes totalling 110 units sounded like ~5 s of continuous
# tone), and the drone does not leave a gap between two notes sent one after another -- pitch
# just slides. mode=24 (`[9,0,2,3,24,0,...]`, guessed from WING_MOBILE_APP.md's buzzerControl(0))
# was sent right after each note as an attempt to silence it before the next one; whether it is a
# real "off" command is НЕИЗВЕСТНО, only that playback sounded less slurred with it than without.

NATIVE_UNIT_S = 0.045  # ВЫВОД, see above; not the same unit as the AD FA relay path (UNIT_S)


def native_frame(note: Union[int, str], duration: int) -> bytes:
    """set_buzzer(note, duration) over the formation Wi-Fi link: group=2/sub=3/mode=27."""
    idx = note_index(note) if isinstance(note, str) else int(note)
    if not 0 <= idx <= MAX_NOTE:
        raise ValueError(f"Нота {idx} вне таблицы 0..{MAX_NOTE}")
    if not 1 <= duration <= 255:
        raise ValueError("Длительность 1..255")
    return proto.frame([9, 0, 2, 3, 27, 1, idx, duration, 0, 0, 0, 0, 3])


def native_off_frame() -> bytes:
    """buzzerControl(0), mode=24: an attempt at 'stop the sound' between two native notes."""
    return proto.frame([9, 0, 2, 3, 24, 0, 0, 0, 0, 0, 0, 0, 0])


def play_live(send, song: Song, gap_s: float = 0.06, unit_s: float = NATIVE_UNIT_S, sleep=None) -> None:
    """Play `song` (as parse_song()) over an already-connected drone link: `send` is a
    DroneConn.send-like callable (bytes -> None), e.g. `litebee.link.Link.wait_for(ip).send`.

    Blocks for the song's own duration (each note's native_frame, held for duration*unit_s,
    then native_off_frame and a small technical gap before the next one)."""
    import time
    sleep = sleep or time.sleep
    for note, dur in song:
        if note is None:
            sleep(dur * unit_s)
            continue
        send(native_frame(note, dur))
        sleep(dur * unit_s)
        send(native_off_frame())
        sleep(gap_s)
