from unittest.mock import MagicMock, patch

from gns3server.api.routes.controller.controller import get_server_uptime_seconds


def test_server_uptime_uses_process_creation_time() -> None:
    process = MagicMock()
    process.create_time.return_value = 50.25

    with patch("gns3server.api.routes.controller.controller.time.time", return_value=200.75), \
            patch("gns3server.api.routes.controller.controller.psutil.Process", return_value=process):
        uptime = get_server_uptime_seconds()

    assert uptime == 150
