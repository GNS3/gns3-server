from gns3server.modules.dynamips import Hub
from gns3server.modules.dynamips import NIO_Null
import pytest


@pytest.fixture
def hub(request, hypervisor):

    hub = Hub(hypervisor, "hub")
    request.addfinalizer(hub.delete)
    return hub


def test_hub_exists(hub):

    assert hub.list()


def test_add_remove_nio(hub):

    nio = NIO_Null(hub.hypervisor)
    hub.add_nio(nio, 0)  # add NIO to port 0
    assert hub.mapping[0] == nio
    hub.remove_nio(0)  # remove NIO from port 0
    nio.delete()
