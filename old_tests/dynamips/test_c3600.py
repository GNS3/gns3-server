from gns3server.modules.dynamips import C3600
from gns3server.modules.dynamips import DynamipsError
from gns3server.modules.dynamips import NM_1E
from gns3server.modules.dynamips import NM_4E
from gns3server.modules.dynamips import NM_1FE_TX
from gns3server.modules.dynamips import NM_16ESW
from gns3server.modules.dynamips import NM_4T
import pytest


@pytest.fixture
def router_c3600(request, hypervisor):

    router = C3600(hypervisor, "c3600 router")
    request.addfinalizer(router.delete)
    return router


def test_router_exist(router_c3600):

    assert router_c3600.platform == "c3600"
    assert router_c3600.list()


def test_chassis_3620(hypervisor):

    router = C3600(hypervisor, "3620 chassis", chassis="3620")
    assert router.chassis == "3620"
    router.delete()


def test_chassis_change_to_3620(router_c3600):

    assert router_c3600.chassis == "3640"  # default chassis
    router_c3600.chassis = "3620"
    assert router_c3600.chassis == "3620"


def test_chassis_3660(hypervisor):

    router = C3600(hypervisor, "3660 chassis", chassis="3660")
    assert router.chassis == "3660"
    assert str(router.slots[0]) == "Leopard-2FE"
    router.delete()


def test_chassis_change_to_3660(router_c3600):

    assert router_c3600.chassis == "3640"  # default chassis
    router_c3600.chassis = "3660"
    assert router_c3600.chassis == "3660"


def test_iomem(router_c3600):

    assert router_c3600.iomem == 5  # default value
    router_c3600.iomem = 10
    assert router_c3600.iomem == 10


def test_mac_addr(router_c3600):

    assert router_c3600.mac_addr is not None
    router_c3600.mac_addr = "aa:aa:aa:aa:aa:aa"
    assert router_c3600.mac_addr == "aa:aa:aa:aa:aa:aa"


def test_bogus_mac_addr(router_c3600):

    with pytest.raises(DynamipsError):
        router_c3600.mac_addr = "zz:zz:zz:zz:zz:zz"


def test_system_id(router_c3600):

    assert router_c3600.system_id == "FTX0945W0MY"  # default value
    router_c3600.system_id = "FTX0945W0MO"
    assert router_c3600.system_id == "FTX0945W0MO"


def test_get_hardware_info(router_c3600):

    router_c3600.get_hardware_info()  # FIXME: Dynamips doesn't return anything


def test_slot_add_NM_1E(router_c3600):

    adapter = NM_1E()
    router_c3600.slot_add_binding(1, adapter)
    assert router_c3600.slots[1] == adapter


def test_slot_add_NM_4E(router_c3600):

    adapter = NM_4E()
    router_c3600.slot_add_binding(1, adapter)
    assert router_c3600.slots[1] == adapter


def test_slot_add_NM_1FE_TX(router_c3600):

    adapter = NM_1FE_TX()
    router_c3600.slot_add_binding(1, adapter)
    assert router_c3600.slots[1] == adapter


def test_slot_add_NM_16ESW(router_c3600):

    adapter = NM_16ESW()
    router_c3600.slot_add_binding(1, adapter)
    assert router_c3600.slots[1] == adapter


def test_slot_add_NM_4T(router_c3600):

    adapter = NM_4T()
    router_c3600.slot_add_binding(1, adapter)
    assert router_c3600.slots[1] == adapter
