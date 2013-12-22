from gns3server.modules.dynamips import Router
from gns3server.modules.dynamips import DynamipsError
import pytest
import tempfile
import base64


@pytest.fixture
def router(request, hypervisor):

    router = Router(hypervisor, "router", "c3725")
    request.addfinalizer(router.delete)
    return router


def test_hypervisor_is_started(hypervisor):

    assert hypervisor.is_running()


def test_create_and_delete_router(hypervisor):

    router = Router(hypervisor, "test my router")
    assert router.id >= 0
    assert router.name == "test my router"
    assert router.platform == "c7200"  # default platform
    assert not router.is_running()
    router.delete()
    with pytest.raises(DynamipsError):
        router.get_status()


# def test_rename_router(router):
#
#     assert router.name == "router"
#     router.rename("my_router")
#     assert router.name == "my_router"
#     router.rename("router")
#     assert router.name == "router"
    #router.delete()  # FIXME: fails with current Dynamips version


def test_image(router):

    # let's pretend this file is an IOS image
    with tempfile.NamedTemporaryFile() as ios_image:
        router.image = ios_image.name
        assert router.image == ios_image.name


def test_set_config(router):

    with tempfile.NamedTemporaryFile() as startup_config:
        startup_config.write(b"hostname test_config\n")
        router.set_config(startup_config.name)


def test_push_config(router):

    startup_config = base64.b64encode(b"hostname test_config\n").decode("utf-8")
    private_config = base64.b64encode(b"private config\n").decode("utf-8")
    router.push_config(startup_config, private_config)
    router_startup_config, router_private_config = router.extract_config()
    assert startup_config == router_startup_config
    assert private_config == router_private_config


def test_status(router, image):
    # don't test if we have no IOS image
    if not image:
        return

    assert router.get_status() == "inactive"
    router.ram = 256
    router.image = image
    router.start()
    assert router.is_running()
    router.suspend()
    assert router.get_status() == "suspended"
    router.resume()
    assert router.is_running()
    router.stop()
    assert router.get_status() == "inactive"


def test_ram(router):

    assert router.ram == 128  # default ram
    router.ram = 256
    assert router.ram == 256


def test_nvram(router):

    assert router.nvram == 128  # default nvram
    router.nvram = 256
    assert router.nvram == 256


def test_mmap(router):

    assert router.mmap == True  # default value
    router.mmap = False
    assert router.mmap == False


def test_sparsemem(router):

    assert router.sparsemem == True  # default value
    router.sparsemem = False
    assert router.sparsemem == False


def test_clock_divisor(router):

    assert router.clock_divisor == 8  # default value
    router.clock_divisor = 4
    assert router.clock_divisor == 4


def test_idlepc(router):

    assert router.idlepc == ""  # no default value
    router.idlepc = "0x60c086a8"
    assert router.idlepc == "0x60c086a8"


def test_idlemax(router):

    assert router.idlemax == 1500  # default value
    router.idlemax = 500
    assert router.idlemax == 500


def test_idlesleep(router):

    assert router.idlesleep == 30  # default value
    router.idlesleep = 15
    assert router.idlesleep == 15


def test_exec_area(router):

    assert router.exec_area == None  # default value
    router.exec_area = 64
    assert router.exec_area == 64


def test_disk0(router):

    assert router.disk0 == 0  # default value
    router.disk0 = 16
    assert router.disk0 == 16


def test_disk1(router):

    assert router.disk1 == 0  # default value
    router.disk1 = 16
    assert router.disk1 == 16


def test_confreg(router):

    assert router.confreg == "0x2102"  # default value
    router.confreg = "0x2142"
    assert router.confreg == "0x2142"


def test_console(router):

    assert router.console == router.hypervisor.baseconsole + router.id
    new_console_port = router.console + 100
    router.console = new_console_port
    assert router.console == new_console_port


def test_aux(router):

    assert router.aux == router.hypervisor.baseaux + router.id
    new_aux_port = router.aux + 100
    router.aux = new_aux_port
    assert router.aux == new_aux_port


def test_cpu_info(router):

    router.get_cpu_info()  # nothing is returned by the hypervisor, cannot test?


def test_cpu_usage(router):

    usage = router.get_cpu_usage()
    assert usage == 0  # router isn't running, so usage must be 0


def test_get_slot_bindings(router):

    assert router.get_slot_bindings()[0] == "0/0: GT96100-FE"


def test_get_slot_nio_bindings(router):

    router.get_slot_nio_bindings(slot_id=0)


def test_mac_addr(router):

    assert router.mac_addr == None  # default value
    router.mac_addr = "aa:aa:aa:aa:aa:aa"
    assert router.mac_addr == "aa:aa:aa:aa:aa:aa"


def test_bogus_mac_addr(router):

    with pytest.raises(DynamipsError):
        router.mac_addr = "zz:zz:zz:zz:zz:zz"


def test_system_id(router):

    assert router.system_id == None  # default value
    router.system_id = "FTX0945W0MO"
    assert router.system_id == "FTX0945W0MO"


def test_get_hardware_info(router):

    router.get_hardware_info()
