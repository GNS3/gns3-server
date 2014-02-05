from gns3server.modules.dynamips import EthernetSwitch
from gns3server.modules.dynamips import NIO_Null
from gns3server.modules.dynamips import DynamipsError
import pytest


@pytest.fixture
def ethsw(request, hypervisor):

    ethsw = EthernetSwitch(hypervisor, "Ethernet switch")
    request.addfinalizer(ethsw.delete)
    return ethsw


def test_ethsw_exists(ethsw):

    assert ethsw.list()


def test_rename_ethsw(ethsw):

    ethsw.name = "new Ethernet switch"
    assert ethsw.name == "new Ethernet switch"


def test_add_remove_nio(ethsw):

    nio = NIO_Null(ethsw.hypervisor)
    ethsw.add_nio(nio, 0)  # add NIO on port 0
    assert ethsw.nios
    ethsw.remove_nio(0)  # remove NIO from port 0
    nio.delete()


def test_add_nio_already_allocated_port(ethsw):

    nio = NIO_Null(ethsw.hypervisor)
    ethsw.add_nio(nio, 0)  # add NIO on port 0
    with pytest.raises(DynamipsError):
        ethsw.add_nio(nio, 0)
        nio.delete()


def test_remove_nio_non_allocated_port(ethsw):

    with pytest.raises(DynamipsError):
        ethsw.remove_nio(0)  # remove NIO from port 0


def test_set_access_port(ethsw):

    nio = NIO_Null(ethsw.hypervisor)
    ethsw.add_nio(nio, 0)  # add NIO on port 0
    ethsw.set_access_port(0, 10)  # set port 0 as access in VLAN 10
    assert ethsw.mapping[0] == ("access", 10)
    ethsw.remove_nio(0)  # remove NIO from port 0
    nio.delete()


def test_set_dot1q_port(ethsw):

    nio = NIO_Null(ethsw.hypervisor)
    ethsw.add_nio(nio, 0)  # add NIO on port 0
    ethsw.set_dot1q_port(0, 1)  # set port 0 as 802.1Q trunk with native VLAN 1
    assert ethsw.mapping[0] == ("dot1q", 1)
    ethsw.remove_nio(0)  # remove NIO from port 0
    nio.delete()


def test_set_qinq_port(ethsw):

    nio = NIO_Null(ethsw.hypervisor)
    ethsw.add_nio(nio, 0)  # add NIO on port 0
    ethsw.set_qinq_port(0, 100)  # set port 0 as QinQ trunk with outer VLAN 100
    assert ethsw.mapping[0] == ("qinq", 100)
    ethsw.remove_nio(0)  # remove NIO from port 0
    nio.delete()


def test_get_mac_addr_table(ethsw):

    assert not ethsw.get_mac_addr_table()  # MAC address table should be empty


def test_clear_mac_addr_table(ethsw):

    ethsw.clear_mac_addr_table()
