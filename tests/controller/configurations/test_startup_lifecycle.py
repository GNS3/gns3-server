"""Exercise the ordinary wipe/start policy against real compute adapters."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from gns3server.api.routes.compute.configurations import configuration_startup_state
from gns3server.compute.configurations import ConfigurationService, wipe_configuration
from gns3server.controller.configurations import (
    PreparedStartup,
    apply,
    enroll,
    launch_apply,
    launch_live_apply,
    managed,
    prepare_start,
    startup_delivery,
    state,
    validate_startup_entry,
    wipe_configurations,
)
from gns3server.controller.controller_error import ComputeConflictError, ControllerError
from gns3server.schemas.configurations import ApplyOptions, ConfigurationSet, Engine, Selection, StartupEntry
from gns3server.services.configurations.sets.selections import SelectionStore
from gns3server.services.configurations.sets.store import StartupStore
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.node_lease import node_lease
from gns3server.services.configurations.shared.safe_io import write_json
from gns3server.services.configurations.shared.startup_journal import journal_path, mark_started, mark_wiped, runtime
from tests.support.configurations import (
    configuration_project,
    controller_node,
    native_node,
    qemu_runtime_node,
    save_startup,
    startup_state_reply,
)
from tests.support.configurations.fixtures import compute_request


def write_config(node, path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text)


def test_media_attachment_reports_delivery_without_claiming_guest_success(tmp_path):
    project, node, store = controller_node(tmp_path, properties={"startup_media_profile": "cisco-viptela"})
    entry = StartupEntry(device_type="cisco_viptela", content="system\n", enabled=True)
    prepared = PreparedStartup(store.read().selected, entry, startup_delivery(node, entry))
    node.properties["startup_media_profile"] = None
    launch_apply(node, prepared)
    assert state(project)["nodes"][node.id]["status"] == "media_delivered"
    assert state(project)["tasks"] == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile,content,code,compute_preflight",
    [
        pytest.param(None, "banner motd #unterminated\n", "configuration_invalid_content", False, id="invalid-console"),
        pytest.param(
            "cisco-c8000v-autonomous", "hostname Saved\n", "boot_media_tool_missing", True, id="missing-media-tool"
        ),
        pytest.param(
            "cisco-c8000v-controller",
            "hostname Saved\n",
            "configuration_login_required",
            False,
            id="missing-guest-user",
        ),
    ],
)
async def test_restore_preflight_failure_leaves_running_guest_alone(
    tmp_path, profile, content, code, compute_preflight
):
    project, node, store = controller_node(
        tmp_path,
        status="started",
        netmiko_device_type="cisco_ios_telnet",
        properties={"startup_media_profile": profile},
        stop=AsyncMock(),
        default_username="admin",
        default_password="admin",
    )
    save_startup(store, node.id, "cisco_ios_telnet", content)
    if compute_preflight:
        node.post.side_effect = ComputeConflictError("compute", {"message": code})
    assert await wipe_configurations(project, [node.id]) == {node.id: code}
    node.stop.assert_not_awaited()
    assert [call.args[0] for call in node.post.await_args_list] == (
        ["/configuration-media/preflight"] if compute_preflight else []
    )


async def start_node(node):
    prepared = await prepare_start(node)
    mark_started(node)
    launch_apply(node, prepared)
    task = state(node.project)["tasks"].get("apply:" + node.id)
    if task:
        await task
    return prepared


@pytest.mark.asyncio
@pytest.mark.parametrize("enrolled", [False, True])
@pytest.mark.parametrize(
    "engine,driver",
    [
        ("qemu", "cisco_nxos"),
        ("qemu", "cisco_xr"),
        ("qemu", "cisco_asa"),
        ("qemu", "cisco_ios_telnet"),
        ("iou", "cisco_ios_telnet"),
        ("dynamips", "cisco_ios_telnet"),
        ("vpcs", "vpcs"),
    ],
)
async def test_first_wipe_delivers_the_selected_set_once_then_keeps_guest_saves(
    tmp_path, monkeypatch, engine, driver, enrolled
):
    project = SimpleNamespace(id=str(uuid4()), path=str(tmp_path / "project"), nodes={})
    root = tmp_path / "runtime"
    if engine == "qemu":
        node = qemu_runtime_node(project, root, driver)
    elif engine in ("iou", "dynamips"):
        node = native_node(root, engine)
        node.properties = {}
        # The engine writes the selected text into its own startup file.
        node.manager = SimpleNamespace(_create_config=write_config)
        node.startup_config_content = ""
    else:
        root.mkdir()
        node = SimpleNamespace(id=str(uuid4()), working_dir=str(root), status="stopped", properties={})
    node.project, node.node_type, node.locked = project, engine, False
    node.netmiko_device_type = driver if engine == "qemu" else None
    project.nodes[node.id] = node
    monkeypatch.setattr("gns3server.compute.configurations.dynamips_query", AsyncMock(return_value=["0"]))
    applied = []

    async def post(path, data=None, **kwargs):
        return await compute_request(node, engine, path, data, applied)

    async def get(path, **kwargs):
        return await compute_request(node, engine, path)

    node.post, node.get = AsyncMock(side_effect=post), AsyncMock(side_effect=get)
    store = StartupStore(project)
    document = store.read()
    first = {
        "vpcs": "set pcname Saved\n",
    }.get(driver, "hostname Saved\nend\n")
    document = save_startup(store, node.id, driver, first)

    def delivered():
        if engine == "qemu":
            return applied[-1] if applied else None
        if engine == "iou":
            return node.startup_config_content
        path = Path(node.startup_config_path) if engine == "dynamips" else root / "startup.vpc"
        return path.read_text() if path.exists() else None

    assert not journal_path(node).exists()
    # Absence of a journal must not be mistaken for permission to overwrite old state.
    assert await start_node(node) is None and delivered() in (None, "")
    mark_started_generation = runtime(node)["generation"]
    assert await wipe_configurations(project, [node.id]) == {node.id: "wiped"}
    assert runtime(node)["state"] == "clean"
    assert runtime(node)["generation"] == mark_started_generation + 1
    assert managed(node) == (engine != "qemu")
    assert await start_node(node) is not None
    assert delivered() == first
    assert store.read() == document
    assert runtime(node)["state"] == "initialized"
    # Ordinary restart must not replay the saved set over guest saves.
    assert await start_node(node) is None
    second = first.replace("Saved", "OtherSet")
    document, _ = store.create_set("Other set", revision=document.revision, select=True)
    document = save_startup(store, node.id, driver, second)
    if enrolled:
        enroll(node)
    # A changed source must not implicitly discard guest saves on Start.
    assert await start_node(node) is None
    assert delivered() == first
    generation = runtime(node)["generation"]
    assert await wipe_configurations(project, [node.id]) == {node.id: "wiped"}
    assert runtime(node)["generation"] == generation + 1
    assert await start_node(node) is not None
    assert delivered() == second
    assert store.read() == document
    assert state(project)["tasks"] == {}

    # A clean boot with startup OFF must consume the same one-time permission.
    document = save_startup(store, node.id, driver, second, enabled=False)
    assert await wipe_configurations(project, [node.id]) == {node.id: "wiped"}
    assert await start_node(node) is None
    save_startup(store, node.id, driver, second)
    assert await start_node(node) is None
    assert runtime(node)["state"] == "initialized"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["started", "suspended"])
@pytest.mark.parametrize("stop_fails", [False, True])
async def test_running_wipe_stops_before_erasing_and_preserves_saved_sets(tmp_path, status, stop_fails):

    project = SimpleNamespace(id=str(uuid4()), path=str(tmp_path), nodes={})
    node = SimpleNamespace(
        id=str(uuid4()),
        project=project,
        node_type="vpcs",
        properties={},
        locked=False,
        status=status,
        netmiko_device_type=None,
    )
    project.nodes[node.id] = node
    calls = []

    async def stop(strict=False):
        assert strict is True
        calls.append("stop")
        if stop_fails:
            raise ControllerError("compute unavailable")
        node.status = "stopped"

    async def post(path):
        # The compute is asked about the node's storage first, while the guest still runs.
        if path != "/configuration-wipe/preflight":
            assert node.status == "stopped"
        calls.append(path)

    node.stop, node.post = AsyncMock(side_effect=stop), AsyncMock(side_effect=post)
    store = StartupStore(project)
    document = save_startup(store, node.id, "vpcs", "set pcname Saved\n")
    expected = "stop_required" if stop_fails else "wiped"
    stopped = []
    assert await wipe_configurations(project, [node.id], stopped=stopped) == {node.id: expected}
    preflight = "/configuration-wipe/preflight"
    assert calls == ([preflight, "stop"] if stop_fails else [preflight, "stop", "/configuration-wipe"])
    assert stopped == ([node.id] if status != "stopped" and not stop_fails else [])
    assert store.read() == document


@pytest.mark.asyncio
async def test_a_console_platform_without_readback_reports_the_restore_as_accepted(tmp_path):
    # The other console platforms are covered by the first-wipe matrix; RouterOS has no comparable read-back.
    driver = "mikrotik_routeros"
    project, node, store = controller_node(
        tmp_path, netmiko_device_type=driver, default_username="admin", default_password="test"
    )
    content = "saved startup configuration\n"
    save_startup(store, node.id, driver, content)
    assert await wipe_configurations(project, [node.id]) == {node.id: "wiped"}
    node.get = startup_state_reply()
    prepared = await prepare_start(node)
    launch_apply(node, prepared)
    await state(project)["tasks"]["apply:" + node.id]
    assert state(project)["nodes"][node.id]["status"] == "configuration_apply_accepted"
    assert node.post.call_args.args == ("/configuration-apply",)
    assert node.post.call_args.kwargs["data"]["content"] == content
    assert node.post.call_args.kwargs["data"]["wait_ready"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "console_type,netmiko,entry_type,enabled,expected",
    [
        # A QEMU appliance is restored through its console, so Wipe of an entry that has to survive needs a serial one.
        ("telnet", "cisco_xr", "cisco_xr", True, "wiped"),
        ("ssh", "cisco_xr", "cisco_xr", True, "wiped"),
        ("vnc", "cisco_xr", "cisco_xr", True, "configuration_restore_console_required"),
        # An entry the node type cannot apply is refused, so the entry is never lost.
        ("telnet", None, "vpcs", True, "configuration_apply_unsupported"),
        # With no entry that has to survive, nothing blocks the wipe.
        ("vnc", "cisco_asa", "cisco_asa", False, "wiped"),
    ],
)
async def test_wipe_refuses_when_the_enabled_entry_cannot_be_restored(
    tmp_path, console_type, netmiko, entry_type, enabled, expected
):
    fields = {"netmiko_device_type": netmiko} if netmiko else {}
    project, node, store = controller_node(tmp_path, console_type=console_type, **fields)
    save_startup(store, node.id, entry_type, "hostname Saved\ninterface Gi0\n", enabled=enabled)
    assert await wipe_configurations(project, [node.id]) == {node.id: expected}
    if expected == "wiped":
        assert [call.args[0] for call in node.post.await_args_list] == [
            "/configuration-wipe/preflight",
            "/configuration-wipe",
        ]
    else:
        node.post.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("driver", ["cisco_nxos", "cisco_asa"])
@pytest.mark.parametrize("choice", ["none", "assigned_set"])
async def test_a_console_qemu_node_restores_only_the_set_it_is_assigned(tmp_path, driver, choice):
    project = SimpleNamespace(id=str(uuid4()), path=str(tmp_path), nodes={})
    node = SimpleNamespace(
        id=str(uuid4()),
        project=project,
        node_type="qemu",
        properties={},
        netmiko_device_type=driver,
        console_type="telnet",
        get=startup_state_reply(),
        post=AsyncMock(),
    )
    project.nodes[node.id] = node
    store = StartupStore(project)
    document = store.read()
    # The project default set also holds an enabled entry: only the node's own assignment decides.
    default = StartupEntry(device_type=driver, content="hostname Default\n", enabled=True)
    store.put_entry(document.selected, node.id, default, revision=document.revision)
    entry = StartupEntry(device_type=driver, content="hostname Assigned\n", enabled=True)
    other = ConfigurationSet(name="Assigned", nodes={UUID(node.id): entry})
    document = store.read()
    store.write(document.model_copy(update={"sets": (*document.sets, other)}), revision=document.revision)
    selection = Selection() if choice == "none" else Selection(kind="set", set_id=other.id)
    SelectionStore(project).assign(node.id, selection, 0)

    prepared = await prepare_start(node)

    if choice == "none":
        assert prepared is None
        node.get.assert_not_awaited()
    else:
        assert (prepared.set_id, prepared.entry) == (other.id, entry)
        node.get.assert_awaited_once_with("/configuration-startup-state", timeout=30)
    node.post.assert_not_awaited()
    assert node.properties == {}
    assert not managed(node)


@pytest.mark.asyncio
@pytest.mark.parametrize("assigned", [False, True])
async def test_the_start_after_a_wipe_delivers_the_nodes_assignment_not_the_project_default(tmp_path, assigned):
    project, node, store = controller_node(tmp_path, netmiko_device_type="cisco_asa")
    document = store.read()
    # The default set holds an entry of another recipe: delivering it would be refused, so it must never be used.
    default_entry = StartupEntry(device_type="cisco_ios_telnet", enabled=True, content="hostname Default\n")
    alternate_entry = StartupEntry(device_type="cisco_asa", enabled=True, content="hostname Assigned\n")
    document = store.put_entry(document.selected, node.id, default_entry, revision=document.revision)
    alternate = ConfigurationSet(name="Assigned", nodes={UUID(node.id): alternate_entry})
    store.write(document.model_copy(update={"sets": (*document.sets, alternate)}), revision=document.revision)
    selection = Selection(kind="set", set_id=alternate.id) if assigned else Selection()
    SelectionStore(project).assign(node.id, selection, 0)
    assert await wipe_configurations(project, [node.id]) == {node.id: "wiped"}
    assert [call.args[0] for call in node.post.await_args_list] == [
        "/configuration-wipe/preflight",
        "/configuration-wipe",
    ]
    assert store.read().selected == document.selected
    node.get = startup_state_reply()
    prepared = await prepare_start(node)
    if assigned:
        assert (prepared.set_id, prepared.entry) == (alternate.id, alternate_entry)
    else:
        assert prepared is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "declared,device_type,error",
    [
        (None, "cisco_ios_telnet", "device_type_required"),
        ("", "cisco_ios_telnet", "device_type_required"),
        ("linux", "cisco_ios_telnet", "device_type_unsupported"),
        ("cisco_ios", "cisco_nxos", "configuration_profile_mismatch"),
        ("cisco_asa_ssh", "cisco_ios_telnet", "configuration_profile_mismatch"),
    ],
)
async def test_missing_or_mismatched_device_type_blocks_start_and_wipe_before_runtime_changes(
    tmp_path, declared, device_type, error
):
    project, node, store = controller_node(
        tmp_path,
        status="started",
        netmiko_device_type=declared,
        # A wiped node: its next start would apply the entry.
        get=startup_state_reply(),
        stop=AsyncMock(),
        update=AsyncMock(),
    )
    document = save_startup(store, node.id, device_type, "hostname Saved\n")
    assert await wipe_configurations(project, [node.id]) == {node.id: error}
    assert node.status == "started"
    node.stop.assert_not_awaited()
    with pytest.raises(ConfigurationError, match=error):
        await prepare_start(node)
    node.post.assert_not_awaited()
    node.update.assert_not_awaited()
    assert store.read() == document


@pytest.mark.parametrize(
    "netmiko,saved",
    [
        # ASAv runs the ASA CLI.
        ("cisco_asa", "cisco_asa"),
        ("cisco_asa_ssh", "cisco_asa"),
        ("cisco_asa_telnet", "cisco_asa"),
        # Catalyst 8000v and CSR 1000v run the IOS-XE CLI, recipe cisco_ios_telnet.
        ("cisco_xe", "cisco_ios_telnet"),
        ("cisco_xe_ssh", "cisco_ios_telnet"),
        ("cisco_xe_telnet", "cisco_ios_telnet"),
        ("cisco_ios", "cisco_ios_telnet"),
    ],
)
def test_asav_and_c8000v_netmiko_names_enable_startup_through_existing_recipes(netmiko, saved):
    node = SimpleNamespace(node_type="qemu", netmiko_device_type=netmiko, console_type="telnet")
    # The entry stores the canonical recipe name, whichever alias the node uses.
    entry = StartupEntry(device_type=netmiko, content="hostname Saved\n", enabled=True)
    assert entry.device_type == saved
    validate_startup_entry(node, entry)


def test_a_qemu_node_without_a_console_recipe_cannot_enable_startup():
    entry = StartupEntry(device_type="cisco_asa", content="hostname Saved\n", enabled=True)
    for netmiko, code in ((None, "device_type_required"), ("cisco_ftd", "device_type_unsupported")):
        node = SimpleNamespace(node_type="qemu", netmiko_device_type=netmiko, console_type="telnet")
        with pytest.raises(ConfigurationError, match=code):
            validate_startup_entry(node, entry)
    # Disabled or empty entries never need a recipe, and other engines never did.
    node = SimpleNamespace(node_type="qemu", netmiko_device_type=None, console_type="telnet")
    validate_startup_entry(node, entry.model_copy(update={"enabled": False}))
    validate_startup_entry(node, entry.model_copy(update={"content": ""}))
    validate_startup_entry(SimpleNamespace(node_type="vpcs", netmiko_device_type=None), None)


@pytest.mark.asyncio
@pytest.mark.parametrize("how", ["assigned_none", "entry_disabled"])
async def test_a_qemu_node_with_startup_off_boots_the_base_image_without_a_console_recipe(tmp_path, how):
    project, node, store = controller_node(tmp_path, get=AsyncMock())
    if how == "assigned_none":
        SelectionStore(project).assign(node.id, Selection(), 0)
    else:
        entry = StartupEntry(device_type="cisco_ios_telnet", content="hostname Saved\n", enabled=False)
        store.put_entry(store.read().selected, node.id, entry, revision=0)
    assert await prepare_start(node) is None
    node.get.assert_not_awaited()


def _running_node(tmp_path, project):
    node = SimpleNamespace(
        id=str(uuid4()),
        node_type="vpcs",
        status="started",
        project=project,
        post=AsyncMock(),
        _startup_lifecycle_lock=asyncio.Lock(),
    )

    async def stop(strict=False):
        node.status = "stopped"

    node.stop = AsyncMock(side_effect=stop)
    project.nodes[node.id] = node
    return node


@pytest.mark.asyncio
async def test_wipe_cancels_pending_startup_apply(tmp_path):
    """A startup replay stuck waiting for the console must not block Wipe."""
    project = SimpleNamespace(id=str(uuid4()), path=str(tmp_path), nodes={})
    node = _running_node(tmp_path, project)
    data = state(project)
    task = asyncio.create_task(asyncio.sleep(60))
    data["tasks"]["apply:" + node.id] = task
    data["startup"].add("apply:" + node.id)
    data["nodes"][node.id] = {"status": "waiting_for_console", "set_id": "x"}
    stopped = []
    assert await wipe_configurations(project, [node.id], stopped=stopped) == {node.id: "wiped"}
    assert task.cancelled()
    assert "apply:" + node.id not in data["tasks"]
    assert node.id not in data["nodes"]
    assert stopped == [node.id]
    assert [call.args[0] for call in node.post.await_args_list] == [
        "/configuration-wipe/preflight",
        "/configuration-wipe",
    ]
    assert not node._startup_lifecycle_lock.locked()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code",
    [
        "configuration_wipe_unsupported",
        "configuration_extra_storage",
        "configuration_mount_shadowed",
        "configuration_image_changed",
        "container_state_unavailable",
        "unsafe_configuration_path",
    ],
)
async def test_storage_the_compute_cannot_reset_leaves_the_node_running(tmp_path, code):
    project = SimpleNamespace(id=str(uuid4()), path=str(tmp_path), nodes={})
    node = _running_node(tmp_path, project)
    node.post = AsyncMock(side_effect=ComputeConflictError("/configuration-wipe/preflight", {"message": code}))
    stopped = []
    assert await wipe_configurations(project, [node.id], stopped=stopped) == {node.id: code}
    assert node.status == "started" and stopped == []
    node.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_node_that_does_not_report_stopped_is_neither_wiped_nor_listed_as_stopped(tmp_path):
    project = SimpleNamespace(id=str(uuid4()), path=str(tmp_path), nodes={})
    node = _running_node(tmp_path, project)
    node.stop = AsyncMock()
    stopped = []
    assert await wipe_configurations(project, [node.id], stopped=stopped) == {node.id: "stop_required"}
    assert stopped == []
    assert [call.args[0] for call in node.post.await_args_list] == ["/configuration-wipe/preflight"]


@pytest.mark.asyncio
@pytest.mark.parametrize("during", ["startup_cancellation", "stop", "reset"])
async def test_a_live_apply_is_refused_while_its_node_is_being_wiped(tmp_path, during):
    project = SimpleNamespace(id=str(uuid4()), path=str(tmp_path), nodes={})
    node = _running_node(tmp_path, project)
    data = state(project)
    entry = StartupEntry(device_type="vpcs", content="set pcname A\n", enabled=True)
    refused = []

    def request_apply():
        with pytest.raises(ConfigurationError, match="configuration_operation_in_progress"):
            launch_live_apply(node, uuid4(), entry)
        refused.append(True)

    async def startup_apply():
        try:
            await asyncio.sleep(60)
        finally:
            data["tasks"].pop("apply:" + node.id, None)
            if during == "startup_cancellation":
                request_apply()

    async def stop(strict=False):
        if during == "stop":
            request_apply()
        node.status = "stopped"

    async def post(path):
        if during == "reset" and path == "/configuration-wipe":
            request_apply()

    node.stop = AsyncMock(side_effect=stop)
    node.post = AsyncMock(side_effect=post)
    data["tasks"]["apply:" + node.id] = asyncio.create_task(startup_apply())
    data["startup"].add("apply:" + node.id)
    await asyncio.sleep(0)

    assert await wipe_configurations(project, [node.id]) == {node.id: "wiped"}
    assert refused == [True]
    assert data["tasks"] == {} and data["jobs"] == {}
    # The reservation ends with the wipe.
    assert node.id not in data["wiping"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "engine,driver,properties",
    [
        ("docker", "linux_interfaces", {}),
        ("docker", "cisco_ios_telnet", {"environment": "GNS3_IOL_RUNNER=1"}),
    ],
)
async def test_docker_restart_keeps_saved_state_until_wipe(tmp_path, engine, driver, properties):
    project = SimpleNamespace(path=str(tmp_path / "project"), nodes={})
    node = SimpleNamespace(
        id=str(uuid4()),
        project=project,
        node_type=engine,
        properties=properties,
        working_dir=str(tmp_path),
        post=AsyncMock(),
        default_username="admin",
        default_password="test",
        netmiko_device_type=driver,
        console_type="telnet",
    )

    async def get(path, **kwargs):
        assert path == "/configuration-startup-state"
        return SimpleNamespace(json=await configuration_startup_state(Engine(engine), node))

    node.get = get
    store = StartupStore(project)
    document = store.read()
    entry = StartupEntry(device_type=driver, content="saved startup configuration\n", enabled=True)
    store.put_entry(document.selected, node.id, entry, revision=document.revision)

    # Absence of a journal must not be mistaken for permission to erase old state.
    assert await start_node(node) is None
    node.post.assert_not_awaited()
    mark_wiped(node)
    assert await start_node(node) is not None
    node.post.assert_awaited_once()
    assert runtime(node)["state"] == "initialized"
    node.post.reset_mock()

    # Both a plain restart and selecting another set preserve the guest's saves.
    assert await start_node(node) is None
    document, _ = store.create_set("Replacement", revision=store.read().revision, select=True)
    store.put_entry(document.selected, node.id, entry, revision=document.revision)
    assert await start_node(node) is None
    node.post.assert_not_awaited()

    # Starting with startup OFF still consumes the clean generation. Enabling it
    # later must not overwrite changes saved during that factory/default boot.
    document = store.read()
    document = store.put_entry(
        document.selected, node.id, entry.model_copy(update={"enabled": False}), revision=document.revision
    )
    mark_wiped(node)
    assert await start_node(node) is None
    # The compute is asked to withdraw what an earlier Start prepared; a launched runtime is left as it is.
    node.post.assert_awaited_once_with("/configuration-withdraw")
    node.post.reset_mock()
    document = store.put_entry(document.selected, node.id, entry, revision=document.revision)
    assert await start_node(node) is None
    node.post.assert_not_awaited()
    mark_wiped(node)
    assert await start_node(node) is not None
    node.post.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_restore", [False, True])
async def test_a_wipe_is_consumed_by_the_next_start_even_when_the_console_restore_fails(tmp_path, fail_restore):
    project = SimpleNamespace(path=str(tmp_path / "project"), nodes={})
    node = qemu_runtime_node(project, tmp_path / "runtime", "cisco_nxos")
    project.nodes[node.id] = node
    overlay = tmp_path / "runtime" / "hda_disk.qcow2"
    overlay.write_bytes(b"guest-saved configuration")
    applications = []

    async def get(path, **kwargs):
        assert path == "/configuration-startup-state"
        return SimpleNamespace(json=await configuration_startup_state(Engine.qemu, node))

    async def post(path, data=None, **kwargs):
        if path == "/configuration-wipe/preflight":
            await ConfigurationService(node, Engine.qemu).preflight_wipe()
        elif path == "/configuration-wipe":
            await ConfigurationService(node, Engine.qemu).wipe()
        else:
            assert path == "/configuration-apply"
            applications.append(data["content"])
            if fail_restore:
                raise ConfigurationError("configuration_apply_failed")

    node.get, node.post = get, post
    store = StartupStore(project)
    save_startup(store, node.id, "cisco_nxos", "hostname Baseline\n")
    assert await prepare_start(node) is None
    assert overlay.read_bytes() == b"guest-saved configuration"
    assert await wipe_configurations(project, [node.id]) == {node.id: "wiped"}
    assert not overlay.exists()
    prepared = await prepare_start(node)
    mark_started(node)
    launch_apply(node, prepared)
    await state(project)["tasks"]["apply:" + node.id]
    assert applications == ["hostname Baseline\n"]
    assert state(project)["nodes"][node.id]["status"] == ("configuration_apply_failed" if fail_restore else "applied")
    overlay.write_bytes(b"new guest changes")
    assert await prepare_start(node) is None
    assert overlay.read_bytes() == b"new guest changes"
    assert applications == ["hostname Baseline\n"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value,code",
    [
        ({"generation": 1, "state": "resetting"}, "configuration_outcome_unknown"),
        ({"generation": 1, "state": "preparing"}, "configuration_outcome_unknown"),
        ({"generation": 1, "state": "unexpected"}, "invalid_startup_runtime"),
        ({"state": "clean"}, "invalid_startup_runtime"),
    ],
)
async def test_an_interrupted_or_unreadable_runtime_state_blocks_start(tmp_path, value, code):
    project = SimpleNamespace(path=str(tmp_path))
    node = SimpleNamespace(
        id=str(uuid4()),
        project=project,
        node_type="qemu",
        properties={},
        netmiko_device_type="cisco_nxos",
        console_type="telnet",
        get=AsyncMock(return_value=SimpleNamespace(json=value)),
        post=AsyncMock(),
    )
    store = StartupStore(project)
    save_startup(store, node.id, "cisco_nxos", "hostname Saved\n")
    with pytest.raises(ConfigurationError, match=code):
        await prepare_start(node)
    node.post.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_state", ["legacy_existing", "initialized"])
async def test_an_ordinary_restart_ignores_an_entry_it_would_never_apply(tmp_path, runtime_state):
    project, node, store = controller_node(
        tmp_path, netmiko_device_type="cisco_xr", default_username="", default_password=""
    )
    node.get = startup_state_reply(runtime_state)
    save_startup(store, node.id, "cisco_nxos", "hostname Saved\n")
    assert await prepare_start(node) is None
    node.post.assert_not_awaited()
    node.get = startup_state_reply()
    with pytest.raises(ConfigurationError, match="configuration_profile_mismatch"):
        await prepare_start(node)


@pytest.mark.asyncio
@pytest.mark.parametrize("state,sent", [("prepared", True), ("clean", True), ("initialized", False)])
async def test_a_native_set_is_prepared_again_until_the_node_has_launched(tmp_path, state, sent):
    project, node, store = controller_node(tmp_path, node_type="iou")
    node.get = startup_state_reply(state)
    save_startup(store, node.id, "cisco_ios_telnet", "hostname Saved\n")
    assert (await prepare_start(node) is not None) is sent
    assert node.post.await_count == (1 if sent else 0)


@pytest.mark.asyncio
async def test_turning_startup_off_withdraws_a_native_preparation_once(tmp_path):
    project, node, store = controller_node(tmp_path, node_type="iou")
    node.get = startup_state_reply()
    entry = StartupEntry(device_type="cisco_ios_telnet", content="hostname Saved\n", enabled=True)
    store.put_entry(store.read().selected, node.id, entry, revision=0)
    assert await prepare_start(node) is not None
    store.put_entry(store.read().selected, node.id, entry.model_copy(update={"enabled": False}), revision=1)
    node.post.reset_mock()
    assert await prepare_start(node) is None
    node.post.assert_awaited_once_with("/configuration-withdraw")
    node.post.reset_mock()
    assert await prepare_start(node) is None
    node.post.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_state", ["legacy_existing", "initialized", "prepared"])
async def test_a_booted_or_prepared_runtime_is_never_replayed(tmp_path, runtime_state):
    project = SimpleNamespace(path=str(tmp_path / "project"))
    node = SimpleNamespace(
        id=str(uuid4()),
        project=project,
        node_type="qemu",
        working_dir=str(tmp_path),
        properties={},
        netmiko_device_type="cisco_nxos",
        console_type="telnet",
        post=AsyncMock(),
    )
    write_json(journal_path(node), {"version": 1, "generation": 1, "state": runtime_state})
    node.get = AsyncMock(return_value=SimpleNamespace(json=runtime(node)))
    store = StartupStore(project)
    save_startup(store, node.id, "cisco_nxos", "hostname Saved\n")
    assert await prepare_start(node) is None
    node.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_live_apply_cancelled_while_it_waits_for_the_node_does_not_stay_running(tmp_path):
    project = SimpleNamespace(id=str(uuid4()), path=str(tmp_path), nodes={})
    node = SimpleNamespace(id=str(uuid4()), project=project)
    entry = StartupEntry(device_type="vpcs", content="set pcname A\n")
    async with node_lease(node):
        job = launch_live_apply(node, uuid4(), entry)
        await asyncio.sleep(0)
        task = state(project)["tasks"]["apply:" + node.id]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert job["status"] == "cancelled" and job["nodes"][node.id] == "cancelled"
    assert state(project)["tasks"] == {}


def linked_project(tmp_path, link):
    """A project reached through a symlink at ``link``: the projects folder, or its own ``project-files``."""
    real = tmp_path / "disk" / "projects" / "lab"
    real.mkdir(parents=True)
    if link == "projects":
        (tmp_path / "GNS3").symlink_to(tmp_path / "disk")
        return tmp_path / "GNS3" / "projects" / "lab"
    (tmp_path / "elsewhere").mkdir()
    (real / "project-files").symlink_to(tmp_path / "elsewhere")
    return real


@pytest.mark.asyncio
@pytest.mark.parametrize("link", ["projects", "project-files"])
@pytest.mark.parametrize("engine", ["qemu", "vpcs", "iou", "dynamips", "docker"])
async def test_a_symlinked_project_folder_does_not_stop_nodes_from_starting(tmp_path, link, engine):
    _, node, _ = controller_node(linked_project(tmp_path, link), node_type=engine)
    assert await prepare_start(node) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("link", ["projects", "project-files"])
async def test_sets_and_native_runtime_work_in_a_symlinked_project_folder(tmp_path, link):
    path = linked_project(tmp_path, link)
    project = SimpleNamespace(id=str(uuid4()), path=str(path), nodes={})
    identifier = str(uuid4())
    store = StartupStore(project)
    save_startup(store, identifier, "vpcs", "set pcname A\n", enabled=False)
    assert store.read().revision == 1 and store.revision() == 1
    working = path / "project-files" / "vpcs" / identifier
    working.mkdir(parents=True)
    node = SimpleNamespace(id=identifier, working_dir=str(working), status="stopped")
    mark_wiped(node)
    service = ConfigurationService(node, Engine.vpcs)
    await service.apply(ApplyOptions(device_type="vpcs", content="set pcname B\n"))
    await service.withdraw()
    assert not (working / "startup.vpc").exists()
    (working / "startup.vpc").write_text("set pcname C\n")
    wipe_configuration(node, "vpcs")
    assert not (working / "startup.vpc").exists() and runtime(node)["state"] == "resetting"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "driver,content",
    [
        ("cisco_asa", "hostname restored\n"),
        ("cisco_nxos", "hostname restored\n"),
        ("cisco_ios_telnet", "hostname restored\n"),
    ],
)
async def test_qemu_start_uses_saved_node_credentials_and_records_result(tmp_path, driver, content):
    project = configuration_project(tmp_path)
    node = SimpleNamespace(
        id=str(uuid4()),
        project=project,
        node_type="qemu",
        properties={},
        netmiko_device_type=driver,
        console_type="telnet",
        post=AsyncMock(),
        default_username="saved-admin",
        default_password="saved-password",
    )
    store = StartupStore(project)
    document = store.read()
    entry = StartupEntry(device_type=driver, content=content, enabled=True)
    store.put_entry(document.selected, node.id, entry, revision=0)
    node.get = startup_state_reply()
    prepared = await prepare_start(node)
    launch_apply(node, prepared)
    await state(project)["tasks"]["apply:" + node.id]
    assert state(project)["nodes"][node.id]["status"] == "applied"
    assert node.post.await_args.args == ("/configuration-apply",)
    assert node.post.await_args.kwargs["data"]["credentials"] == {
        "username": "saved-admin",
        "password": "saved-password",
        "enable_secret": "saved-password" if driver in ("cisco_asa", "cisco_ios_telnet") else "",
    }
    assert node.post.await_args.kwargs["data"]["wait_ready"] is True
    assert node.post.await_args.kwargs["data"]["device_type"] == driver
    assert node.post.await_args.kwargs["data"]["content"] == content
    assert set(node.post.await_args.kwargs["data"]) == {"device_type", "content", "credentials", "wait_ready"}
    assert "saved-password" not in store.path.read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "node_type,properties",
    [("iou", {}), ("dynamips", {}), ("docker", {"environment": "GNS3_IOL_RUNNER=1"})],
)
async def test_native_ios_sets_use_the_shared_apply_endpoint_before_start_only_when_enabled(
    tmp_path, node_type, properties
):
    project, node, store = controller_node(
        tmp_path, node_type=node_type, properties=properties, put=AsyncMock(), get=startup_state_reply()
    )
    save_startup(store, node.id, "cisco_ios", "hostname selected\n", enabled=False)
    assert await prepare_start(node) is None
    node.post.assert_not_awaited()
    save_startup(store, node.id, "cisco_ios", "hostname selected\n")
    prepared = await prepare_start(node)
    node.post.assert_awaited_once_with(
        "/configuration-apply",
        data={"device_type": "cisco_ios_telnet", "content": "hostname selected\n"},
    )
    node.put.assert_not_called()
    assert state(project)["nodes"][node.id]["status"] == "prepared"
    launch_apply(node, prepared)
    assert state(project)["nodes"][node.id]["status"] == "applied"
    assert not state(project)["tasks"]


@pytest.mark.parametrize(
    "driver",
    ["cisco_asa", "cisco_ios_telnet", "cisco_nxos", "mikrotik_routeros"],
)
@pytest.mark.parametrize("override", [None, "", "explicit-enable"])
def test_default_credentials_resolve_privilege_password_and_preserve_explicit_override(driver, override):
    from gns3server.controller.configurations import credentials_for
    from gns3server.schemas.configurations import ConsoleCredentials
    from gns3server.services.configurations.console.platforms import get_platform

    node = SimpleNamespace(default_username="admin", default_password="saved-login")
    supplied = None if override is None else ConsoleCredentials(enable_secret=override)
    result = credentials_for(node, driver, supplied)
    assert result.password.get_secret_value() == "saved-login"
    expected = ("saved-login" if get_platform(driver).enable else "") if override is None else override
    assert result.enable_secret.get_secret_value() == expected
    assert "saved-login" not in repr(result)


FAILED = "configuration_apply_failed"


def failing_apply_node(tmp_path, code, details):
    """A QEMU node whose compute refuses the console apply with ``code``."""
    error = ComputeConflictError("url", {"message": code, "details": details})
    project, node, _ = controller_node(
        tmp_path,
        name="Nexus",
        default_username="admin",
        default_password="saved-password",
        post=AsyncMock(side_effect=error),
    )
    return project, node


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "code,details,expected",
    [
        # A replay the guest does not hold is reported as such, never as applied.
        ("configuration_apply_unverified", {}, {}),
        (
            FAILED,
            {"phase": "replay", "command_index": 2, "config": "PRIVATE-CONFIG"},
            {"phase": "replay", "command_index": 2},
        ),
        (
            FAILED,
            {
                "phase": "replay",
                "command_index": 2,
                "command_total": 9,
                "command": "aaa user admin password $6$salt$PRIVATE",
                "device_error": "syntax error: 'PRIVATE-CONFIG'",
                "config": "PRIVATE-CONFIG",
            },
            {
                "phase": "replay",
                "command_index": 2,
                "command_total": 9,
                "command": "aaa user admin password <masked>",
                "device_error": "syntax error: <masked>",
            },
        ),
        (FAILED, {"phase": "PRIVATE-CONFIG", "command_index": 2}, {}),
        (FAILED, {"phase": "replay", "command_index": True}, {"phase": "replay"}),
        (FAILED, {"phase": ["PRIVATE-CONFIG"]}, {}),
    ],
)
async def test_startup_relay_only_exposes_safe_restore_context(tmp_path, code, details, expected):
    project, node = failing_apply_node(tmp_path, code, details)
    selected = uuid4()
    await apply(node, selected, StartupEntry(device_type="cisco_nxos", content="hostname restored\n", enabled=True))
    result = state(project)["nodes"][node.id]
    assert result == {"status": code, "set_id": str(selected), **expected}
    assert "PRIVATE-CONFIG" not in str(result)


@pytest.mark.asyncio
async def test_failed_startup_apply_notification_and_status_carry_the_masked_location(tmp_path):
    details = {"phase": "replay", "command": "commit", "device_error": "Aborted: bad value 'SECRET'"}
    project, node = failing_apply_node(tmp_path, FAILED, details)
    project.emit_notification = MagicMock()
    await apply(node, uuid4(), StartupEntry(device_type="cisco_nxos", content="hostname x\n", enabled=True))
    status = state(project)["nodes"][node.id]
    assert status["status"] == "configuration_apply_failed"
    assert status["phase"] == "replay" and status["device_error"] == "Aborted: bad value <masked>"
    message = project.emit_notification.call_args.args[1]["message"]
    assert "phase=replay" in message and "SECRET" not in message
