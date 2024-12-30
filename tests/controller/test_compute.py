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

import json
import pytest
import aiohttp
from unittest.mock import patch, MagicMock

from gns3server.controller.project import Project
from gns3server.controller.compute import Compute, ComputeConflict
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
    assert compute._getUrl("/test") == "https://localhost:84/v2/compute/test"
    # IPV6 localhost
    compute = Compute("my_compute_id", protocol="https", host="::1", port=84, controller=controller)
    assert compute._getUrl("/test") == "https://[::1]:84/v2/compute/test"

    # Listen on all interfaces aka 0.0.0.0 require us to connect via 127.0.0.1
    compute = Compute("my_compute_id", protocol="https", host="0.0.0.0", port=84, controller=controller)
    assert compute._getUrl("/test") == "https://127.0.0.1:84/v2/compute/test"
    # IPV6
    compute = Compute("my_compute_id", protocol="https", host="::", port=84, controller=controller)
    assert compute._getUrl("/test") == "https://[::1]:84/v2/compute/test"


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


async def test_compute_httpQuery(compute):

    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 200
        await compute.post("/projects", {"a": "b"})
        await compute.close()
        mock.assert_called_with("POST", "https://example.com:84/v2/compute/projects", data=b'{"a": "b"}', headers={'content-type': 'application/json'}, auth=None, chunked=None, timeout=120)
        assert compute._auth is None


async def test_compute_httpQueryAuth(compute):

    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 200

        compute.user = "root"
        compute.password = "toor"
        await compute.post("/projects", {"a": "b"})
        await compute.close()
        mock.assert_called_with("POST", "https://example.com:84/v2/compute/projects", data=b'{"a": "b"}', headers={'content-type': 'application/json'}, auth=compute._auth, chunked=None, timeout=120)
        assert compute._auth.login == "root"
        assert compute._auth.password == "toor"


# async def test_compute_httpQueryNotConnected(compute, controller):
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
#     controller.notification.controller_emit.assert_called_with("compute.updated", compute.__json__())
#     await compute.close()


# async def test_compute_httpQueryNotConnectedGNS3vmNotRunning(compute, controller):
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
#     controller.notification.controller_emit.assert_called_with("compute.updated", compute.__json__())
#     await compute.close()


async def test_compute_httpQueryNotConnectedInvalidVersion(compute):

    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=json.dumps({"version": "1.42.4"}).encode())
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(aiohttp.web.HTTPConflict):
            await compute.post("/projects", {"a": "b"})
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, chunked=None, timeout=120)
        await compute.close()


async def test_compute_httpQueryNotConnectedNonGNS3Server(compute):

    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=b'Blocked by super antivirus')
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(aiohttp.web.HTTPConflict):
            await compute.post("/projects", {"a": "b"})
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, chunked=None, timeout=120)
        await compute.close()


async def test_compute_httpQueryNotConnectedNonGNS3Server2(compute):

    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=b'{}')
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(aiohttp.web.HTTPConflict):
            await compute.post("/projects", {"a": "b"})
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, chunked=None, timeout=120)


async def test_compute_httpQueryError(compute):

    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 404
        with pytest.raises(aiohttp.web.HTTPNotFound):
            await compute.post("/projects", {"a": "b"})
        assert mock.called
        await compute.close()


async def test_compute_httpQueryConflictError(compute):

    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 409
        response.read = AsyncioMagicMock(return_value=b'{"message": "Test"}')
        with pytest.raises(ComputeConflict):
            await compute.post("/projects", {"a": "b"})
        assert mock.called
        await compute.close()


async def test_compute_httpQuery_project(compute):

    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 200
        with patch('gns3server.controller.project.Project.emit_controller_notification') as mock_notification:
            project = Project(name="Test")
            mock_notification.assert_called()
        await compute.post("/projects", project)
        mock.assert_called_with("POST", "https://example.com:84/v2/compute/projects", data=json.dumps(project.__json__()), headers={'content-type': 'application/json'}, auth=None, chunked=None, timeout=120)
        await compute.close()

# FIXME: https://github.com/aio-libs/aiohttp/issues/2525
# async def test_connectNotification(compute):
#
#     ws_mock = AsyncioMagicMock()
#     call = 0
#
#     async def receive():
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
#     async def receive():
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

async def test_json(compute):

    compute.user = "test"
    assert compute.__json__() == {
        "compute_id": "my_compute_id",
        "name": compute.name,
        "protocol": "https",
        "host": "example.com",
        "port": 84,
        "user": "test",
        "cpu_usage_percent": None,
        "memory_usage_percent": None,
        "connected": True,
        "last_error": None,
        "capabilities": {
            "version": None,
            "node_types": []
        }
    }
    assert compute.__json__(topology_dump=True) == {
        "compute_id": "my_compute_id",
        "name": compute.name,
        "protocol": "https",
        "host": "example.com",
        "port": 84,
    }


async def test_downloadFile(project, compute):

    response = MagicMock()
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        await compute.download_file(project, "test/titi")
    mock.assert_called_with("GET", "https://example.com:84/v2/compute/projects/{}/files/test/titi".format(project.id), auth=None)
    await compute.close()


async def test_close(compute):

    assert compute.connected is True
    await compute.close()
    assert compute.connected is False


async def test_update(compute, controller):

    compute._controller._notification = MagicMock()
    compute._controller.save = MagicMock()
    compute.name = "Test"
    compute.host = "example.org"
    compute._connected = True
    await compute.update(name="Test 2")
    assert compute.name == "Test 2"
    assert compute.host == "example.org"
    controller.notification.controller_emit.assert_called_with("compute.updated", compute.__json__())
    assert compute.connected is False
    assert compute._controller.save.called


async def test_forward_get(compute):

    response = MagicMock()
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        await compute.forward("GET", "qemu", "images")
        mock.assert_called_with("GET", "https://example.com:84/v2/compute/qemu/images", auth=None, data=None, headers={'content-type': 'application/json'}, chunked=None, timeout=None)
        await compute.close()


async def test_forward_404(compute):

    response = MagicMock()
    response.status = 404
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
            await compute.forward("GET", "qemu", "images")
        assert mock.called
        await compute.close()


async def test_forward_post(compute):

    response = MagicMock()
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        await compute.forward("POST", "qemu", "img", data={"id": 42})
        mock.assert_called_with("POST", "https://example.com:84/v2/compute/qemu/img", auth=None, data=b'{"id": 42}', headers={'content-type': 'application/json'}, chunked=None, timeout=None)
        await compute.close()


async def test_images(compute):
    """
    Will return image on compute
    """

    response = MagicMock()
    response.status = 200
    response.read = AsyncioMagicMock(return_value=json.dumps([{
        "filename": "linux.qcow2",
        "path": "linux.qcow2",
        "md5sum": "d41d8cd98f00b204e9800998ecf8427e",
        "filesize": 0}]).encode())
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        images = await compute.images("qemu")
        mock.assert_called_with("GET", "https://example.com:84/v2/compute/qemu/images", auth=None, data=None, headers={'content-type': 'application/json'}, chunked=None, timeout=None)
        await compute.close()

    assert images == [
        {"filename": "linux.qcow2", "path": "linux.qcow2", "md5sum": "d41d8cd98f00b204e9800998ecf8427e", "filesize": 0}
    ]


async def test_list_files(project, compute):

    res = [{"path": "test"}]
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=json.dumps(res).encode())
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        assert await compute.list_files(project) == res
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/projects/{}/files".format(project.id), auth=None, chunked=None, data=None, headers={'content-type': 'application/json'}, timeout=None)
        await compute.close()


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
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/network/interfaces", auth=None, chunked=None, data=None, headers={'content-type': 'application/json'}, timeout=120)
        await compute.close()


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
