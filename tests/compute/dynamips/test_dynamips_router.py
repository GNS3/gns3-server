#
# Copyright (C) 2020 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from gns3server.compute.dynamips import Dynamips
from gns3server.compute.dynamips.dynamips_error import DynamipsError
from gns3server.compute.dynamips.nodes.router import Router
from gns3server.config import Config


@pytest_asyncio.fixture
async def manager(port_manager):

    m = Dynamips.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def router(compute_project, manager):

    return Router("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)


def test_router(compute_project, manager):

    router = Router("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    assert router.name == "test"
    assert router.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_convert_project_before_2_0_0_b3(compute_project, manager):

    node_id = str(uuid.uuid4())
    wdir = compute_project.module_working_directory(manager.module_name.lower())
    os.makedirs(os.path.join(wdir, node_id))
    os.makedirs(os.path.join(wdir, "configs"))
    open(os.path.join(wdir, "configs", "i1_startup-config.cfg"), "w+").close()
    open(os.path.join(wdir, "configs", "i2_startup-config.cfg"), "w+").close()
    open(os.path.join(wdir, "c7200_i1_nvram"), "w+").close()
    open(os.path.join(wdir, "c7200_i2_nvram"), "w+").close()
    router = Router("test", node_id, compute_project, manager, dynamips_id=1)
    assert os.path.exists(os.path.join(wdir, node_id, "configs", "i1_startup-config.cfg"))
    assert not os.path.exists(os.path.join(wdir, node_id, "configs", "i2_startup-config.cfg"))
    assert os.path.exists(os.path.join(wdir, node_id, "c7200_i1_nvram"))
    assert not os.path.exists(os.path.join(wdir, node_id, "c7200_i2_nvram"))


@pytest.mark.asyncio
async def test_router_invalid_dynamips_path(compute_project, config, manager):

    config = Config.instance()
    config.settings.Dynamips.dynamips_path = "/bin/test_fake"
    config.settings.Dynamips.allocate_aux_console_ports = False

    with pytest.raises(DynamipsError):
        router = Router("test", "00010203-0405-0607-0809-0a0b0c0d0e0e", compute_project, manager)
        await router.create()
        assert router.name == "test"
        assert router.id == "00010203-0405-0607-0809-0a0b0c0d0e0e"


@pytest.mark.asyncio
async def test_managed_router_redundant_stop_keeps_prepared_source(router):
    from pathlib import Path

    from gns3server.services.configurations.shared.safe_io import write_json
    from gns3server.services.configurations.shared.startup_journal import journal_path

    Path(router.startup_config_path).write_bytes(b"selected startup")
    write_json(journal_path(router), {"version": 1, "generation": 1, "state": "prepared"})
    router.get_status = AsyncMock(return_value="inactive")
    router.extract_config = AsyncMock()
    router.stop_wrap_console = AsyncMock()
    await router.stop()
    router.extract_config.assert_not_awaited()
    assert Path(router.startup_config_path).read_bytes() == b"selected startup"
    journal_path(router).unlink()


@pytest.mark.asyncio
async def test_router_stop_drains_queued_watcher_saves_before_final_extraction(router):
    from gns3server.services.configurations.shared.node_lease import node_lease
    from gns3server.services.configurations.shared.safe_io import write_json
    from gns3server.services.configurations.shared.startup_journal import journal_path

    write_json(journal_path(router), {"version": 1, "generation": 1, "state": "initialized"})
    router.get_status = AsyncMock(return_value="inactive")
    router.extract_config = AsyncMock(return_value=(None, None))
    router.stop_wrap_console = AsyncMock()
    router._memory_watcher = MagicMock()
    watcher = router._memory_watcher
    async with node_lease(router):
        router._memory_changed("ignored")
        pending = list(router._configuration_save_tasks)
        await router.stop()
    assert all(task.cancelled() for task in pending)
    assert not router._configuration_save_tasks
    watcher.close.assert_called_once_with()
    router.extract_config.assert_awaited_once()
    journal_path(router).unlink()


@pytest.mark.asyncio
@pytest.mark.parametrize("members", [(), ("startup",), ("startup", "private")])
async def test_managed_router_start_uses_owned_absolute_paths_without_changing_hypervisor_cwd(
    router, tmp_path, monkeypatch, members
):
    from pathlib import Path

    from gns3server.services.configurations.shared.safe_io import write_json
    from gns3server.services.configurations.shared.startup_journal import journal_path, runtime

    for role, path in (("startup", router.startup_config_path), ("private", router.private_config_path)):
        if role in members:
            Path(path).write_bytes(b"selected config")
        else:
            Path(path).unlink(missing_ok=True)
    image = tmp_path / "image.bin"
    image.write_bytes(b"\x7fELF\x01\x02\x01")
    router._image = str(image)
    router._hypervisor = MagicMock()
    router._hypervisor.send = AsyncMock()
    router.get_status = AsyncMock(return_value="inactive")
    router._prepare_tap_datapath = AsyncMock()
    router.check_available_ram = MagicMock()
    router.start_wrap_console = AsyncMock()
    monkeypatch.setattr("gns3server.compute.dynamips.nodes.router.monitor_process", MagicMock())
    write_json(journal_path(router), {"version": 1, "generation": 1, "state": "prepared"})
    await router.start()
    startup = router.startup_config_path if "startup" in members else ""
    private = router.private_config_path if "private" in members else ""
    router._hypervisor.send.assert_any_await(f'vm set_config "test" "{startup}" "{private}"')
    router._hypervisor.set_working_dir.assert_not_called()
    assert runtime(router)["state"] == "initialized"
    router._memory_watcher.close()
    journal_path(router).unlink()
