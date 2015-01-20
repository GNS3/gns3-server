from gns3server.modules.dynamips import C7200
from gns3server.modules.dynamips import DynamipsError
from gns3server.modules.dynamips import PA_2FE_TX
from gns3server.modules.dynamips import PA_4E
from gns3server.modules.dynamips import PA_4T
from gns3server.modules.dynamips import PA_8E
from gns3server.modules.dynamips import PA_8T
from gns3server.modules.dynamips import PA_A1
from gns3server.modules.dynamips import PA_FE_TX
from gns3server.modules.dynamips import PA_GE
from gns3server.modules.dynamips import PA_POS_OC3
from gns3server.modules.dynamips import NIO_Null
import pytest


@pytest.fixture
def router_c7200(request, hypervisor):

    router = C7200(hypervisor, "c7200 router")
    request.addfinalizer(router.delete)
    return router


def test_router_exists(router_c7200):

    assert router_c7200.platform == "c7200"
    assert router_c7200.list()


def test_npe(router_c7200):

    assert router_c7200.npe == "npe-400"  # default value
    router_c7200.npe = "npe-200"
    assert router_c7200.npe == "npe-200"


def test_midplane(router_c7200):

    assert router_c7200.midplane == "vxr"  # default value
    router_c7200.midplane = "std"
    assert router_c7200.midplane == "std"


def test_sensors(router_c7200):

    assert router_c7200.sensors == [22, 22, 22, 22]  # default values (everything at 22C)
    router_c7200.sensors = [25, 25, 25, 25]
    assert router_c7200.sensors == [25, 25, 25, 25]


def test_power_supplies(router_c7200):

    assert router_c7200.power_supplies == [1, 1]  # default values (1 = powered on)
    router_c7200.power_supplies = [0, 0]
    assert router_c7200.power_supplies == [0, 0]


def test_mac_addr(router_c7200):

    assert router_c7200.mac_addr is not None
    router_c7200.mac_addr = "aa:aa:aa:aa:aa:aa"
    assert router_c7200.mac_addr == "aa:aa:aa:aa:aa:aa"


def test_bogus_mac_addr(router_c7200):

    with pytest.raises(DynamipsError):
        router_c7200.mac_addr = "zz:zz:zz:zz:zz:zz"


def test_system_id(router_c7200):

    assert router_c7200.system_id == "FTX0945W0MY"  # default value
    router_c7200.system_id = "FTX0945W0MO"
    assert router_c7200.system_id == "FTX0945W0MO"


def test_get_hardware_info(router_c7200):

    router_c7200.get_hardware_info()  # FIXME: Dynamips doesn't return anything


def test_slot_add_PA_2FE_TX(router_c7200):

    adapter = PA_2FE_TX()
    router_c7200.slot_add_binding(1, adapter)
    assert router_c7200.slots[1] == adapter


def test_slot_add_PA_4E(router_c7200):

    adapter = PA_4E()
    router_c7200.slot_add_binding(2, adapter)
    assert router_c7200.slots[2] == adapter


def test_slot_add_PA_4T(router_c7200):

    adapter = PA_4T()
    router_c7200.slot_add_binding(3, adapter)
    assert router_c7200.slots[3] == adapter


def test_slot_add_PA_8E(router_c7200):

    adapter = PA_8E()
    router_c7200.slot_add_binding(4, adapter)
    assert router_c7200.slots[4] == adapter


def test_slot_add_PA_8T(router_c7200):

    adapter = PA_8T()
    router_c7200.slot_add_binding(5, adapter)
    assert router_c7200.slots[5] == adapter


def test_slot_add_PA_A1(router_c7200):

    adapter = PA_A1()
    router_c7200.slot_add_binding(1, adapter)
    assert router_c7200.slots[1] == adapter


def test_slot_add_PA_FE_TX(router_c7200):

    adapter = PA_FE_TX()
    router_c7200.slot_add_binding(2, adapter)
    assert router_c7200.slots[2] == adapter


def test_slot_add_PA_GE(router_c7200):

    adapter = PA_GE()
    router_c7200.slot_add_binding(3, adapter)
    assert router_c7200.slots[3] == adapter


def test_slot_add_PA_POS_OC3(router_c7200):

    adapter = PA_POS_OC3()
    router_c7200.slot_add_binding(4, adapter)
    assert router_c7200.slots[4] == adapter


def test_slot_add_into_already_occupied_slot(router_c7200):

    adapter = PA_FE_TX()
    with pytest.raises(DynamipsError):
        router_c7200.slot_add_binding(0, adapter)


def test_slot_add_into_wrong_slot(router_c7200):

    adapter = PA_FE_TX()
    with pytest.raises(DynamipsError):
        router_c7200.slot_add_binding(10, adapter)


def test_slot_remove_adapter(router_c7200):

    adapter = PA_FE_TX()
    router_c7200.slot_add_binding(1, adapter)
    router_c7200.slot_remove_binding(1)
    assert router_c7200.slots[1] is None


def test_slot_add_remove_nio_binding(router_c7200):

    adapter = PA_FE_TX()
    router_c7200.slot_add_binding(1, adapter)
    nio = NIO_Null(router_c7200.hypervisor)
    router_c7200.slot_add_nio_binding(1, 0, nio)  # slot 1/0
    assert router_c7200.get_slot_nio_bindings(slot_id=1)
    assert router_c7200.slots[1].ports[0] == nio
    router_c7200.slot_remove_nio_binding(1, 0)  # slot 1/0
    assert not router_c7200.get_slot_nio_bindings(slot_id=0)
    nio.delete()


def test_slot_add_nio_to_wrong_port(router_c7200):

    adapter = PA_FE_TX()
    router_c7200.slot_add_binding(1, adapter)
    nio = NIO_Null(router_c7200.hypervisor)
    with pytest.raises(DynamipsError):
        router_c7200.slot_add_nio_binding(1, 1, nio)  # slot 1/1
    nio.delete()
