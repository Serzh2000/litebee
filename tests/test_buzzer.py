"""Buzzer frames: the bytes that were played on a live module (see docs/firmware/BUZZER_EXTENSION.md). No port is opened."""
import pytest

from litebee import buzzer


def test_note_table_matches_litebee_go():
    assert buzzer.NOTE_NAMES[0] == "B0" and buzzer.NOTE_NAMES[1] == "C1" and buzzer.NOTE_NAMES[2] == "CS1"
    assert buzzer.NOTE_NAMES[-1] == "DS8"
    assert buzzer.note_index("C3") == 25 and buzzer.note_index("D3") == 27 and buzzer.note_index("E3") == 29
    assert buzzer.note_index("c4") == 37                               # the app's high Do
    assert len(buzzer.NOTE_NAMES) == 89


def test_frames_equal_the_ones_heard_on_the_buzzer():
    assert buzzer.frame(25, 10).hex() == "adfa01190a24"                 # note 25, 0.5 s: sounded
    assert buzzer.frame(37, 10).hex() == "adfa01250a30"                 # an octave higher: sounded higher
    assert buzzer.frame("C3", 5).hex() == "adfa0119051f"                # short
    assert buzzer.frame("C3", 20).hex() == "adfa0119142e"               # longer


def test_checksum_is_sum_of_command_and_data():
    f = buzzer.frame(44, 40)
    assert f[-1] == (0x01 + 44 + 40) & 0xFF


def test_ranges_are_refused():
    with pytest.raises(ValueError):
        buzzer.frame(200, 10)
    with pytest.raises(ValueError):
        buzzer.frame(25, 0)
    with pytest.raises(ValueError):
        buzzer.note_index("H4")


def test_song_text_and_plan():
    song = buzzer.parse_song("C3:10 R:5 E3:20")
    assert song == [("C3", 10), (None, 5), ("E3", 20)]
    p = buzzer.plan(song, gap_s=0.05)
    assert p[0] == (buzzer.frame("C3", 10), pytest.approx(0.55))
    assert p[1] == (b"", pytest.approx(0.25))
    assert p[2][1] == pytest.approx(1.05)
    with pytest.raises(ValueError):
        buzzer.parse_song("C3")
