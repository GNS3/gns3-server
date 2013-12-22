from gns3server.modules.dynamips import Hypervisor
import time
import os


def test_is_started(hypervisor):

    assert hypervisor.is_running()


def test_port(hypervisor):

    assert hypervisor.port == 9000


def test_host(hypervisor):

    assert hypervisor.host == "127.0.0.1"


def test_workingdir(hypervisor):

    assert hypervisor.workingdir == "/tmp"


def test_path(hypervisor):

    cwd = os.path.dirname(os.path.abspath(__file__))
    dynamips_path = os.path.join(cwd, "dynamips.stable")
    assert hypervisor.path == dynamips_path


def test_stdout():

    # try to launch Dynamips on the same port
    # this will fail so that we can read its stdout/stderr
    cwd = os.path.dirname(os.path.abspath(__file__))
    dynamips_path = os.path.join(cwd, "dynamips.stable")
    hypervisor = Hypervisor(dynamips_path, "/tmp", "172.0.0.1", 7200)
    hypervisor.start()
    # give some time for Dynamips to start
    time.sleep(0.01)
    output = hypervisor.read_stdout()
    assert output
