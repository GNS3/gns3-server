from gns3server.modules.vpcs import VPCSDevice
import os
import pytest


@pytest.fixture(scope="session")
def vpcs(request):

    cwd = os.path.dirname(os.path.abspath(__file__))
    vpcs_path = os.path.join(cwd, "vpcs")
    vpcs_device = VPCSDevice(vpcs_path, "/tmp")
    vpcs_device.start()
    request.addfinalizer(vpcs_device.delete)
    return vpcs_device


def test_vpcs_is_started(vpcs):

    print(vpcs.command())
    assert vpcs.id == 1  # we should have only one VPCS running!
    assert vpcs.is_running()


def test_vpcs_restart(vpcs):

    vpcs.stop()
    assert not vpcs.is_running()
    vpcs.start()
    assert vpcs.is_running()
