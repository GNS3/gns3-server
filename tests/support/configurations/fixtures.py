"""Pytest fixtures and in-process fakes shared by the startup configuration tests (not tests themselves).

* ``scripted_session``: the real console session logic driven by fragmented, deterministic serial input.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def scripted_session(monkeypatch):
    """Run the real session logic with fragmented, deterministic serial input."""

    from gns3server.services.configurations.console.session import ConsoleSession

    def create(chunks, *, driver="cisco_ios_telnet", content=None, fragmented=False, wait_ready=False):
        if fragmented:
            chunks = [character for chunk in chunks for character in "\r\n" + chunk]
        chunks = iter(chunk.encode() for chunk in chunks)
        connection = SimpleNamespace(
            read_very_eager=lambda: next(chunks),
            write=Mock(),
            open=Mock(),
            close=Mock(),
        )
        monkeypatch.setattr("gns3server.services.configurations.console.session.Telnet", lambda: connection)
        payload = {"port": 1, "device_type": driver, "username": "", "password": "", "enable_secret": ""}
        if content is not None:
            payload.update(content=content, wait_ready=wait_ready)
        return ConsoleSession(payload)

    return create
