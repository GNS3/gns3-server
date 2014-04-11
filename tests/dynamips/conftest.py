from gns3server.modules.dynamips import HypervisorManager
import pytest
import os


@pytest.fixture(scope="module")
def hypervisor(request):

    cwd = os.path.dirname(os.path.abspath(__file__))
    dynamips_path = os.path.join(cwd, "dynamips.stable")
    print("\nStarting Dynamips Hypervisor: {}".format(dynamips_path))
    manager = HypervisorManager(dynamips_path, "/tmp", "127.0.0.1", 9000)
    hypervisor = manager.start_new_hypervisor()

    def stop():
        print("\nStopping Dynamips Hypervisor")
        manager.stop_all_hypervisors()

    request.addfinalizer(stop)
    return hypervisor


@pytest.fixture(scope="session")
def image(request):

    cwd = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(cwd, "c3725.image")
    if not os.path.isfile(image_path):
        return None
    return image_path
