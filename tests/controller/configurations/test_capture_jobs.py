"""Controller capture jobs and round trips from capture into startup sets."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from gns3server.controller.configurations import capture, launch_apply, prepare_start, state
from gns3server.schemas.configurations import Engine, Source, StartupEntry
from gns3server.services.configurations.sets.store import StartupStore
from gns3server.services.configurations.shared.errors import ConfigurationError
from tests.support.configurations import configuration_project, export_result, startup_state_reply


@pytest.mark.asyncio
async def test_bulk_capture_preserves_failed_and_concurrently_edited_configs(tmp_path):
    project = configuration_project(tmp_path)
    ids = [str(uuid4()) for _ in range(3)]
    for node_id in ids:
        project.nodes[node_id] = SimpleNamespace(
            id=node_id,
            project=project,
            node_type="qemu",
            status="started",
            netmiko_device_type="cisco_asa",
            default_username=None,
            default_password=None,
        )
    store = StartupStore(project)
    document = store.read()
    original = StartupEntry(device_type="cisco_asa", content="old configuration\n", enabled=True)
    for node_id in ids:
        document = store.put_entry(document.selected, node_id, original, revision=document.revision)

    async def exported(node, options):
        assert options.backup and options.source == Source.running
        if node.id == ids[1]:
            raise ConfigurationError("console_busy")
        if node.id == ids[2]:
            current = store.read()
            store.put_entry(
                current.selected,
                node.id,
                original.model_copy(update={"content": "user edit\n"}),
                revision=current.revision,
            )
        return export_result(node, Engine.qemu, Source.running, "running-config.cfg", b"new configuration\n")

    job = {"id": "test", "nodes": {}}
    with patch("gns3server.controller.configurations.request_export", exported):
        await capture(project, document.selected, ids, job)
    assert job["status"] == "finished"
    assert job["nodes"] == {ids[0]: "captured", ids[1]: "console_busy", ids[2]: "startup_configurations_changed"}
    entries = store.read().sets[0].nodes
    assert entries[UUID(ids[0])].content == "new configuration\n"
    assert entries[UUID(ids[0])].enabled
    assert entries[UUID(ids[1])].content == "old configuration\n"
    assert entries[UUID(ids[2])].content == "user edit\n"


async def capture_then_start(project, node, export, device_type, content):
    """Capture into the selected set, enable the entry, and let the next start apply it."""
    store = StartupStore(project)
    job = {"id": "test", "nodes": {}}
    with patch("gns3server.controller.configurations.request_export", export):
        await capture(project, store.read().selected, [node.id], job)
    assert job["nodes"][node.id] == "captured"
    document = store.read()
    entry = document.sets[0].nodes[UUID(node.id)]
    assert entry.device_type == device_type and entry.content == content
    store.put_entry(document.selected, node.id, entry.model_copy(update={"enabled": True}), revision=document.revision)
    node.get = startup_state_reply()
    prepared = await prepare_start(node)
    node.post.assert_awaited_once_with("/configuration-apply", data={"device_type": device_type, "content": content})
    launch_apply(node, prepared)
    assert state(project)["nodes"][node.id]["status"] == "applied"
    assert not state(project)["tasks"]


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [None, "linux", "linux_telnet"])
async def test_webterm_captures_saved_network_while_stopped_and_restores_before_start(tmp_path, metadata):
    project = configuration_project(tmp_path)
    node = SimpleNamespace(
        id=str(uuid4()),
        project=project,
        node_type="docker",
        status="stopped",
        netmiko_device_type=metadata,
        post=AsyncMock(),
    )
    project.nodes[node.id] = node
    store = StartupStore(project)
    content = "auto eth0\niface eth0 inet dhcp\n"
    exported = export_result(node, Engine.docker, Source.saved_files, "etc/network/interfaces", content.encode())

    async def export(node, options):
        assert options.source == Source.saved_files
        assert options.device_type is None and options.credentials is None
        return exported

    await capture_then_start(project, node, export, "linux_interfaces", content)


@pytest.mark.asyncio
async def test_vpcs_saved_script_capture_and_native_startup_application(tmp_path):
    from gns3server.compute.configurations import ConfigurationService
    from gns3server.schemas.configurations import ExportOptions

    project = configuration_project(tmp_path)
    content = "set pcname PC1\nip 192.0.2.5/24 192.0.2.1\n"
    (tmp_path / "startup.vpc").write_text(content)
    node = SimpleNamespace(
        id=str(uuid4()),
        project=project,
        node_type="vpcs",
        status="stopped",
        working_dir=str(tmp_path),
        post=AsyncMock(),
    )
    project.nodes[node.id] = node
    result = await ConfigurationService(node, Engine.vpcs).export(ExportOptions())
    assert result.source == Source.saved_startup
    assert result.files[0].filename == "startup.vpc" and result.files[0].content == content.encode()
    document = StartupStore(project).read()
    await capture_then_start(project, node, AsyncMock(return_value=result), "vpcs", content)
