#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import json
import asyncio
import aiohttp
import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from gns3server.controller.project import Project
from gns3server.controller.compute import Compute
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerNotFoundError,
    ControllerUnauthorizedError,
    ComputeConflictError,
)
from pydantic import SecretStr
from tests.utils import asyncio_patch, AsyncioMagicMock


@pytest.fixture
def compute(controller):

    compute = Compute("my_compute_id", protocol="https", host="example.com", port=84, controller=controller)
    compute._connected = True
    return compute


def test_init(compute):

    assert compute.id == "my_compute_id"


def test_getUrl(controller):

    compute = Compute("my_compute_id", protocol="https", host="localhost", port=84, controller=controller)
    assert compute._getUrl("/test") == "https://localhost:84/v3/compute/test"
    # IPV6 localhost
    compute = Compute("my_compute_id", protocol="https", host="::1", port=84, controller=controller)
    assert compute._getUrl("/test") == "https://[::1]:84/v3/compute/test"

    # Listen on all interfaces aka 0.0.0.0 require us to connect via 127.0.0.1
    compute = Compute("my_compute_id", protocol="https", host="0.0.0.0", port=84, controller=controller)
    assert compute._getUrl("/test") == "https://127.0.0.1:84/v3/compute/test"
    # IPV6
    compute = Compute("my_compute_id", protocol="https", host="::", port=84, controller=controller)
    assert compute._getUrl("/test") == "https://[::1]:84/v3/compute/test"


def test_get_url(controller):

    compute = Compute("my_compute_id", protocol="https", host="localhost", port=84, controller=controller)
    with patch('gns3server.controller.compute.Compute._getUrl', return_value="returned") as getURL:
        assert compute.get_url("/test") == 'returned'
        getURL.assert_called_once_with('/test')


def test_host_ip(controller):

    compute = Compute("my_compute_id", protocol="https", host="localhost", port=84, controller=controller)
    assert compute.host_ip == "127.0.0.1"


def test_name():

    c = Compute("my_compute_id", protocol="https", host="example.com", port=84, controller=MagicMock(), name=None)
    assert c.name == "https://example.com:84"
    c = Compute("world", protocol="https", host="example.com", port=84, controller=MagicMock(), name="hello")
    assert c.name == "hello"
    c = Compute("world", protocol="https", host="example.com", port=84, controller=MagicMock(), user="azertyuiopqsdfghjklkm")
    assert c.name == "https://azertyuiopq...@example.com:84"


@pytest.mark.asyncio
async def test_compute_httpQuery(compute):

    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 200
        await compute.post("/projects", {"a": "b"})
        await compute.close()
        mock.assert_called_with("POST", "https://example.com:84/v3/compute/projects", headers={'content-type': 'application/json'}, data=b'{"a": "b"}', auth=None, params=None, chunked=None, timeout=120)
        assert compute._auth is None


@pytest.mark.asyncio
async def test_compute_httpQueryAuth(compute):

    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 200

        compute.user = "root"
        compute.password = SecretStr("toor")
        await compute.post("/projects", {"a": "b"})
        await compute.close()
        mock.assert_called_with("POST", "https://example.com:84/v3/compute/projects", headers={'content-type': 'application/json'}, data=b'{"a": "b"}', auth=compute._auth, params=None, chunked=None, timeout=120)
        assert compute._auth.login == "root"
        assert compute._auth.password == "toor"


# @pytest.mark.asyncio
#async def test_compute_httpQueryNotConnected(compute, controller):
#
#     controller._notification = MagicMock()
#     compute._connected = False
#     response = AsyncioMagicMock()
#     response.read = AsyncioMagicMock(return_value=json.dumps({"version": __version__}).encode())
#     response.status = 200
#     with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
#         await compute.post("/projects", {"a": "b"})
#         mock.assert_any_call("GET", "https://example.com:84/v2/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, chunked=None, timeout=20)
#         mock.assert_any_call("POST", "https://example.com:84/v2/compute/projects", data=b'{"a": "b"}', headers={'content-type': 'application/json'}, auth=None, chunked=None, timeout=20)
#     #assert compute._connected
#     assert compute._capabilities["version"] == __version__
#     controller.notification.controller_emit.assert_called_with("compute.updated", compute.asdict())
#     await compute.close()


# @pytest.mark.asyncio
#async def test_compute_httpQueryNotConnectedGNS3vmNotRunning(compute, controller):
#     """
#     We are not connected to the remote and it's a GNS3 VM. So we need to start it
#     """
#
#     controller._notification = MagicMock()
#     controller.gns3vm = AsyncioMagicMock()
#     controller.gns3vm.running = False
#
#     compute._id = "vm"
#     compute._connected = False
#     response = AsyncioMagicMock()
#     response.read = AsyncioMagicMock(return_value=json.dumps({"version": __version__}).encode())
#     response.status = 200
#     with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
#         await compute.post("/projects", {"a": "b"})
#         mock.assert_any_call("GET", "https://example.com:84/v2/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, chunked=None, timeout=20)
#         mock.assert_any_call("POST", "https://example.com:84/v2/compute/projects", data=b'{"a": "b"}', headers={'content-type': 'application/json'}, auth=None, chunked=None, timeout=20)
#
#     assert controller.gns3vm.start.called
#     #assert compute._connected
#     assert compute._capabilities["version"] == __version__
#     controller.notification.controller_emit.assert_called_with("compute.updated", compute.asdict())
#     await compute.close()


@pytest.mark.asyncio
async def test_compute_httpQueryNotConnectedInvalidVersion(compute):

    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=json.dumps({"version": "1.42.4"}).encode())
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(ControllerError):
            await compute.post("/projects", {"a": "b"})
        mock.assert_any_call("GET", "https://example.com:84/v3/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, params=None, chunked=None, timeout=120)
        await compute.close()


@pytest.mark.asyncio
async def test_compute_httpQueryNotConnectedNonGNS3Server(compute):

    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=b'Blocked by super antivirus')
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(ControllerError):
            await compute.post("/projects", {"a": "b"})
        mock.assert_any_call("GET", "https://example.com:84/v3/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, params=None, chunked=None, timeout=120)
        await compute.close()


@pytest.mark.asyncio
async def test_compute_httpQueryNotConnectedNonGNS3Server2(compute):

    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=b'{}')
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(ControllerError):
            await compute.post("/projects", {"a": "b"})
        mock.assert_any_call("GET", "https://example.com:84/v3/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, params=None, chunked=None, timeout=120)


@pytest.mark.asyncio
async def test_compute_httpQueryError(compute):

    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 404
        with pytest.raises(ControllerNotFoundError):
            await compute.post("/projects", {"a": "b"})
        assert mock.called
        await compute.close()


@pytest.mark.asyncio
async def test_compute_httpQueryConflictError(compute):

    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 409
        response.read = AsyncioMagicMock(return_value=b'{"message": "Test"}')
        with pytest.raises(ComputeConflictError):
            await compute.post("/projects", {"a": "b"})
        assert mock.called
        await compute.close()


@pytest.mark.asyncio
async def test_compute_httpQuery_project(compute):

    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 200
        with patch('gns3server.controller.project.Project.emit_controller_notification') as mock_notification:
            project = Project(name="Test")
            mock_notification.assert_called()
        await compute.post("/projects", project)
        mock.assert_called_with("POST", "https://example.com:84/v3/compute/projects", headers={'content-type': 'application/json'}, data=json.dumps(project.asdict()), auth=None, params=None, chunked=None, timeout=120)
        await compute.close()

# FIXME: https://github.com/aio-libs/aiohttp/issues/2525
# @pytest.mark.asyncio
#async def test_connectNotification(compute):
#
#     ws_mock = AsyncioMagicMock()
#     call = 0
#
#     @pytest.mark.asyncio
#async def receive():
#         nonlocal call
#         call += 1
#         if call == 1:
#             response = MagicMock()
#             response.data = '{"action": "test", "event": {"a": 1}}'
#             response.type = aiohttp.WSMsgType.TEXT
#             return response
#         else:
#             response = MagicMock()
#             response.type = aiohttp.WSMsgType.CLOSED
#             return response
#
#     compute._controller._notification = MagicMock()
#     compute._http_session = AsyncioMagicMock(return_value=ws_mock)
#     compute._http_session.ws_connect = AsyncioMagicMock(return_value=ws_mock)
#     ws_mock.receive = receive
#     await compute._connect_notification()
#
#     compute._controller.notification.dispatch.assert_called_with('test', {'a': 1}, compute_id=compute.id)
#     assert compute._connected is False


# def test_connectNotificationPing(compute, async_run):
#     """
#     When we receive a ping from a compute we update
#     the compute memory and CPU usage
#     """
#     ws_mock = AsyncioMagicMock()
#
#     call = 0
#
#     @pytest.mark.asyncio
#async def receive():
#         nonlocal call
#         call += 1
#         if call == 1:
#             response = MagicMock()
#             response.data = '{"action": "ping", "event": {"cpu_usage_percent": 35.7, "memory_usage_percent": 80.7}}'
#             response.type = aiohttp.WSMsgType.TEST
#             return response
#         else:
#             response = MagicMock()
#             response.type = aiohttp.WSMsgType.CLOSED
#
#     compute._controller._notification = MagicMock()
#     compute._http_session = AsyncioMagicMock(return_value=ws_mock)
#     compute._http_session.ws_connect = AsyncioMagicMock(return_value=ws_mock)
#     ws_mock.receive = receive
#     async_run(compute._connect_notification())
#
#     assert not compute._controller.notification.dispatch.called
#     args, _ = compute._controller.notification.controller_emit.call_args_list[0]
#     assert args[0] == "compute.updated"
#     assert args[1]["memory_usage_percent"] == 80.7
#     assert args[1]["cpu_usage_percent"] == 35.7

@pytest.mark.asyncio
async def test_json(compute):

    compute.user = "test"
    assert compute.asdict() == {
        "compute_id": "my_compute_id",
        "name": compute.name,
        "protocol": "https",
        "host": "example.com",
        "port": 84,
        "user": "test",
        "cpu_usage_percent": 0,
        "memory_usage_percent": 0,
        "disk_usage_percent": 0,
        "connected": True,
        "last_error": None,
        "capabilities": {
            "version": "",
            "platform": "",
            "cpus": 0,
            "memory": 0,
            "disk_size": 0,
            "node_types": []
        }
    }
    assert compute.asdict(topology_dump=True) == {
        "compute_id": "my_compute_id",
        "name": compute.name,
        "protocol": "https",
        "host": "example.com",
        "port": 84,
    }


@pytest.mark.asyncio
async def test_downloadFile(project, compute):

    response = MagicMock()
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        await compute.download_file(project, "test/titi")
    mock.assert_called_with("GET", "https://example.com:84/v3/compute/projects/{}/files/test/titi".format(project.id), auth=None)
    await compute.close()


@pytest.mark.asyncio
async def test_close(compute):

    assert compute.connected is True
    await compute.close()
    assert compute.connected is False


@pytest.mark.asyncio
async def test_update(compute, controller):

    compute._controller._notification = MagicMock()
    compute._controller.save = MagicMock()
    compute.name = "Test"
    compute.host = "example.org"
    compute._connected = True
    await compute.update(name="Test 2")
    assert compute.name == "Test 2"
    assert compute.host == "example.org"
    controller.notification.controller_emit.assert_called_with("compute.updated", compute.asdict())
    assert compute.connected is False
    assert compute._controller.save.called


@pytest.mark.asyncio
async def test_forward_get(compute):

    response = MagicMock()
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        await compute.forward("GET", "qemu", "images")
        mock.assert_called_with("GET", "https://example.com:84/v3/compute/qemu/images", headers={'content-type': 'application/json'}, data=None, auth=None, params=None, chunked=None, timeout=None)
        await compute.close()


@pytest.mark.asyncio
async def test_forward_404(compute):

    response = MagicMock()
    response.status = 404
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(ControllerNotFoundError):
            await compute.forward("GET", "qemu", "images")
        assert mock.called
        await compute.close()


@pytest.mark.asyncio
async def test_forward_post(compute):

    response = MagicMock()
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        await compute.forward("POST", "qemu", "img", data={"id": 42})
        mock.assert_called_with("POST", "https://example.com:84/v3/compute/qemu/img", headers={'content-type': 'application/json'}, data=b'{"id": 42}', auth=None, params=None, chunked=None, timeout=None)
        await compute.close()


@pytest.mark.asyncio
async def test_list_files(project, compute):

    res = [{"path": "test"}]
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=json.dumps(res).encode())
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        assert await compute.list_files(project) == res
        mock.assert_any_call("GET", "https://example.com:84/v3/compute/projects/{}/files".format(project.id), headers={'content-type': 'application/json'}, data=None, auth=None, params=None, chunked=None, timeout=None)
        await compute.close()


@pytest.mark.asyncio
async def test_interfaces(compute):

    res = [
        {
            "id": "vmnet99",
            "ip_address": "172.16.97.1",
            "mac_address": "00:50:56:c0:00:63",
            "name": "vmnet99",
            "netmask": "255.255.255.0",
            "type": "ethernet"
        }
    ]
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=json.dumps(res).encode())
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        assert await compute.interfaces() == res
        mock.assert_any_call("GET", "https://example.com:84/v3/compute/network/interfaces", headers={'content-type': 'application/json'}, data=None, auth=None, params=None, chunked=None, timeout=120)
        await compute.close()


@pytest.mark.asyncio
async def test_get_ip_on_same_subnet(controller):

    compute1 = Compute("compute1", host="192.168.1.1", controller=controller)
    compute1._interfaces_cache = [
        {
            "ip_address": "127.0.0.1",
            "netmask": "255.255.255.255"
        },
        {
            "ip_address": "192.168.2.1",
            "netmask": "255.255.255.0"
        },
        {
            "ip_address": "192.168.1.1",
            "netmask": "255.255.255.0"
        },
    ]

    # Case 1 both host are on the same network
    compute2 = Compute("compute2", host="192.168.1.2", controller=controller)
    compute2._interfaces_cache = [
        {
            "ip_address": "127.0.0.1",
            "netmask": "255.255.255.255"
        },
        {
            "ip_address": "192.168.2.2",
            "netmask": "255.255.255.0"
        },
        {
            "ip_address": "192.168.1.2",
            "netmask": "255.255.255.0"
        }
    ]
    assert await compute1.get_ip_on_same_subnet(compute2) == ("192.168.1.1", "192.168.1.2")

    # Case 2 compute2 host is on a different network but a common interface is available
    compute2 = Compute("compute2", host="127.0.0.1", controller=controller)
    compute2._interfaces_cache = [
        {
            "ip_address": "127.0.0.1",
            "netmask": "255.255.255.255"
        },
        {
            "ip_address": "192.168.4.2",
            "netmask": "255.255.255.0"
        },
        {
            "ip_address": "192.168.1.2",
            "netmask": "255.255.255.0"
        }
    ]
    assert await compute1.get_ip_on_same_subnet(compute2) == ("192.168.1.1", "192.168.1.2")

    #No common interface
    compute2 = Compute("compute2", host="127.0.0.1", controller=controller)
    compute2._interfaces_cache = [
        {
            "ip_address": "127.0.0.1",
            "netmask": "255.255.255.255"
        }
    ]
    with pytest.raises(ValueError):
        await compute1.get_ip_on_same_subnet(compute2)

    # Ignore 169.254 network because it's for Windows special purpose
    compute2 = Compute("compute2", host="192.168.1.2", controller=controller)
    compute1 = Compute("compute1", host="192.168.2.1", controller=controller)
    compute1._interfaces_cache = [
        {
            "ip_address": "127.0.0.1",
            "netmask": "255.255.255.255"
        },
        {
            "ip_address": "169.254.1.1",
            "netmask": "255.255.0.0"
        },
    ]
    compute2._interfaces_cache = [
        {
            "ip_address": "127.0.0.1",
            "netmask": "255.255.255.255"
        },
        {
            "ip_address": "169.254.2.1",
            "netmask": "255.255.0.0"
        },
    ]
    assert await compute1.get_ip_on_same_subnet(compute2) == ('192.168.2.1', '192.168.1.2')


class FakeWebSocket:
    """
    Minimal aiohttp WebSocketResponse stand-in for notification stream tests.
    """

    def __init__(self, frames):
        self._frames = list(frames)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._frames:
            raise StopAsyncIteration
        return self._frames.pop(0)


def _text_frame(payload):
    return SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data=json.dumps(payload))


@pytest.mark.asyncio
async def test_connect_notification_poison_frame_autoreconnects(compute, monkeypatch):
    """
    A malformed frame must not permanently kill the notification stream: the
    error is logged, clients are notified and a reconnection is scheduled.
    """

    emit_mock = MagicMock()
    monkeypatch.setattr(compute._controller.notification, "controller_emit", emit_mock)
    frames = [
        _text_frame({"action": "ping", "event": {"cpu_usage_percent": 10.0, "memory_usage_percent": 20.0, "disk_usage_percent": 30.0}}),
        _text_frame({"event": {"poison": True}}),  # missing "action": raises KeyError in the receive loop
    ]
    session = MagicMock()
    session.closed = False
    session.ws_connect = MagicMock(return_value=FakeWebSocket(frames))
    compute._http_session = session

    # allow the reconnection to be scheduled during the test
    monkeypatch.delattr(sys, "_called_from_test", raising=False)
    from gns3server.api.server import app as gns3_app
    monkeypatch.setattr(gns3_app.state, "exiting", False)

    async def fake_connect():
        compute._reconnect_attempted = True
    monkeypatch.setattr(compute, "connect", fake_connect)

    # must not raise despite the poison frame
    await compute._connect_notification()

    actions = [c.args[0] for c in emit_mock.call_args_list]
    assert actions.count("compute.updated") >= 2  # one for the ping, one for the disconnect
    assert compute._connected is False

    # the reconnection scheduled by the finally block fires after 1 second
    await asyncio.sleep(1.2)
    assert compute._reconnect_attempted is True


@pytest.mark.asyncio
async def test_connect_http_error_notifies_schedules_retry_and_raises(compute, monkeypatch):
    """
    HTTP-level failures (401/403/404...) reach connect() as ControllerError
    subclasses. They must notify clients, schedule a retry and still raise for
    explicit callers. They used to silently kill the fire-and-forget connect()
    task started at controller startup: no notification, no retry.
    """

    compute._connected = False
    emit_mock = MagicMock()
    monkeypatch.setattr(compute._controller.notification, "controller_emit", emit_mock)

    async def raise_unauthorized(*args, **kwargs):
        raise ControllerUnauthorizedError("Invalid authentication for compute 'my_compute_id'")

    monkeypatch.setattr(compute, "_run_http_query", raise_unauthorized)
    monkeypatch.delattr(sys, "_called_from_test", raising=False)
    scheduled_delays = []
    monkeypatch.setattr(asyncio.get_event_loop(), "call_later", lambda delay, callback: scheduled_delays.append(delay))

    with pytest.raises(ControllerUnauthorizedError):
        await compute.connect()

    assert compute._last_error == "Invalid authentication for compute 'my_compute_id'"
    assert compute.connected is False
    actions = [c.args[0] for c in emit_mock.call_args_list]
    assert "compute.updated" in actions
    assert scheduled_delays == [5]  # first exponential backoff delay
