# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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


import pytest
import socket
import asyncio
import tempfile
import shutil
import os
import sys
from aiohttp import web
from unittest.mock import patch


sys._called_from_test = True
sys.original_platform = sys.platform

# Prevent execution of external binaries
os.environ["PATH"] = tempfile.mkdtemp()

from gns3server.config import Config
from gns3server.web.route import Route
# TODO: get rid of *
from gns3server.handlers import *
from gns3server.compute import MODULES
from gns3server.compute.port_manager import PortManager
from gns3server.compute.project_manager import ProjectManager
from gns3server.controller import Controller
from tests.handlers.api.base import Query


@pytest.yield_fixture
def restore_original_path():
    """
    Temporary restore a standard path environnement. This allow
    to run external binaries.
    """
    os.environ["PATH"] = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    yield
    os.environ["PATH"] = tempfile.mkdtemp()


@pytest.yield_fixture(scope="session")
def loop(request):
    """Return an event loop and destroy it at the end of test"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)  # Replace main loop to avoid conflict between tests
    yield loop
    #loop.close()
    asyncio.set_event_loop(None)


def _get_unused_port():
    """ Return an unused port on localhost. In rare occasion it can return
    an already used port (race condition)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    addr, port = s.getsockname()
    s.close()
    return port


@pytest.yield_fixture
def http_server(request, loop, port_manager, monkeypatch, controller):
    """A GNS3 server"""

    app = web.Application()
    for method, route, handler in Route.get_routes():
        app.router.add_route(method, route, handler)

    host = "localhost"

    # We try multiple time. Because on Travis test can fail when because the port is taken by someone else
    for i in range(0, 5):
        port = _get_unused_port()
        try:
            srv = loop.create_server(app.make_handler(), host, port)
            srv = loop.run_until_complete(srv)
        except OSError:
            pass
        else:
            break

    yield (host, port)

    loop.run_until_complete(controller.stop())
    for module in MODULES:
        instance = module.instance()
        monkeypatch.setattr('gns3server.compute.virtualbox.virtualbox_vm.VirtualBoxVM.close', lambda self: True)
        loop.run_until_complete(instance.unload())
    srv.close()
    srv.wait_closed()


@pytest.fixture
def http_root(loop, http_server):
    """
    Return an helper allowing you to call the server without any prefix
    """
    host, port = http_server
    return Query(loop, host=host, port=port)


@pytest.fixture
def http_controller(loop, http_server):
    """
    Return an helper allowing you to call the server API without any prefix
    """
    host, port = http_server
    return Query(loop, host=host, port=port, api_version=2)


@pytest.fixture
def http_compute(loop, http_server):
    """
    Return an helper allowing you to call the hypervisor API via HTTP
    """
    host, port = http_server
    return Query(loop, host=host, port=port, prefix="/compute", api_version=2)


@pytest.fixture(scope="function")
def project(tmpdir):
    """A GNS3 lab"""

    p = ProjectManager.instance().create_project(project_id="a1e920ca-338a-4e9f-b363-aa607b09dd80")
    return p


@pytest.fixture(scope="function")
def port_manager():
    """An instance of port manager"""
    PortManager._instance = None
    p = PortManager.instance()
    p.console_host = "127.0.0.1"
    return p


@pytest.fixture(scope="function")
def free_console_port(request, port_manager, project):
    """Get a free TCP port"""

    # In case of already use ports we will raise an exception
    port = port_manager.get_free_tcp_port(project)
    # We release the port immediately in order to allow
    # the test do whatever the test want
    port_manager.release_tcp_port(port, project)
    return port


@pytest.fixture
def ethernet_device():
    import psutil
    return sorted(psutil.net_if_addrs().keys())[0]


@pytest.fixture
def controller_config_path(tmpdir):
    return str(tmpdir / "config" / "gns3_controller.conf")


@pytest.fixture
def controller(tmpdir, controller_config_path):
    Controller._instance = None
    controller = Controller.instance()
    controller._config_file = controller_config_path
    controller._settings = {}
    return controller


@pytest.fixture
def config():
    config = Config.instance()
    config.clear()
    return config


@pytest.yield_fixture(autouse=True)
def run_around_tests(monkeypatch, port_manager, controller, config):
    """
    This setup a temporay project file environnement around tests
    """

    tmppath = tempfile.mkdtemp()

    for module in MODULES:
        module._instance = None

    os.makedirs(os.path.join(tmppath, 'projects'))
    config.set("Server", "projects_path", os.path.join(tmppath, 'projects'))
    config.set("Server", "symbols_path", os.path.join(tmppath, 'symbols'))
    config.set("Server", "images_path", os.path.join(tmppath, 'images'))
    config.set("Server", "ubridge_path", os.path.join(tmppath, 'bin', 'ubridge'))
    config.set("Server", "auth", False)

    # Prevent executions of the VM if we forgot to mock something
    config.set("VirtualBox", "vboxmanage_path", tmppath)
    config.set("VPCS", "vpcs_path", tmppath)
    config.set("VMware", "vmrun_path", tmppath)

    # Force turn off KVM because it's not available on CI
    config.set("Qemu", "enable_kvm", False)

    monkeypatch.setattr("gns3server.utils.path.get_default_project_directory", lambda *args: os.path.join(tmppath, 'projects'))

    # Force sys.platform to the original value. Because it seem not be restore correctly at each tests
    sys.platform = sys.original_platform

    yield

    # An helper should not raise Exception
    try:
        shutil.rmtree(tmppath)
    except:
        pass


@pytest.fixture
def images_dir(config):
    """
    Get the location of images
    """
    path = config.get_section_config("Server").get("images_path")
    os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(path, "QEMU"))
    os.makedirs(os.path.join(path, "IOU"))
    return path


@pytest.fixture
def symbols_dir(config):
    """
    Get the location of symbols
    """
    path = config.get_section_config("Server").get("symbols_path")
    os.makedirs(path, exist_ok=True)
    print(path)
    return path


@pytest.fixture
def projects_dir(config):
    """
    Get the location of images
    """
    path = config.get_section_config("Server").get("projects_path")
    os.makedirs(path, exist_ok=True)
    return path


@pytest.fixture
def ubridge_path(config):
    """
    Get the location of a fake ubridge
    """
    path = config.get_section_config("Server").get("ubridge_path")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w+').close()
    return path


@pytest.yield_fixture
def darwin_platform():
    """
    Change sys.plaform to Darwin
    """
    old_platform = sys.platform
    sys.platform = "darwin10.10"
    yield
    sys.plaform = old_platform


@pytest.yield_fixture
def windows_platform():
    """
    Change sys.plaform to Windows
    """
    old_platform = sys.platform
    sys.platform = "win10"
    yield
    sys.plaform = old_platform


@pytest.yield_fixture
def linux_platform():
    """
    Change sys.plaform to Linux
    """
    old_platform = sys.platform
    sys.platform = "linuxdebian"
    yield
    sys.plaform = old_platform


@pytest.fixture
def async_run(loop):
    """
    Shortcut for running in asyncio loop
    """
    return lambda x: loop.run_until_complete(asyncio.async(x))


@pytest.yield_fixture
def on_gns3vm(linux_platform):
    """
    Mock the hostname to  emulate the GNS3 VM
    """
    with patch("gns3server.utils.interfaces.interfaces", return_value=[
            {"name": "eth0", "special": False, "type": "ethernet"},
            {"name": "eth1", "special": False, "type": "ethernet"},
            {"name": "virbr0", "special": True, "type": "ethernet"}]):
        with patch("socket.gethostname", return_value="gns3vm"):
            yield
