from gns3server.modules.dynamips import FrameRelaySwitch
from gns3server.modules.dynamips import NIO_Null
from gns3server.modules.dynamips import DynamipsError
import pytest


@pytest.fixture
def frsw(request, hypervisor):

    frsw = FrameRelaySwitch(hypervisor, "Frane Relay switch")
    request.addfinalizer(frsw.delete)
    return frsw


def test_frsw_exists(frsw):

    assert frsw.list()


def test_rename_frsw(frsw):

    frsw.name = "new Frame Relay switch"
    assert frsw.name == "new Frame Relay switch"


def test_add_remove_nio(frsw):

    nio = NIO_Null(frsw.hypervisor)
    frsw.add_nio(nio, 0)  # add NIO on port 0
    assert frsw.nios
    frsw.remove_nio(0)  # remove NIO from port 0
    nio.delete()


def test_add_nio_already_allocated_port(frsw):

    nio = NIO_Null(frsw.hypervisor)
    frsw.add_nio(nio, 0)  # add NIO on port 0
    with pytest.raises(DynamipsError):
        frsw.add_nio(nio, 0)
        nio.delete()


def test_remove_nio_non_allocated_port(frsw):

    with pytest.raises(DynamipsError):
        frsw.remove_nio(0)  # remove NIO from port 0


def test_vc(frsw):

    nio1 = NIO_Null(frsw.hypervisor)
    frsw.add_nio(nio1, 0)  # add NIO on port 0
    nio2 = NIO_Null(frsw.hypervisor)
    frsw.add_nio(nio1, 1)  # add NIO on port 1
    frsw.map_vc(0, 10, 1, 20)  # port 0 DLCI 10 to port 1 DLCI 20 (unidirectional)
    frsw.map_vc(1, 20, 0, 10)  # port 1 DLCI 20 to port 0 DLCI 10 (unidirectional)
    assert frsw.mapping[(0, 10)] == (1, 20)
    assert frsw.mapping[(1, 20)] == (0, 10)
    frsw.unmap_vc(0, 10, 1, 20)  # port 0 DLCI 10 to port 1 DLCI 20 (unidirectional)
    frsw.unmap_vc(1, 20, 0, 10)  # port 1 DLCI 20 to port 0 DLCI 10 (unidirectional)
    frsw.remove_nio(0)
    frsw.remove_nio(1)
    nio1.delete()
    nio2.delete()
