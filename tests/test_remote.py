"""USB remote link: bytes seen on the real remote (COM3), the read-only guard, and a full conversation on a test double."""
import pytest

from fake_remote import FakeRemote
from litebee import cli, remote as r

# captured on the real remote, 2026-10-28
REAL_ACK = bytes.fromhex("fc fc 02 e9 03")
REAL_VERSION = bytes.fromhex("fc fc 04 0d 00 6f 00")
REAL_DATA = bytes.fromhex("fc fc 1f 0e") + bytes(30)


def test_messages_to_the_remote_are_the_ones_litebee_go_sends():
    assert r.HELLO.hex() == "fdfd01e9"
    assert r.ASK_VERSION.hex() == "fdfd010d"
    assert r.ASK_DATA.hex() == "fdfd010e"
    assert r.HEARTBEAT == b"\x00"
    assert r.to_remote([27, 2, 0, 20, 0, 0]).hex() == "fdfd061b0200140000"
    with pytest.raises(r.RemoteError):
        r.to_remote([])
    with pytest.raises(r.RemoteError):
        r.to_remote(bytes(256))


def test_parser_reads_the_real_frames_even_in_pieces():
    p = r.RemoteParser()
    stream = REAL_ACK + REAL_VERSION + REAL_DATA
    got = []
    for i in range(0, len(stream), 3):                 # three bytes at a time
        got += p.feed(stream[i:i + 3])
    assert got == [bytes([0xE9, 3]), bytes([0x0D, 0, 0x6F, 0]), bytes([0x0E]) + bytes(30)]
    assert not p.buf


def test_parser_skips_garbage_and_keeps_a_half_frame():
    p = r.RemoteParser()
    assert p.feed(b"\x00\x01\xfc\xfc\x02\xe9") == []                     # frame not complete yet
    assert p.feed(b"\x03" + b"\x55\xfc") == [bytes([0xE9, 3])]
    assert p.feed(b"\xfc\x01\x0d") == [bytes([0x0D])]                      # the lone FC joined the next FC


def test_version_and_data_decoding():
    v = r.decode_version(bytes([0x0D, 0, 0x6F, 0]))
    assert v == r.Version(0, 111) and v.fv_text is None and v.rv_text == "1.1.1"
    assert r.decode_version(bytes([0x0D, 123, 111])).fv_text == "1.2.3"
    assert r.decode_version(b"\x0e\x00\x00") is None and r.decode_version(b"\x0d\x00") is None
    d = r.decode_data(bytes([0x0E]) + bytes(30))
    assert d.is_empty and len(d.raw) == 30
    assert not r.decode_data(bytes([0x0E]) + bytes([0] * 29 + [5])).is_empty
    assert r.decode_data(b"\xe9\x03") is None
    assert r.decode_data(bytes([0x0E, 0, 5])) is None                    # too short to be a data package


# captured on the real remote with the drone linked, 2026-10-28
REAL_LINKED = bytes.fromhex("49 00 06 01 00 00 41 03 2e 00 4a 00 4d 00 00 0a 12 ff fa 00 00 00 00 00 00 00 00 00 00 05")


def test_data_package_fields_follow_litebee_go():
    d = r.decode_data(bytes([0x0E]) + REAL_LINKED)
    assert d.pos == (73, 262, 0)
    assert (d.roll_deg, d.pitch_deg, d.yaw_deg) == (83.3, 4.6, 7.4)
    assert d.voltage == 7.7 and d.mode == 10 and d.speed == (18, -1, -6) and d.mission == 5
    assert not d.is_empty


def test_full_conversation_with_a_remote_that_sees_no_drone():
    fake = FakeRemote(drone_linked=False)
    with r.RemoteLink(fake) as link:
        assert link.handshake() is True
        assert link.request_version() == r.Version(0, 111)
        pkg = link.request_data()
        assert pkg is not None and pkg.is_empty
        link.run(1.2)                                                 # real clock: three 500 ms heartbeats at most
    assert fake.closed
    assert link.data_count > 5
    assert set(fake.written) <= r.READ_ONLY_WRITES                    # only the four read-only messages
    assert fake.written[0] == r.HELLO and fake.written.count(r.HEARTBEAT) >= 2


def test_conversation_with_a_linked_drone_gives_non_zero_data():
    fake = FakeRemote(drone_linked=True, version=(123, 111))
    link = r.RemoteLink(fake)
    assert link.handshake() and link.request_version().fv_text == "1.2.3"
    assert not link.request_data().is_empty


def test_no_answer_means_no_handshake():
    ticks = iter(range(10 ** 6))
    link = r.RemoteLink(FakeRemote(ack=False), clock=lambda: next(ticks) / 100, sleep=lambda s: None)
    assert link.handshake(timeout=1.0) is False and not link.acked


def test_commands_are_blocked_by_default():
    fake = FakeRemote()
    link = r.RemoteLink(fake)
    with pytest.raises(r.RemoteError):
        link.send_message([16])                                       # take-off
    assert fake.written == []
    with pytest.raises(r.RemoteError):
        link._write(r.to_remote([16]))                                # also the internal write is whitelisted
    assert fake.written == []
    link2 = r.RemoteLink(fake, allow_commands=True)
    link2.send_message([17])
    assert fake.written == [bytes.fromhex("fdfd0111")]


def test_cli_wing_status_reports_an_unlinked_drone(monkeypatch, capsys):
    monkeypatch.setattr(r, "open_link", lambda port=None, **kw: r.RemoteLink(FakeRemote(drone_linked=False)))
    assert cli.main(["wing-status", "--seconds", "0.3"]) == 0
    out = capsys.readouterr().out
    assert "пульт ответил на приветствие" in out and "пульт 1.1.1" in out and "не видит дрон" in out


def test_cli_wing_status_reports_a_linked_drone(monkeypatch, capsys):
    monkeypatch.setattr(r, "open_link", lambda port=None, **kw: r.RemoteLink(FakeRemote(drone_linked=True, version=(123, 111))))
    assert cli.main(["wing-status", "--seconds", "0.3"]) == 0
    out = capsys.readouterr().out
    assert "дрон 1.2.3" in out and "пульт видит дрон" in out and "батарея" in out


def test_cli_wing_status_fails_politely(monkeypatch, capsys):
    def boom(port=None, **kw):
        raise r.RemoteError("Пульт не найден")
    monkeypatch.setattr(r, "open_link", boom)
    assert cli.main(["wing-status"]) == 1
    assert "Пульт не найден" in capsys.readouterr().out
    monkeypatch.setattr(r, "open_link", lambda port=None, **kw: r.RemoteLink(FakeRemote(ack=False)))
    monkeypatch.setattr(r.RemoteLink, "handshake", lambda self, timeout=1.0: False)
    assert cli.main(["wing-status"]) == 1
