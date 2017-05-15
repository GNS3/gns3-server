#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import os
import json
import pytest
import socket
import aiohttp
import asyncio
from unittest.mock import patch, MagicMock

from gns3server.controller.project import Project
from gns3server.controller.compute import Compute, ComputeError, ComputeConflict
from gns3server.version import __version__
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


def test_compute_httpQuery(compute, async_run):
    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 200

        async_run(compute.post("/projects", {"a": "b"}))
        mock.assert_called_with("POST", "https://example.com:84/v2/compute/projects", data='{"a": "b"}', headers={'content-type': 'application/json'}, auth=None, chunked=False, timeout=20)
        assert compute._auth is None


def test_compute_httpQueryAuth(compute, async_run):
    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 200

        compute.user = "root"
        compute.password = "toor"
        async_run(compute.post("/projects", {"a": "b"}))
        mock.assert_called_with("POST", "https://example.com:84/v2/compute/projects", data='{"a": "b"}', headers={'content-type': 'application/json'}, auth=compute._auth, chunked=False, timeout=20)
        assert compute._auth.login == "root"
        assert compute._auth.password == "toor"


def test_compute_httpQueryNotConnected(compute, controller, async_run):
    controller._notification = MagicMock()
    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=json.dumps({"version": __version__}).encode())
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        async_run(compute.post("/projects", {"a": "b"}))
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, chunked=False, timeout=20)
        mock.assert_any_call("POST", "https://example.com:84/v2/compute/projects", data='{"a": "b"}', headers={'content-type': 'application/json'}, auth=None, chunked=False, timeout=20)
    assert compute._connected
    assert compute._capabilities["version"] == __version__
    controller.notification.emit.assert_called_with("compute.updated", compute.__json__())


def test_compute_httpQueryNotConnectedGNS3vmNotRunning(compute, controller, async_run):
    """
    We are not connected to the remote and it's a GNS3 VM. So we need to start it
    """
    controller._notification = MagicMock()
    controller.gns3vm = AsyncioMagicMock()
    controller.gns3vm.running = False

    compute._id = "vm"
    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=json.dumps({"version": __version__}).encode())
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        async_run(compute.post("/projects", {"a": "b"}))
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, chunked=False, timeout=20)
        mock.assert_any_call("POST", "https://example.com:84/v2/compute/projects", data='{"a": "b"}', headers={'content-type': 'application/json'}, auth=None, chunked=False, timeout=20)

    assert controller.gns3vm.start.called
    assert compute._connected
    assert compute._capabilities["version"] == __version__
    controller.notification.emit.assert_called_with("compute.updated", compute.__json__())


def test_compute_httpQueryNotConnectedInvalidVersion(compute, async_run):
    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=json.dumps({"version": "1.42.4"}).encode())
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(aiohttp.web.HTTPConflict):
            async_run(compute.post("/projects", {"a": "b"}))
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, chunked=False, timeout=20)


def test_compute_httpQueryNotConnectedNonGNS3Server(compute, async_run):
    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=b'Blocked by super antivirus')
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(aiohttp.web.HTTPConflict):
            async_run(compute.post("/projects", {"a": "b"}))
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, chunked=False, timeout=20)


def test_compute_httpQueryNotConnectedNonGNS3Server2(compute, async_run):
    compute._connected = False
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=b'{}')
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(aiohttp.web.HTTPConflict):
            async_run(compute.post("/projects", {"a": "b"}))
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/capabilities", headers={'content-type': 'application/json'}, data=None, auth=None, chunked=False, timeout=20)


def test_compute_httpQueryError(compute, async_run):
    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 404

        with pytest.raises(aiohttp.web.HTTPNotFound):
            async_run(compute.post("/projects", {"a": "b"}))


def test_compute_httpQueryConflictError(compute, async_run):
    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 409
        response.read = AsyncioMagicMock(return_value=b'{"message": "Test"}')

        with pytest.raises(ComputeConflict):
            async_run(compute.post("/projects", {"a": "b"}))


def test_compute_httpQuery_project(compute, async_run):
    response = MagicMock()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        response.status = 200

        project = Project(name="Test")
        async_run(compute.post("/projects", project))
        mock.assert_called_with("POST", "https://example.com:84/v2/compute/projects", data=json.dumps(project.__json__()), headers={'content-type': 'application/json'}, auth=None, chunked=False, timeout=20)


def test_connectNotification(compute, async_run):
    ws_mock = AsyncioMagicMock()

    call = 0

    @asyncio.coroutine
    def receive():
        nonlocal call
        call += 1
        if call == 1:
            response = MagicMock()
            response.data = '{"action": "test", "event": {"a": 1}}'
            response.tp = aiohttp.MsgType.text
            return response
        else:
            response = MagicMock()
            response.tp = aiohttp.MsgType.closed
            return response

    compute._controller._notification = MagicMock()
    compute._http_session = AsyncioMagicMock(return_value=ws_mock)
    compute._http_session.ws_connect = AsyncioMagicMock(return_value=ws_mock)
    ws_mock.receive = receive
    async_run(compute._connect_notification())

    compute._controller.notification.dispatch.assert_called_with('test', {'a': 1}, compute_id=compute.id)
    assert compute._connected is False


def test_connectNotificationPing(compute, async_run):
    """
    When we receive a ping from a compute we update
    the compute memory and CPU usage
    """
    ws_mock = AsyncioMagicMock()

    call = 0

    @asyncio.coroutine
    def receive():
        nonlocal call
        call += 1
        if call == 1:
            response = MagicMock()
            response.data = '{"action": "ping", "event": {"cpu_usage_percent": 35.7, "memory_usage_percent": 80.7}}'
            response.tp = aiohttp.MsgType.text
            return response
        else:
            response = MagicMock()
            response.tp = aiohttp.MsgType.closed
            return response

    compute._controller._notification = MagicMock()
    compute._http_session = AsyncioMagicMock(return_value=ws_mock)
    compute._http_session.ws_connect = AsyncioMagicMock(return_value=ws_mock)
    ws_mock.receive = receive
    async_run(compute._connect_notification())

    assert not compute._controller.notification.dispatch.called
    args, _ = compute._controller.notification.emit.call_args_list[0]
    assert args[0] == "compute.updated"
    assert args[1]["memory_usage_percent"] == 80.7
    assert args[1]["cpu_usage_percent"] == 35.7


def test_json(compute):
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


def test_streamFile(project, async_run, compute):
    response = MagicMock()
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        async_run(compute.stream_file(project, "test/titi"))
    mock.assert_called_with("GET", "https://example.com:84/v2/compute/projects/{}/stream/test/titi".format(project.id), auth=None, timeout=None)


def test_downloadFile(project, async_run, compute):
    response = MagicMock()
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        async_run(compute.download_file(project, "test/titi"))
    mock.assert_called_with("GET", "https://example.com:84/v2/compute/projects/{}/files/test/titi".format(project.id), auth=None)


def test_close(compute, async_run):
    assert compute.connected is True
    async_run(compute.close())
    assert compute.connected is False


def test_update(compute, controller, async_run):
    compute._controller._notification = MagicMock()
    compute._controller.save = MagicMock()
    compute.name = "Test"
    compute.host = "example.org"
    compute._connected = True
    async_run(compute.update(name="Test 2"))
    assert compute.name == "Test 2"
    assert compute.host == "example.org"
    controller.notification.emit.assert_called_with("compute.updated", compute.__json__())
    assert compute.connected is False
    assert compute._controller.save.called


def test_forward_get(compute, async_run):
    response = MagicMock()
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        async_run(compute.forward("GET", "qemu", "images"))
        mock.assert_called_with("GET", "https://example.com:84/v2/compute/qemu/images", auth=None, data=None, headers={'content-type': 'application/json'}, chunked=False, timeout=None)


def test_forward_404(compute, async_run):
    response = MagicMock()
    response.status = 404
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
            async_run(compute.forward("GET", "qemu", "images"))


def test_forward_post(compute, async_run):
    response = MagicMock()
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        async_run(compute.forward("POST", "qemu", "img", data={"id": 42}))
        mock.assert_called_with("POST", "https://example.com:84/v2/compute/qemu/img", auth=None, data='{"id": 42}', headers={'content-type': 'application/json'}, chunked=False, timeout=None)


def test_images(compute, async_run, images_dir):
    """
    Will return image on compute and on controller
    """
    response = MagicMock()
    response.status = 200
    response.read = AsyncioMagicMock(return_value=json.dumps([{
        "filename": "linux.qcow2",
        "path": "linux.qcow2",
        "md5sum": "d41d8cd98f00b204e9800998ecf8427e",
        "filesize": 0}]).encode())
    open(os.path.join(images_dir, "QEMU", "asa.qcow2"), "w+").close()
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        images = async_run(compute.images("qemu"))
        mock.assert_called_with("GET", "https://example.com:84/v2/compute/qemu/images", auth=None, data=None, headers={'content-type': 'application/json'}, chunked=False, timeout=None)

    assert images == [
        {"filename": "asa.qcow2", "path": "asa.qcow2", "md5sum": "d41d8cd98f00b204e9800998ecf8427e", "filesize": 0},
        {"filename": "linux.qcow2", "path": "linux.qcow2", "md5sum": "d41d8cd98f00b204e9800998ecf8427e", "filesize": 0}
    ]


def test_list_files(project, async_run, compute):
    res = [{"path": "test"}]
    response = AsyncioMagicMock()
    response.read = AsyncioMagicMock(return_value=json.dumps(res).encode())
    response.status = 200
    with asyncio_patch("aiohttp.ClientSession.request", return_value=response) as mock:
        assert async_run(compute.list_files(project)) == res
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/projects/{}/files".format(project.id), auth=None, chunked=False, data=None, headers={'content-type': 'application/json'}, timeout=120)


def test_interfaces(project, async_run, compute):
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
        assert async_run(compute.interfaces()) == res
        mock.assert_any_call("GET", "https://example.com:84/v2/compute/network/interfaces", auth=None, chunked=False, data=None, headers={'content-type': 'application/json'}, timeout=20)


def test_get_ip_on_same_subnet(controller, async_run):
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
    assert async_run(compute1.get_ip_on_same_subnet(compute2)) == ("192.168.1.1", "192.168.1.2")

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
    assert async_run(compute1.get_ip_on_same_subnet(compute2)) == ("192.168.1.1", "192.168.1.2")

    #No common interface
    compute2 = Compute("compute2", host="127.0.0.1", controller=controller)
    compute2._interfaces_cache = [
        {
            "ip_address": "127.0.0.1",
            "netmask": "255.255.255.255"
        }
    ]
    with pytest.raises(ValueError):
        async_run(compute1.get_ip_on_same_subnet(compute2))

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
    assert async_run(compute1.get_ip_on_same_subnet(compute2)) == ('192.168.2.1', '192.168.1.2')
