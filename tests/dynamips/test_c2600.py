from gns3server.modules.dynamips import C2600
from gns3server.modules.dynamips import DynamipsError
from gns3server.modules.dynamips import NM_1E
from gns3server.modules.dynamips import NM_4E
from gns3server.modules.dynamips import NM_1FE_TX
from gns3server.modules.dynamips import NM_16ESW
import pytest


@pytest.fixture
def router_c2600(request, hypervisor):

    router = C2600(hypervisor, "c2600 router")
    request.addfinalizer(router.delete)
    return router


def test_router_exists(router_c2600):

    assert router_c2600.platform == "c2600"
    assert router_c2600.list()


def test_chassis_2611(hypervisor):

    router = C2600(hypervisor, "2611 chassis", chassis="2611")
    assert router.chassis == "2611"
    assert isinstance(router.slots[0], router.integrated_adapters["2611"])
    router.delete()


def test_chassis_change_to_2611(router_c2600):

    assert router_c2600.chassis == "2610"  # default chassis
    router_c2600.chassis = "2611"
    assert router_c2600.chassis == "2611"


def test_chassis_2620(hypervisor):

    router = C2600(hypervisor, "2620 chassis", chassis="2620")
    assert router.chassis == "2620"
    assert isinstance(router.slots[0], router.integrated_adapters["2620"])
    router.delete()


def test_chassis_change_to_2620(router_c2600):

    assert router_c2600.chassis == "2610"  # default chassis
    router_c2600.chassis = "2620"
    assert router_c2600.chassis == "2620"


def test_chassis_2621(hypervisor):

    router = C2600(hypervisor, "2621 chassis", chassis="2621")
    assert router.chassis == "2621"
    assert isinstance(router.slots[0], router.integrated_adapters["2621"])
    router.delete()


def test_chassis_change_to_2621(router_c2600):

    assert router_c2600.chassis == "2610"  # default chassis
    router_c2600.chassis = "2621"
    assert router_c2600.chassis == "2621"


def test_chassis_2610XM(hypervisor):

    router = C2600(hypervisor, "2610XM chassis", chassis="2610XM")
    assert router.chassis == "2610XM"
    assert isinstance(router.slots[0], router.integrated_adapters["2610XM"])
    router.delete()


def test_chassis_change_to_2610XM(router_c2600):

    assert router_c2600.chassis == "2610"  # default chassis
    router_c2600.chassis = "2610XM"
    assert router_c2600.chassis == "2610XM"


def test_chassis_2611XM(hypervisor):

    router = C2600(hypervisor, "2611XM chassis", chassis="2611XM")
    assert router.chassis == "2611XM"
    assert isinstance(router.slots[0], router.integrated_adapters["2611XM"])
    router.delete()


def test_chassis_change_to_2611XM(router_c2600):

    assert router_c2600.chassis == "2610"  # default chassis
    router_c2600.chassis = "2611XM"
    assert router_c2600.chassis == "2611XM"


def test_chassis_2620XM(hypervisor):

    router = C2600(hypervisor, "2620XM chassis", chassis="2620XM")
    assert router.chassis == "2620XM"
    assert isinstance(router.slots[0], router.integrated_adapters["2620XM"])
    router.delete()


def test_chassis_change_to_2620XM(router_c2600):

    assert router_c2600.chassis == "2610"  # default chassis
    router_c2600.chassis = "2620XM"
    assert router_c2600.chassis == "2620XM"


def test_chassis_2621XM(hypervisor):

    router = C2600(hypervisor, "2621XM chassis", chassis="2621XM")
    assert router.chassis == "2621XM"
    assert isinstance(router.slots[0], router.integrated_adapters["2621XM"])
    router.delete()


def test_chassis_change_to_2621XM(router_c2600):

    assert router_c2600.chassis == "2610"  # default chassis
    router_c2600.chassis = "2621XM"
    assert router_c2600.chassis == "2621XM"


def test_chassis_2650XM(hypervisor):

    router = C2600(hypervisor, "2650XM chassis", chassis="2650XM")
    assert router.chassis == "2650XM"
    assert isinstance(router.slots[0], router.integrated_adapters["2650XM"])
    router.delete()


def test_chassis_change_to_2650XM(router_c2600):

    assert router_c2600.chassis == "2610"  # default chassis
    router_c2600.chassis = "2650XM"
    assert router_c2600.chassis == "2650XM"


def test_chassis_2651XM(hypervisor):

    router = C2600(hypervisor, "2651XM chassis", chassis="2651XM")
    assert router.chassis == "2651XM"
    assert isinstance(router.slots[0], router.integrated_adapters["2651XM"])
    router.delete()


def test_chassis_change_to_2651XM(router_c2600):

    assert router_c2600.chassis == "2610"  # default chassis
    router_c2600.chassis = "2651XM"
    assert router_c2600.chassis == "2651XM"


def test_iomem(router_c2600):

    assert router_c2600.iomem == 15  # default value
    router_c2600.iomem = 20
    assert router_c2600.iomem == 20


def test_mac_addr(router_c2600):

    assert router_c2600.mac_addr == None  # default value
    router_c2600.mac_addr = "aa:aa:aa:aa:aa:aa"
    assert router_c2600.mac_addr == "aa:aa:aa:aa:aa:aa"


def test_bogus_mac_addr(router_c2600):

    with pytest.raises(DynamipsError):
        router_c2600.mac_addr = "zz:zz:zz:zz:zz:zz"


def test_system_id(router_c2600):

    assert router_c2600.system_id == None  # default value
    router_c2600.system_id = "FTX0945W0MO"
    assert router_c2600.system_id == "FTX0945W0MO"


def test_get_hardware_info(router_c2600):

    router_c2600.get_hardware_info()  # FIXME: Dynamips doesn't return anything


def test_slot_add_NM_1E(router_c2600):

    adapter = NM_1E()
    router_c2600.slot_add_binding(1, adapter)
    assert router_c2600.slots[1] == adapter


def test_slot_add_NM_4E(router_c2600):

    adapter = NM_4E()
    router_c2600.slot_add_binding(1, adapter)
    assert router_c2600.slots[1] == adapter


def test_slot_add_NM_1FE_TX(router_c2600):

    adapter = NM_1FE_TX()
    router_c2600.slot_add_binding(1, adapter)
    assert router_c2600.slots[1] == adapter


def test_slot_add_NM_16ESW(router_c2600):

    adapter = NM_16ESW()
    router_c2600.slot_add_binding(1, adapter)
    assert router_c2600.slots[1] == adapter
