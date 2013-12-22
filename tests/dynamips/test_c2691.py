from gns3server.modules.dynamips import C2691
from gns3server.modules.dynamips import DynamipsError
from gns3server.modules.dynamips import NM_1FE_TX
from gns3server.modules.dynamips import NM_4T
from gns3server.modules.dynamips import NM_16ESW
import pytest


@pytest.fixture
def router_c2691(request, hypervisor):

    router = C2691(hypervisor, "c2691 router")
    request.addfinalizer(router.delete)
    return router


def test_router_exists(router_c2691):

    assert router_c2691.platform == "c2691"
    assert router_c2691.list()


def test_iomem(router_c2691):

    assert router_c2691.iomem == 5  # default value
    router_c2691.iomem = 10
    assert router_c2691.iomem == 10


def test_mac_addr(router_c2691):

    assert router_c2691.mac_addr == None  # default value
    router_c2691.mac_addr = "aa:aa:aa:aa:aa:aa"
    assert router_c2691.mac_addr == "aa:aa:aa:aa:aa:aa"


def test_bogus_mac_addr(router_c2691):

    with pytest.raises(DynamipsError):
        router_c2691.mac_addr = "zz:zz:zz:zz:zz:zz"


# FIXME: no implemented within Dynamips
# def test_system_id(hypervisor):
#     router = C2691(hypervisor, "test system id")
#     assert router.system_id == None  # default value
#     router.system_id = "FTX0945W0MO"
#     assert router.system_id == "FTX0945W0MO"
#     router.delete()


def test_get_hardware_info(router_c2691):

    router_c2691.get_hardware_info()  # FIXME: Dynamips doesn't return anything


def test_slot_add_NM_1FE_TX(router_c2691):

    adapter = NM_1FE_TX()
    router_c2691.slot_add_binding(1, adapter)
    assert router_c2691.slots[1] == adapter


def test_slot_add_NM_4T(router_c2691):

    adapter = NM_4T()
    router_c2691.slot_add_binding(1, adapter)
    assert router_c2691.slots[1] == adapter


def test_slot_add_NM_16ESW(router_c2691):

    adapter = NM_16ESW()
    router_c2691.slot_add_binding(1, adapter)
    assert router_c2691.slots[1] == adapter
