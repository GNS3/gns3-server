from gns3server.modules.dynamips import ATMSwitch
from gns3server.modules.dynamips import NIO_Null
from gns3server.modules.dynamips import DynamipsError
import pytest


@pytest.fixture
def atmsw(request, hypervisor):

    atmsw = ATMSwitch(hypervisor, "ATM switch")
    request.addfinalizer(atmsw.delete)
    return atmsw


def test_atmsw_exists(atmsw):

    assert atmsw.list()


def test_rename_atmsw(atmsw):

    atmsw.rename("new ATM switch")
    assert atmsw.name == "new ATM switch"


def test_add_remove_nio(atmsw):

    nio = NIO_Null(atmsw.hypervisor)
    atmsw.add_nio(nio, 0)  # add NIO on port 0
    assert atmsw.nios
    atmsw.remove_nio(0)  # remove NIO from port 0
    nio.delete()


def test_add_nio_already_allocated_port(atmsw):

    nio = NIO_Null(atmsw.hypervisor)
    atmsw.add_nio(nio, 0)  # add NIO on port 0
    with pytest.raises(DynamipsError):
        atmsw.add_nio(nio, 0)
        nio.delete()


def test_remove_nio_non_allocated_port(atmsw):

    with pytest.raises(DynamipsError):
        atmsw.remove_nio(0)  # remove NIO from port 0


def test_vp(atmsw):

    nio1 = NIO_Null(atmsw.hypervisor)
    atmsw.add_nio(nio1, 0)  # add NIO on port 0
    nio2 = NIO_Null(atmsw.hypervisor)
    atmsw.add_nio(nio1, 1)  # add NIO on port 1
    atmsw.map_vp(0, 10, 1, 20)  # port 0 VP 10 to port 1 VP 20 (unidirectional)
    atmsw.map_vp(1, 20, 0, 10)  # port 1 VP 20 to port 0 VP 10 (unidirectional)
    assert atmsw.mapping[(0, 10)] == (1, 20)
    assert atmsw.mapping[(1, 20)] == (0, 10)
    atmsw.unmap_vp(0, 10, 1, 20)  # port 0 VP 10 to port 1 VP 20 (unidirectional)
    atmsw.unmap_vp(1, 20, 0, 10)  # port 1 VP 20 to port 0 VP 10 (unidirectional)
    atmsw.remove_nio(0)
    atmsw.remove_nio(1)
    nio1.delete()
    nio2.delete()


def test_pvc(atmsw):

    nio1 = NIO_Null(atmsw.hypervisor)
    atmsw.add_nio(nio1, 0)  # add NIO on port 0
    nio2 = NIO_Null(atmsw.hypervisor)
    atmsw.add_nio(nio1, 1)  # add NIO on port 1
    atmsw.map_pvc(0, 10, 10, 1, 20, 20)  # port 0 VC 10:10 to port 1 VP 20:20 (unidirectional)
    atmsw.map_pvc(1, 20, 20, 0, 10, 10)  # port 1 VC 20:20 to port 0 VC 10:10 (unidirectional)
    assert atmsw.mapping[(0, 10, 10)] == (1, 20, 20)
    assert atmsw.mapping[(1, 20, 20)] == (0, 10, 10)
    atmsw.unmap_pvc(0, 10, 10, 1, 20, 20)  # port 0 VC 10:10 to port 1 VP 20:20 (unidirectional)
    atmsw.unmap_pvc(1, 20, 20, 0, 10, 10)  # port 1 VC 20:20 to port 0 VC 10:10 (unidirectional)
    atmsw.remove_nio(0)
    atmsw.remove_nio(1)
    nio1.delete()
    nio2.delete()
