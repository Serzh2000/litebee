import threading
import time

import pytest

from conftest import FAST, HOST, open_rig
from fake_drone import FakeDrone, free_port
from litebee import protocol as proto
from litebee.flight import (Aborted, ConnectionLost, MissionRejected, run_mission, start_mission,
                            upload_mission, watch_mission)
from litebee.link import Link
from litebee.mission import Mission, hop_mission, rgb_mission
from litebee.safety import NO_FIX_MESSAGE, SafetyError, preflight


def quiet(msg):
    pass


# ---- link ------------------------------------------------------------------

def test_link_refuses_real_ports_on_loopback():
    with pytest.raises(ValueError):
        Link(HOST)                       # default ports are the real ones
    with pytest.raises(ValueError):
        Link(HOST, tcp_port=18001, udp_remote_port=5)
    with pytest.raises(ValueError):
        Link(HOST, tcp_port=5, udp_remote_port=13146)
    with pytest.raises(ValueError):
        Link(HOST, tcp_port=5, udp_remote_port=6, broadcast=True)


def test_announce_connect_telemetry(rig):
    link, drone, port = rig
    assert HOST in drone.announces
    assert drone.timesyncs > 0
    t = link.get(HOST).snapshot()
    assert t.battery_v == 7.5 and t.drone_id == "1281322685"
    assert link.tcp_port == port and not link.get(HOST).lost
    # pilot callback frame arrives first, heartbeats continue
    assert any((f.group, f.id) == (2, 1) for f in drone.frames)


def test_whitelist_rejects_other_ip():
    port = free_port()
    drone = FakeDrone(port).start()
    link = Link(HOST, tcp_port=port, udp_remote_port=drone.udp_port, whitelist={"10.9.9.9"},
                announce_targets=[HOST]).start()
    try:
        time.sleep(1.5)
        assert link.connections() == {}
        assert drone.announces
    finally:
        link.close()
        drone.stop()


def test_connection_loss_detected(rig):
    link, drone, _ = rig
    drone.drop_connection()
    assert drone.wait_for(lambda: link.get(HOST).lost, 5)


# ---- mission flows ---------------------------------------------------------

def test_rgb_upload_start_stop(rig):
    link, drone, _ = rig
    r = run_mission(link, HOST, rgb_mission(0, 255, 0), go=True, hold=0.6, timing=FAST, log=quiet)
    assert r.uploaded and r.started and r.checksum == 50
    assert drone.checksum == 50 and drone.cleared == 1 and len(drone.starts) == 1 and drone.stops == 1
    assert drone.lands >= 3          # safety net after any started mission


def test_hop_dry_run_does_not_start(rig):
    link, drone, _ = rig
    r = run_mission(link, HOST, hop_mission(100, 3), go=False, timing=FAST, log=quiet)
    assert r.uploaded and not r.started and r.outcome == "dry-run"
    assert drone.checksum == 8 and len(drone.steps) == 4
    assert drone.starts == [] and drone.running == 0 and drone.lands == 0


def test_hop_go_runs_and_lands(rig):
    link, drone, _ = rig
    r = run_mission(link, HOST, hop_mission(100, 3), go=True, timing=FAST, log=quiet)
    assert r.started and r.outcome == "finished"
    assert len(drone.starts) == 1 and drone.lands >= 3


def test_start_requires_arm(rig):
    link, drone, _ = rig
    conn = link.get(HOST)
    m = hop_mission(100, 3)
    upload_mission(conn, m, FAST, quiet)
    with pytest.raises(SafetyError):
        start_mission(link, conn, m, arm=False)
    assert drone.starts == []


def test_start_requires_whitelist_for_flight():
    port = free_port()
    drone = FakeDrone(port).start()
    link = Link(HOST, tcp_port=port, udp_remote_port=drone.udp_port, whitelist=None,
                announce_targets=[HOST]).start()
    try:
        conn = link.wait_for(HOST, 5)
        with pytest.raises(SafetyError):
            start_mission(link, conn, hop_mission(100, 3), arm=True)
        with pytest.raises(SafetyError):
            run_mission(link, HOST, hop_mission(100, 3), go=True, timing=FAST, log=quiet)
        assert drone.starts == []
    finally:
        link.close()
        drone.stop()


def test_low_battery_refuses_and_sends_land():
    port = free_port()
    drone = FakeDrone(port, volts=6.8).start()
    link = Link(HOST, tcp_port=port, udp_remote_port=drone.udp_port, whitelist={HOST},
                announce_targets=[HOST]).start()
    try:
        link.wait_for(HOST, 5)
        with pytest.raises(SafetyError, match="Батарея"):
            run_mission(link, HOST, hop_mission(100, 3), go=True, timing=FAST, log=quiet)
        assert drone.wait_for(lambda: drone.lands >= 1)
        assert drone.starts == [] and drone.steps == {}      # nothing was even uploaded
    finally:
        link.close()
        drone.stop()


def test_low_battery_does_not_block_led_only_mission():
    port = free_port()
    drone = FakeDrone(port, volts=6.8).start()
    link = Link(HOST, tcp_port=port, udp_remote_port=drone.udp_port, whitelist={HOST},
                announce_targets=[HOST]).start()
    try:
        link.wait_for(HOST, 5)
        r = run_mission(link, HOST, rgb_mission(255, 0, 0), go=True, hold=0.3, timing=FAST, log=quiet)
        assert r.started
    finally:
        link.close()
        drone.stop()


def test_mismatch_not_started_and_land_sent(rig):
    link, drone, _ = rig
    m = hop_mission(100, 3)
    orig = drone._handle

    def corrupt(f):                        # drone drops the last step
        if (f.group, f.id) == (3, 2) and f.data[2] == 4:
            return
        orig(f)

    drone._handle = corrupt
    with pytest.raises(MissionRejected) as e:
        run_mission(link, HOST, m, go=True, timing=FAST, log=quiet)
    assert (e.value.expected, e.value.got) == (8, 6)
    assert drone.starts == [] and drone.wait_for(lambda: drone.lands >= 1)


def test_abort_sends_emergency_land(rig):
    link, drone, _ = rig
    abort = threading.Event()
    long_mission = hop_mission(100, 10)
    drone.time_scale = 0.2                    # makes the fake mission last a long time
    threading.Timer(1.5, abort.set).start()
    with pytest.raises(Aborted):
        run_mission(link, HOST, long_mission, go=True, abort=abort, timing=FAST, log=quiet)
    assert drone.lands >= 3 and drone.running == 0


def test_connection_loss_during_flight_raises(rig):
    link, drone, _ = rig
    drone.time_scale = 0.2
    threading.Timer(1.5, drone.drop_connection).start()
    with pytest.raises(ConnectionLost):
        run_mission(link, HOST, hop_mission(100, 10), go=True, timing=FAST, log=quiet)


def test_emergency_land_reaches_drone(rig):
    link, drone, _ = rig
    assert link.emergency_land() == 1
    assert drone.wait_for(lambda: drone.lands >= 3)


def test_land_flag_file_aborts(rig, tmp_path):
    link, drone, _ = rig
    drone.time_scale = 0.2
    flag = tmp_path / "LAND_NOW"
    threading.Timer(1.5, lambda: flag.write_text("x")).start()
    with pytest.raises(Aborted):
        run_mission(link, HOST, hop_mission(100, 10), go=True, land_flag=str(flag), timing=FAST, log=quiet)
    assert drone.lands >= 3


# ---- safety refusals -------------------------------------------------------

def test_preflight_refusals():
    m = hop_mission(100, 3)
    preflight(m, ip=HOST, whitelist={HOST}, volts=7.0)           # exactly 7.0 V passes
    with pytest.raises(SafetyError):
        preflight(m, ip=HOST, whitelist={HOST}, volts=6.9)       # battery < 7.0
    with pytest.raises(SafetyError):
        preflight(m, ip=HOST, whitelist={HOST}, volts=None)      # unknown battery
    with pytest.raises(SafetyError):
        preflight(m, ip=HOST, whitelist={HOST}, volts=8.0, min_volts=5.0)   # cannot lower threshold
    with pytest.raises(SafetyError):
        preflight(m, ip="10.0.0.2", whitelist={HOST}, volts=8.0)  # not whitelisted
    with pytest.raises(SafetyError):
        preflight(m, ip=HOST, whitelist=None, volts=8.0)
    preflight(rgb_mission(1, 2, 3), ip=HOST, whitelist=None, volts=None)   # LED-only: allowed


def test_preflight_refuses_height_and_hover_built_by_hand():
    from litebee.mission import CMD_MOVEZ, CMD_TAKEOFF, MissionStep, z_data
    tall = Mission([MissionStep(CMD_TAKEOFF, 50, z_data(151))])
    with pytest.raises(SafetyError, match="Высота"):
        preflight(tall, ip=HOST, whitelist={HOST}, volts=8.0)
    hover = Mission([MissionStep(CMD_TAKEOFF, 50, z_data(100)), MissionStep(CMD_MOVEZ, 160, z_data(100))])
    assert hover.max_hover_s == 11.0
    with pytest.raises(SafetyError, match="Зависание"):
        preflight(hover, ip=HOST, whitelist={HOST}, volts=8.0)


def test_watch_mission_times_out_quietly(rig):
    link, drone, _ = rig
    conn = link.get(HOST)
    assert watch_mission(conn, rgb_mission(0, 0, 0), timing=FAST, log=quiet, time_limit=0.3) == "timeout"


def test_run_mission_uses_the_height_limit(rig):
    link, drone, _ = rig
    m = hop_mission(160, 3, max_height_cm=170)
    with pytest.raises(SafetyError, match="Высота"):
        run_mission(link, HOST, m, go=False, timing=FAST, log=quiet)          # default limit 150
    assert drone.steps == {}
    r = run_mission(link, HOST, m, go=False, timing=FAST, log=quiet, max_height_cm=170)
    assert r.uploaded and r.outcome == "dry-run" and drone.starts == []


# ---- cell moves (moveXY) need a position fix ----------------------------------------

CODE_SHOW = ("from litebee import Show\nshow = Show('c')\nd = show.drone(1)\n"
             "d.calibrate(5)\nd.takeoff(50, 5)\nd.code(97, 4)\nd.land()\n")


def code_mission():
    from litebee.loader import load_show_source
    from litebee.show import drone_to_mission
    return drone_to_mission(load_show_source(CODE_SHOW).drones[1])


def test_code_show_uploads_and_verifies_the_checksum():
    m = code_mission()
    with open_rig(fix=(40, 320)) as (link, drone, _):             # standing on its first cell, with a fix
        r = run_mission(link, HOST, m, go=False, timing=FAST, log=quiet)
        assert r.uploaded and r.outcome == "dry-run" and r.checksum == 6 == m.checksum
        assert drone.checksum == 6 and drone.starts == []
        assert [bytes(drone.steps[i]) for i in sorted(drone.steps)] == [fr[5:24] for fr in m.frames()]
        assert len(drone.steps) == 4 and drone.steps[3][6] == 3        # the moveXY step reached the drone


def test_code_show_flies_on_the_fake_drone_with_a_fix():
    with open_rig(fix=(40, 330)) as (link, drone, _):             # 10 cm off the cell is fine
        r = run_mission(link, HOST, code_mission(), go=True, timing=FAST, log=quiet)
        assert r.started and len(drone.starts) == 1 and drone.checksum == 6


def test_no_fix_refuses_cell_moves_before_anything_is_sent(rig):
    link, drone, _ = rig                                           # fresh drone: x = y = 0
    with pytest.raises(SafetyError) as e:
        run_mission(link, HOST, code_mission(), go=True, timing=FAST, log=quiet)
    assert str(e.value) == NO_FIX_MESSAGE and "поставьте его на коврик" in str(e.value).lower()
    assert drone.steps == {} and drone.cleared == 0 and drone.starts == []


def test_wrong_start_cell_refuses_and_names_both_cells():
    with open_rig(fix=(400, 400)) as (link, drone, _):             # stands on cell 130, show expects 97
        with pytest.raises(SafetyError) as e:
            run_mission(link, HOST, code_mission(), go=True, timing=FAST, log=quiet)
        assert "на клетке 130" in str(e.value) and "клетке 97" in str(e.value)
        assert drone.steps == {} and drone.starts == []


def test_start_checks_the_position_again():
    """The drone was carried away between upload and start: start_mission refuses."""
    m = code_mission()
    with open_rig(fix=(40, 320)) as (link, drone, _):
        conn = link.get(HOST)
        upload_mission(conn, m, FAST, quiet)
        drone.set_fix((400, 400))
        assert drone.wait_for(lambda: conn.snapshot().x == 400)
        with pytest.raises(SafetyError, match="клетке 130"):
            start_mission(link, conn, m, arm=True)
        drone.set_fix(None)
        assert drone.wait_for(lambda: not conn.snapshot().has_fix)
        with pytest.raises(SafetyError, match="нет позиции"):
            start_mission(link, conn, m, arm=True)
        assert drone.starts == []
        drone.set_fix((40, 320))
        assert drone.wait_for(lambda: conn.snapshot().has_fix)
        start_mission(link, conn, m, arm=True)
        assert drone.wait_for(lambda: len(drone.starts) == 1)


def test_short_hop_gives_a_fix_then_the_cell_moves_run():
    """The routine: a 50 cm hop on a fresh drone, then the mission with cell moves."""
    with open_rig(fix_after_flight=(40, 330)) as (link, drone, _):
        with pytest.raises(SafetyError, match="нет позиции"):
            run_mission(link, HOST, code_mission(), go=True, timing=FAST, log=quiet)
        hop = hop_mission(50, 1)
        run_mission(link, HOST, hop, go=True, timing=FAST, log=quiet)
        assert drone.wait_for(lambda: link.get(HOST).snapshot().has_fix)
        assert drone.wait_for(lambda: not drone.running)
        r = run_mission(link, HOST, code_mission(), go=True, timing=FAST, log=quiet)
        assert r.started and drone.checksum == 6


def test_missions_without_cell_moves_need_no_position(rig):
    link, drone, _ = rig                                           # no fix
    r = run_mission(link, HOST, hop_mission(100, 3), go=False, timing=FAST, log=quiet)
    assert r.uploaded
    preflight(hop_mission(100, 3), ip=HOST, whitelist={HOST}, volts=8.0)       # no telemetry needed


def test_preflight_requires_telemetry_for_cell_moves():
    m = code_mission()
    with pytest.raises(SafetyError, match="позиция дрона неизвестна"):
        preflight(m, ip=HOST, whitelist={HOST}, volts=8.0)
    from litebee.protocol import decode_telemetry, encode_telemetry
    ok = decode_telemetry(encode_telemetry(x=40, y=320))
    preflight(m, ip=HOST, whitelist={HOST}, volts=8.0, telemetry=ok)
