import pytest
import asyncio
import tempfile
import shutil
import weakref

from aiohttp import web
from unittest.mock import MagicMock, patch
from pathlib import Path

from gns3server.web.route import Route
from gns3server.controller import Controller
from gns3server.config import Config
from gns3server.compute import MODULES
from gns3server.compute.port_manager import PortManager
from gns3server.compute.project_manager import ProjectManager
# this import will register all handlers
from gns3server.handlers import *

from .handlers.api.base import Query

sys._called_from_test = True
sys.original_platform = sys.platform


if sys.platform.startswith("win"):
    @pytest.fixture(scope="session")
    def loop(request):
        """Return an event loop and destroy it at the end of test"""

        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)  # Replace main loop to avoid conflict between tests
        yield loop
        asyncio.set_event_loop(None)


@pytest.fixture(scope='function')
async def http_client(aiohttp_client):

    app = web.Application()
    app['websockets'] = weakref.WeakSet()
    for method, route, handler in Route.get_routes():
        app.router.add_route(method, route, handler)
    return await aiohttp_client(app)


@pytest.fixture
def controller_config_path(tmpdir):

    return str(tmpdir / "config" / "gns3_controller.conf")


@pytest.fixture
def controller(tmpdir, controller_config_path):

    Controller._instance = None
    controller = Controller.instance()
    os.makedirs(os.path.dirname(controller_config_path), exist_ok=True)
    Path(controller_config_path).touch()
    controller._config_file = controller_config_path
    controller._config_loaded = True
    return controller


@pytest.fixture
def compute(controller):

    compute = MagicMock()
    compute.id = "example.com"
    controller._computes = {"example.com": compute}
    return compute


@pytest.fixture
async def project(tmpdir, controller):

    return await controller.add_project(name="Test")


@pytest.fixture
def compute_project(tmpdir):

    return ProjectManager.instance().create_project(project_id="a1e920ca-338a-4e9f-b363-aa607b09dd80")


@pytest.fixture
def compute_api(http_client):
    """
    Return an helper allowing you to call the hypervisor API via HTTP
    """

    return Query(http_client, prefix="/compute", api_version=2)


@pytest.fixture
def controller_api(http_client, controller):
    """
    Return an helper allowing you to call the server API without any prefix
    """

    return Query(http_client, api_version=2)


@pytest.fixture
def config():

    config = Config.instance()
    config.clear()
    return config


@pytest.fixture
def images_dir(config):
    """
    Get the location of images
    """

    path = config.get_section_config("Server").get("images_path")
    os.makedirs(path, exist_ok=True)
    os.makedirs(os.path.join(path, "QEMU"), exist_ok=True)
    os.makedirs(os.path.join(path, "IOU"), exist_ok=True)
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


@pytest.fixture(scope="function")
def port_manager():
    """An instance of port manager"""

    PortManager._instance = None
    p = PortManager.instance()
    p.console_host = "127.0.0.1"
    return p


@pytest.fixture(scope="function")
def free_console_port(port_manager, compute_project):
    """Get a free TCP port"""

    # In case of already use ports we will raise an exception
    port = port_manager.get_free_tcp_port(compute_project)
    # We release the port immediately in order to allow
    # the test do whatever the test want
    port_manager.release_tcp_port(port, compute_project)
    return port


@pytest.fixture
def darwin_platform():
    """
    Change sys.plaform to Darwin
    """

    old_platform = sys.platform
    sys.platform = "darwin10.10"
    yield
    sys.plaform = old_platform


@pytest.fixture
def windows_platform():
    """
    Change sys.platform to Windows
    """

    old_platform = sys.platform
    sys.platform = "win10"
    yield
    sys.plaform = old_platform


@pytest.fixture
def linux_platform():
    """
    Change sys.platform to Linux
    """

    old_platform = sys.platform
    sys.platform = "linuxdebian"
    yield
    sys.plaform = old_platform


@pytest.fixture
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


@pytest.fixture
def ethernet_device():

    import psutil
    return sorted(psutil.net_if_addrs().keys())[0]


@pytest.fixture
def ubridge_path(config):
    """
    Get the location of a fake ubridge
    """

    path = config.get_section_config("Server").get("ubridge_path")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w+').close()
    return path


@pytest.fixture(autouse=True)
def run_around_tests(monkeypatch, config, port_manager):#port_manager, controller, config):
    """
    This setup a temporary project file environment around tests
    """

    tmppath = tempfile.mkdtemp()

    for module in MODULES:
        module._instance = None

    os.makedirs(os.path.join(tmppath, 'projects'))
    config.set("Server", "projects_path", os.path.join(tmppath, 'projects'))
    config.set("Server", "symbols_path", os.path.join(tmppath, 'symbols'))
    config.set("Server", "images_path", os.path.join(tmppath, 'images'))
    config.set("Server", "appliances_path", os.path.join(tmppath, 'appliances'))
    config.set("Server", "ubridge_path", os.path.join(tmppath, 'bin', 'ubridge'))
    config.set("Server", "auth", False)

    # Prevent executions of the VM if we forgot to mock something
    config.set("VirtualBox", "vboxmanage_path", tmppath)
    config.set("VPCS", "vpcs_path", tmppath)
    config.set("VMware", "vmrun_path", tmppath)
    config.set("Dynamips", "dynamips_path", tmppath)

    # Force turn off KVM because it's not available on CI
    config.set("Qemu", "enable_kvm", False)

    monkeypatch.setattr("gns3server.utils.path.get_default_project_directory", lambda *args: os.path.join(tmppath, 'projects'))

    # Force sys.platform to the original value. Because it seem not be restore correctly at each tests
    sys.platform = sys.original_platform

    yield

    # An helper should not raise Exception
    try:
        shutil.rmtree(tmppath)
    except BaseException:
        pass
