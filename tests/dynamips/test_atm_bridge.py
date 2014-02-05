from gns3server.modules.dynamips import ATMBridge
from gns3server.modules.dynamips import NIO_Null
from gns3server.modules.dynamips import DynamipsError
import pytest


@pytest.fixture
def atm_bridge(request, hypervisor):

    atm_bridge = ATMBridge(hypervisor, "ATM bridge")
    request.addfinalizer(atm_bridge.delete)
    return atm_bridge


def test_atm_bridge_exists(atm_bridge):

    assert atm_bridge.list()


def test_rename_atm_bridge(atm_bridge):

    atm_bridge.name = "new ATM bridge"
    assert atm_bridge.name == "new ATM bridge"


def test_add_remove_nio(atm_bridge):

    nio = NIO_Null(atm_bridge.hypervisor)
    atm_bridge.add_nio(nio, 0)  # add NIO on port 0
    assert atm_bridge.nios
    atm_bridge.remove_nio(0)  # remove NIO from port 0
    nio.delete()


def test_add_nio_already_allocated_port(atm_bridge):

    nio = NIO_Null(atm_bridge.hypervisor)
    atm_bridge.add_nio(nio, 0)  # add NIO on port 0
    with pytest.raises(DynamipsError):
        atm_bridge.add_nio(nio, 0)
        nio.delete()


def test_remove_nio_non_allocated_port(atm_bridge):

    with pytest.raises(DynamipsError):
        atm_bridge.remove_nio(0)  # remove NIO from port 0


def test_bridge(atm_bridge):

    nio1 = NIO_Null(atm_bridge.hypervisor)
    atm_bridge.add_nio(nio1, 0)  # add NIO on port 0 (Ethernet NIO)
    nio2 = NIO_Null(atm_bridge.hypervisor)
    atm_bridge.add_nio(nio1, 1)  # add NIO on port 1 (ATM NIO)
    atm_bridge.configure(0, 1, 10, 10)  # configure Ethernet port 0 -> ATM port 1 with VC 10:10
    assert atm_bridge.mapping[0] == (1, 10, 10)
    atm_bridge.unconfigure()
    atm_bridge.remove_nio(0)
    atm_bridge.remove_nio(1)
    nio1.delete()
    nio2.delete()
