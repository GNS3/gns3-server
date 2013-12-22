from gns3server.modules.dynamips import Bridge
from gns3server.modules.dynamips import NIO_Null
import pytest


@pytest.fixture
def bridge(request, hypervisor):

    bridge = Bridge(hypervisor, "bridge")
    request.addfinalizer(bridge.delete)
    return bridge


def test_bridge_exists(bridge):

    assert bridge.list()


def test_rename_bridge(bridge):

    bridge.rename("new bridge")
    assert bridge.name == "new bridge"


def test_add_remove_nio(bridge):

    nio = NIO_Null(bridge.hypervisor)
    bridge.add_nio(nio)
    assert bridge.nios
    bridge.remove_nio(nio)
    nio.delete()
