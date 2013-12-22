from gns3server.modules.dynamips import NIO_UDP
from gns3server.modules.dynamips import NIO_UDP_auto
from gns3server.modules.dynamips import NIO_FIFO
from gns3server.modules.dynamips import NIO_Mcast
from gns3server.modules.dynamips import NIO_Null
from gns3server.modules.dynamips import DynamipsError
import pytest

# TODO: test UNIX, TAP, VDE, generic Ethernet and Linux Ethernet NIOs


def test_nio_udp(hypervisor):

    nio1 = NIO_UDP(hypervisor, 10001, "127.0.0.1", 10002)
    assert nio1.lport == 10001
    nio2 = NIO_UDP(hypervisor, 10002, "127.0.0.1", 10001)
    assert nio2.lport == 10002
    nio1.delete()
    nio2.delete()


def test_nio_udp_auto(hypervisor):

    nio1 = NIO_UDP_auto(hypervisor, "127.0.0.1", 10001, 10010)
    assert nio1.lport == 10001
    nio2 = NIO_UDP_auto(hypervisor, "127.0.0.1", 10001, 10010)
    assert nio2.lport == 10002
    nio1.connect("127.0.0.1", nio2.lport)
    nio2.connect("127.0.0.1", nio1.lport)
    nio1.delete()
    nio2.delete()


def test_nio_fifo(hypervisor):

    nio1 = NIO_FIFO(hypervisor)
    nio2 = NIO_FIFO(hypervisor)
    nio1.crossconnect(nio2)
    assert nio1.list()
    nio1.delete()
    nio2.delete()


def test_nio_mcast(hypervisor):

    nio1 = NIO_Mcast(hypervisor, "232.0.0.1", 10001)
    assert nio1.group == "232.0.0.1"
    assert nio1.port == 10001
    nio1.ttl = 254
    assert nio1.ttl == 254
    nio2 = NIO_UDP(hypervisor, 10002, "232.0.0.1", 10001)
    nio1.delete()
    nio2.delete()


def test_nio_null(hypervisor):

    nio = NIO_Null(hypervisor)
    assert nio.list()
    nio.delete()


def test_rename_nio(hypervisor):

    nio = NIO_Null(hypervisor)
    assert nio.name.startswith("nio_null")
    nio.rename("test")
    assert nio.name == "test"
    nio.delete()


def test_debug_nio(hypervisor):

    nio = NIO_Null(hypervisor)
    nio.debug(1)
    nio.debug(0)
    nio.delete()


def test_bind_unbind_filter(hypervisor):

    nio = NIO_Null(hypervisor)
    nio.bind_filter("both", "freq_drop")
    assert nio.input_filter == ("freq_drop", None)
    assert nio.output_filter == ("freq_drop", None)
    nio.unbind_filter("both")
    nio.bind_filter("in", "capture")
    assert nio.input_filter == ("capture", None)
    nio.unbind_filter("in")
    nio.delete()


def test_bind_unknown_filter(hypervisor):

    nio = NIO_Null(hypervisor)
    with pytest.raises(DynamipsError):
        nio.bind_filter("both", "my_filter")
        nio.delete()


def test_unbind_with_no_filter_applied(hypervisor):

    nio = NIO_Null(hypervisor)
    with pytest.raises(DynamipsError):
        nio.unbind_filter("out")
        nio.delete()


def test_setup_filter(hypervisor):

    nio = NIO_Null(hypervisor)
    nio.bind_filter("in", "freq_drop")
    nio.setup_filter("in", "5")  # drop every 5th packet
    assert nio.input_filter == ("freq_drop", "5")
    nio.unbind_filter("in")
    nio.delete()


def test_get_stats(hypervisor):

    nio = NIO_Null(hypervisor)
    assert nio.get_stats() == "0 0 0 0"  # nothing has been transmitted or received
    nio.delete()


def test_reset_stats(hypervisor):

    nio = NIO_Null(hypervisor)
    nio.reset_stats()
    nio.delete()


def test_set_bandwidth(hypervisor):

    nio = NIO_Null(hypervisor)
    assert nio.bandwidth == None  # no constraint by default
    nio.set_bandwidth(1000)  # bandwidth = 1000 Kb/s
    assert nio.bandwidth == 1000
    nio.delete()
