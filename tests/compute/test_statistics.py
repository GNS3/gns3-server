from types import SimpleNamespace
from unittest.mock import patch

from gns3server.api.routes.compute.compute import compute_statistics


def test_compute_statistics_preserves_load_average_precision() -> None:
    memory = SimpleNamespace(total=8192, available=4096, percent=50)
    swap = SimpleNamespace(total=1024, free=512, used=512, percent=50)
    disk = SimpleNamespace(total=16384, used=4096, free=12288, percent=25)

    with patch("gns3server.api.routes.compute.compute.CpuPercent.get", return_value=10), \
            patch("gns3server.api.routes.compute.compute.get_cpu_model", return_value="Test CPU"), \
            patch("gns3server.api.routes.compute.compute.psutil.virtual_memory", return_value=memory), \
            patch("gns3server.api.routes.compute.compute.psutil.swap_memory", return_value=swap), \
            patch("gns3server.api.routes.compute.compute.psutil.disk_usage", return_value=disk), \
            patch("gns3server.api.routes.compute.compute.psutil.cpu_count", return_value=4), \
            patch("gns3server.api.routes.compute.compute.psutil.getloadavg", return_value=(1.25, 2.5, 3.75)):
        statistics = compute_statistics()

    assert statistics["load_average"] == [1.25, 2.5, 3.75]
    assert statistics["load_average_percent"] == [31.25, 62.5, 93.75]
    assert statistics["cpu_count"] == 4
    assert statistics["cpu_count_physical"] == 4
    assert statistics["cpu_model"] == "Test CPU"
    assert statistics["disk_total"] == 16384
    assert statistics["disk_used"] == 4096
    assert statistics["disk_free"] == 12288
