from gns3server.modules.dynamips import C3745
from gns3server.modules.dynamips import DynamipsError
from gns3server.modules.dynamips import NM_1FE_TX
from gns3server.modules.dynamips import NM_4T
from gns3server.modules.dynamips import NM_16ESW
import pytest


@pytest.fixture
def router_c3745(request, hypervisor):

    router = C3745(hypervisor, "c3745 router")
    request.addfinalizer(router.delete)
    return router


def test_router_exists(router_c3745):

    assert router_c3745.platform == "c3745"
    assert router_c3745.list()


def test_iomem(router_c3745):

    assert router_c3745.iomem == 5  # default value
    router_c3745.iomem = 10
    assert router_c3745.iomem == 10


def test_mac_addr(router_c3745):

    assert router_c3745.mac_addr == None  # default value
    router_c3745.mac_addr = "aa:aa:aa:aa:aa:aa"
    assert router_c3745.mac_addr == "aa:aa:aa:aa:aa:aa"


def test_bogus_mac_addr(router_c3745):

    with pytest.raises(DynamipsError):
        router_c3745.mac_addr = "zz:zz:zz:zz:zz:zz"


def test_system_id(router_c3745):

    assert router_c3745.system_id == None  # default value
    router_c3745.system_id = "FTX0945W0MO"
    assert router_c3745.system_id == "FTX0945W0MO"


def test_get_hardware_info(router_c3745):

    router_c3745.get_hardware_info()  # FIXME: Dynamips doesn't return anything


def test_slot_add_NM_1FE_TX(router_c3745):

    adapter = NM_1FE_TX()
    router_c3745.slot_add_binding(1, adapter)
    assert router_c3745.slots[1] == adapter


def test_slot_add_NM_4T(router_c3745):

    adapter = NM_4T()
    router_c3745.slot_add_binding(1, adapter)
    assert router_c3745.slots[1] == adapter


def test_slot_add_NM_16ESW(router_c3745):

    adapter = NM_16ESW()
    router_c3745.slot_add_binding(1, adapter)
    assert router_c3745.slots[1] == adapter
