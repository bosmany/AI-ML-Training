"""Pick which implementation the tests import as ``lab``.

Learners run ``pytest`` (target = starter). Maintainers/CI run ``LAB_TARGET=solution pytest``.
"""
import os
import socket
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True

_TARGET = os.environ.get("LAB_TARGET", "starter")
_LAB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_LAB_DIR / _TARGET))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # fixture_server.py

from fixture_server import FixtureSite  # noqa: E402

_LOCAL = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    """Hermeticity guard: anything that is not loopback fails the test instead of touching the network."""
    real_connect, real_connect_ex, real_getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def check_address(address):
        if isinstance(address, tuple) and address and address[0] not in _LOCAL:
            raise AssertionError(f"test tried to reach a non-loopback address: {address!r}")

    def connect(self, address):
        check_address(address)
        return real_connect(self, address)

    def connect_ex(self, address):
        check_address(address)
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if host not in _LOCAL and host is not None:
            raise AssertionError(f"test tried to resolve a non-local host name: {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)


@pytest.fixture
def site():
    s = FixtureSite().start()
    yield s
    s.stop()


@pytest.fixture
def other_site():
    """A second server: same IP, different port, i.e. a different 'host' for same-host checks."""
    s = FixtureSite().start()
    yield s
    s.stop()
