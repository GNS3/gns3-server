from gns3server.modules.dynamips import C1700
from gns3server.modules.dynamips import DynamipsError
from gns3server.modules.dynamips import WIC_2T
from gns3server.modules.dynamips import WIC_1ENET
from gns3server.modules.dynamips import NIO_Null
import pytest


@pytest.fixture
def router_c1700(request, hypervisor):

    router = C1700(hypervisor, "c1700 router")
    request.addfinalizer(router.delete)
    return router


def test_router_exists(router_c1700):

    assert router_c1700.platform == "c1700"
    assert router_c1700.list()


def test_chassis_1721(hypervisor):

    router = C1700(hypervisor, "1721 chassis", chassis="1721")
    assert router.chassis == "1721"
    assert str(router.slots[0]) == "C1700-MB-1FE"
    router.delete()


def test_chassis_change_to_1721(router_c1700):

    assert router_c1700.chassis == "1720"  # default chassis
    router_c1700.chassis = "1721"
    assert router_c1700.chassis == "1721"


def test_chassis_1750(hypervisor):

    router = C1700(hypervisor, "1750 chassis", chassis="1750")
    assert router.chassis == "1750"
    assert str(router.slots[0]) == "C1700-MB-1FE"
    router.delete()


def test_chassis_change_to_1750(router_c1700):

    assert router_c1700.chassis == "1720"  # default chassis
    router_c1700.chassis = "1750"
    assert router_c1700.chassis == "1750"


def test_chassis_1751(hypervisor):

    router = C1700(hypervisor, "1751 chassis", chassis="1751")
    assert router.chassis == "1751"
    assert str(router.slots[0]) == "C1700-MB-1FE"
    router.delete()


def test_chassis_change_to_1751(router_c1700):

    assert router_c1700.chassis == "1720"  # default chassis
    router_c1700.chassis = "1751"
    assert router_c1700.chassis == "1751"


def test_chassis_1760(hypervisor):

    router = C1700(hypervisor, "1760 chassis", chassis="1760")
    assert router.chassis == "1760"
    assert str(router.slots[0]) == "C1700-MB-1FE"
    router.delete()


def test_chassis_change_to_1760(router_c1700):

    assert router_c1700.chassis == "1720"  # default chassis
    router_c1700.chassis = "1760"
    assert router_c1700.chassis == "1760"


def test_iomem(router_c1700):

    assert router_c1700.iomem == 15  # default value
    router_c1700.iomem = 20
    assert router_c1700.iomem == 20


def test_mac_addr(router_c1700):

    assert router_c1700.mac_addr is not None
    router_c1700.mac_addr = "aa:aa:aa:aa:aa:aa"
    assert router_c1700.mac_addr == "aa:aa:aa:aa:aa:aa"


def test_bogus_mac_addr(router_c1700):

    with pytest.raises(DynamipsError):
        router_c1700.mac_addr = "zz:zz:zz:zz:zz:zz"


def test_system_id(router_c1700):

    assert router_c1700.system_id == "FTX0945W0MY"  # default value
    router_c1700.system_id = "FTX0945W0MO"
    assert router_c1700.system_id == "FTX0945W0MO"


def test_get_hardware_info(router_c1700):

    router_c1700.get_hardware_info()  # FIXME: Dynamips doesn't return anything


def test_install_remove_wic(router_c1700):

    wic = WIC_2T()
    router_c1700.install_wic(0, wic)  # install in WIC slot 0
    assert router_c1700.slots[0].wics[0]
    wic = WIC_1ENET()
    router_c1700.install_wic(1, wic)  # install in WIC slot 1
    assert router_c1700.slots[0].wics[1]
    router_c1700.uninstall_wic(0)  # uninstall WIC from slot 0
    assert not router_c1700.slots[0].wics[0]


def test_install_wic_into_wrong_slot(router_c1700):

    wic = WIC_2T()
    with pytest.raises(DynamipsError):
        router_c1700.install_wic(2, wic)  # install in WIC slot 2


def test_install_wic_into_already_occupied_slot(router_c1700):

    wic = WIC_2T()
    router_c1700.install_wic(0, wic)  # install in WIC slot 0
    wic = WIC_1ENET()
    with pytest.raises(DynamipsError):
        router_c1700.install_wic(0, wic)  # install in WIC slot 0


def test_wic_add_remove_nio_binding(router_c1700):

    nio = NIO_Null(router_c1700.hypervisor)
    wic = WIC_2T()
    router_c1700.install_wic(0, wic)  # install WIC in slot 0
    router_c1700.slot_add_nio_binding(0, 17, nio)  # slot 0/17 (slot 0, wic 0, port 1)
    assert router_c1700.slots[0].ports[17] == nio
    assert router_c1700.get_slot_nio_bindings(slot_id=0)
    router_c1700.slot_remove_nio_binding(0, 17)  # slot 0/17 (slot 0, wic 0, port 1)
    assert not router_c1700.get_slot_nio_bindings(slot_id=0)
    assert not router_c1700.slots[0].ports[17] == nio
    nio.delete()


def test_wic_add_remove_nio_binding_for_chassis_1760(hypervisor):

    router = C1700(hypervisor, "1760 chassis", chassis="1760")
    nio = NIO_Null(router.hypervisor)
    wic = WIC_2T()
    router.install_wic(1, wic)  # install WIC in slot 1
    router.slot_add_nio_binding(0, 32, nio)  # slot 0/17 (slot 0, wic 1, port 0)
    router.slot_remove_nio_binding(0, 32)
    assert not router.get_slot_nio_bindings(slot_id=0)
    nio.delete()
    router.delete()
