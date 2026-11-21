"""Test setup. Run from the repo root:  pytest tests/"""
from __future__ import annotations

import pytest
import pytest_socket

from python_libratone_zipp import hub as hub_mod, speaker as speaker_mod
import custom_components.libratone_zipp as integration

from .fake_speaker import FakeSpeaker


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def allow_udp():
    """The fake speakers are real UDP sockets on 127.0.0.x."""
    pytest_socket.enable_socket()
    pytest_socket.socket_allow_hosts(["127.0.0.0/8"], allow_unix_socket=True)
    yield


@pytest.fixture(autouse=True)
def fast_timings(monkeypatch):
    monkeypatch.setattr(hub_mod, "POLL_INTERVAL", 0.3)
    monkeypatch.setattr(hub_mod, "SCAN_INTERVAL", 0.5)
    monkeypatch.setattr(speaker_mod, "AVAILABLE_TIMEOUT", 1.5)
    monkeypatch.setattr(integration, "IDENTIFY_TIMEOUT", 3.0)


@pytest.fixture
async def fakes():
    started: list[FakeSpeaker] = []

    async def _start(ip: str, **kwargs) -> FakeSpeaker:
        fake = await FakeSpeaker(**kwargs).start(ip)
        started.append(fake)
        return fake

    yield _start
    for fake in started:
        fake.stop()
