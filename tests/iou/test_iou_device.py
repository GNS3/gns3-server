from gns3server.modules.iou import IOUDevice
import os
import pytest


def no_iou():
    cwd = os.path.dirname(os.path.abspath(__file__))
    iou_path = os.path.join(cwd, "i86bi_linux-ipbase-ms-12.4.bin")

    if os.path.isfile(iou_path):
        return False
    else:
        return True


@pytest.fixture(scope="session")
def iou(request):

    cwd = os.path.dirname(os.path.abspath(__file__))
    iou_path = os.path.join(cwd, "i86bi_linux-ipbase-ms-12.4.bin")
    iou_device = IOUDevice("IOU1", iou_path, "/tmp")
    iou_device.start()
    request.addfinalizer(iou_device.delete)
    return iou_device


@pytest.mark.skipif(no_iou(), reason="IOU Image not available")
def test_iou_is_started(iou):

    print(iou.command())
    assert iou.id == 1  # we should have only one IOU running!
    assert iou.is_running()


@pytest.mark.skipif(no_iou(), reason="IOU Image not available")
def test_iou_restart(iou):

    iou.stop()
    assert not iou.is_running()
    iou.start()
    assert iou.is_running()
