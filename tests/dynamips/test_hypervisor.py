from gns3server.modules.dynamips import Hypervisor
import time


def test_is_started(hypervisor):

    assert hypervisor.is_running()


def test_port(hypervisor):

    assert hypervisor.port == 7200


def test_host(hypervisor):

    assert hypervisor.host == "0.0.0.0"


def test_working_dir(hypervisor):

    assert hypervisor.working_dir == "/tmp"


def test_path(hypervisor):

    dynamips_path = '/usr/bin/dynamips'
    assert hypervisor.path == dynamips_path


def test_stdout():

    # try to launch Dynamips on the same port
    # this will fail so that we can read its stdout/stderr
    dynamips_path = '/usr/bin/dynamips'
    hypervisor = Hypervisor(dynamips_path, "/tmp", "127.0.0.1", 7200)
    hypervisor.start()
    # give some time for Dynamips to start
    time.sleep(0.1)
    output = hypervisor.read_stdout()
    assert output
