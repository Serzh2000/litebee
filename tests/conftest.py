import os
import sys
from contextlib import contextmanager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.dirname(os.path.abspath(__file__))):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402

from fake_drone import FakeDrone, free_port  # noqa: E402
from litebee.flight import Timing  # noqa: E402
from litebee.link import Link  # noqa: E402

FAST = Timing(telemetry_wait=0.3, after_clear=0.05, between_steps=0.005, after_upload=0.4,
              poll=0.05, run_margin=10, land_wait=0.05)
HOST = "127.0.0.1"


@contextmanager
def open_rig(**fake_kwargs):
    """Loopback link + fake drone (FakeDrone keyword arguments, e.g. fix=(x, y)), started and
    connected. Never touches real ports."""
    port = free_port()
    drone = FakeDrone(port, **fake_kwargs).start()
    link = Link(HOST, tcp_port=port, udp_remote_port=drone.udp_port, whitelist={HOST},
                announce_targets=[HOST]).start()
    try:
        assert drone.wait_connected(5), "fake drone did not connect"
        link.wait_for(HOST, 5)
        drone.wait_for(lambda: link.get(HOST).snapshot() is not None)
        yield link, drone, port
    finally:
        link.close()
        drone.stop()


@pytest.fixture
def rig():
    """Loopback link + fake drone without a position fix (a freshly powered drone)."""
    with open_rig() as r:
        yield r
