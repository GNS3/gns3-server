from gns3server.modules.dynamips import Router
from gns3server.modules.dynamips import HypervisorManager
import pytest
import os


@pytest.fixture(scope="module")
def hypervisor_manager(request):

    dynamips_path = '/usr/bin/dynamips'
    print("\nStarting Dynamips Hypervisor: {}".format(dynamips_path))
    manager = HypervisorManager(dynamips_path, "/tmp", "127.0.0.1")

    # manager.start_new_hypervisor()

    def stop():
        print("\nStopping Dynamips Hypervisor")
        manager.stop_all_hypervisors()

    request.addfinalizer(stop)
    return manager


def test_allocate_hypervisor_for_router(hypervisor_manager):

    hypervisor_manager.allocate_hypervisor_per_device = False
    # default of 1GB of RAM per hypervisor instance
    assert hypervisor_manager.memory_usage_limit_per_hypervisor == 1024
    hypervisor = hypervisor_manager.allocate_hypervisor_for_router("c3725.image", 512)
    assert hypervisor.is_running()
    hypervisor = hypervisor_manager.allocate_hypervisor_for_router("c3725.image", 256)
    assert hypervisor.memory_load == 768
    hypervisor = hypervisor_manager.allocate_hypervisor_for_router("c3725.image", 512)
    assert hypervisor.memory_load == 512
    assert len(hypervisor_manager.hypervisors) == 2


def test_unallocate_hypervisor_for_router(hypervisor_manager):

    assert len(hypervisor_manager.hypervisors) == 2
    hypervisor = hypervisor_manager.hypervisors[0]
    assert hypervisor.memory_load == 768
    router = Router(hypervisor, "router", "c3725")  # default is 128MB of RAM
    hypervisor_manager.unallocate_hypervisor_for_router(router)
    assert hypervisor.memory_load == 640
    hypervisor.decrease_memory_load(512)  # forces memory load down to 128
    assert hypervisor.memory_load == 128
    router.delete()
    hypervisor_manager.unallocate_hypervisor_for_router(router)
    # router is deleted and memory load to 0 now, one hypervisor must
    # have been shutdown
    assert len(hypervisor_manager.hypervisors) == 1
