import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import status

from gns3server.controller.configurations import state
from gns3server.controller.controller_error import ComputeConflictError
from gns3server.controller.node import Node
from gns3server.schemas.configurations import Engine, Source, StartupEntry
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY
from gns3server.services.configurations.boot_media import PROFILES
from gns3server.services.configurations.sets.selections import SelectionStore
from gns3server.services.configurations.sets.store import StartupStore
from tests.support.configurations import export_result, save_startup
from tests.support.configurations.fixtures import restore_controller, user1_with  # noqa: F401 (fixture used by name)

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("restore_controller")]


@pytest.fixture
def startup_node(project, compute):
    node = Node(project, compute, "ASA1", node_type="qemu")
    node.netmiko_device_type = "cisco_asa"
    node._status = "started"
    project._nodes[node.id] = node
    return node


async def test_saved_sets_revision_conflicts_and_status_excludes_credentials(client, startup_node):
    node = startup_node
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    response = await client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    document = response.json()
    document["sets"][0]["nodes"][node.id] = {"device_type": "cisco_asa", "content": "hostname ASA1\n", "enabled": True}
    saved = await client.put(path, json=document)
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1
    stale = await client.put(path, json=document)
    assert stale.status_code == 409
    assert stale.json()["message"] == "startup_configurations_changed"
    node.default_username = "admin"
    node.default_password = "private-login"
    response = await client.get(path + "/status")
    assert response.status_code == 200
    assert "credential_nodes" not in response.json()
    assert "private-login" not in response.text
    assert "private-login" not in (await client.get(path)).text


async def test_running_node_can_toggle_startup_with_a_document_larger_than_export_options(
    client, startup_node, compute
):
    from gns3server.services.configurations.sets.store import StartupStore

    node = startup_node
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    content = "hostname ASA1\n" + "! saved configuration\n" * 2048
    store = StartupStore(node.project)
    save_startup(store, node.id, "cisco_asa", content, enabled=False)
    document = (await client.get(path)).json()
    compute.post = AsyncMock()
    for enabled in (True, False, True):
        document["sets"][0]["nodes"][node.id]["enabled"] = enabled
        document["selections"][node.id] = (
            {"kind": "set", "set_id": document["selected"]} if enabled else {"kind": "none"}
        )
        response = await client.put(path, json=document)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        saved = response.json()
        assert saved["revision"] == document["revision"] + 1
        assert saved["sets"][0]["nodes"][node.id] == {
            "device_type": "cisco_asa",
            "content": content,
            "enabled": enabled,
        }
        assert saved["selections"][node.id] == {
            "kind": "set" if enabled else "none",
            "set_id": document["selected"] if enabled else None,
        }
        document = saved
    assert node.status == "started"
    compute.post.assert_not_awaited()


async def test_export_options_keep_the_small_body_limit(client, startup_node, compute):
    compute.post = AsyncMock()
    response = await client.post(
        f"/v3/projects/{startup_node.project.id}/nodes/{startup_node.id}/configuration-export",
        json={"oversized": "x" * (16 * 1024)},
    )
    assert response.status_code == 413
    assert response.json()["message"] == "configuration_request_too_large"
    compute.post.assert_not_awaited()


async def test_wipe_reports_each_node_and_preserves_saved_sets(client, startup_node, compute):
    node = startup_node
    node._node_type = "iou"
    node.netmiko_device_type = "cisco_ios_telnet"
    stopped = Node(node.project, compute, "PC1", node_type="vpcs")
    stopped._status = "stopped"
    node.project._nodes[stopped.id] = stopped
    suspended = Node(node.project, compute, "R2", node_type="iou")
    suspended._status = "suspended"
    node.project._nodes[suspended.id] = suspended
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    document["sets"][0]["nodes"][node.id] = {
        "device_type": "cisco_ios_telnet",
        "content": "hostname R1",
        "enabled": True,
    }
    saved = (await client.put(path, json=document)).json()
    compute.post = AsyncMock()
    response = await client.post(path + "/wipe", json={"all": True})
    assert response.status_code == 200, response.text
    # Every supported node is wiped in any state; only the running and suspended ones need stopping first.
    assert response.json()["nodes"] == {node.id: "wiped", stopped.id: "wiped", suspended.id: "wiped"}
    assert sorted(response.json()["stopped"]) == sorted([node.id, suspended.id])
    paths = [call.args[0] for call in compute.post.await_args_list]
    running_root = f"/projects/{node.project.id}/iou/nodes/{node.id}"
    assert paths.index(running_root + "/stop") < paths.index(running_root + "/configuration-wipe")
    stopped_root = f"/projects/{node.project.id}/vpcs/nodes/{stopped.id}"
    assert stopped_root + "/configuration-wipe" in paths
    assert stopped_root + "/stop" not in paths
    assert node.status == "stopped"
    assert (await client.get(path)).json() == saved


@pytest.mark.parametrize("body", [{}, {"node_ids": []}, {"all": False}, {"all": True, "node_ids": ["x"]}])
async def test_wipe_requires_explicit_selection(client, startup_node, compute, body):
    node = startup_node
    node._status = "started"
    compute.post = AsyncMock()
    response = await client.post(f"/v3/projects/{node.project.id}/startup-configurations/wipe", json=body)
    assert response.status_code == 422
    compute.post.assert_not_awaited()
    assert node.status == "started"


@pytest.mark.parametrize(
    "endpoint,body,count",
    [
        ("wipe", {}, 1500),
        ("wipe", {}, 10000),
        ("capture", {"set_id": "00000000-0000-0000-0000-000000000002"}, 900),
    ],
)
async def test_bulk_requests_for_large_projects_are_not_cut_off(client, startup_node, compute, endpoint, body, count):
    """Wipe All names every node it confirmed: the request limits must not stop it."""
    compute.post = AsyncMock()
    node_ids = [f"00000000-0000-0000-0001-{number:012d}" for number in range(count)]
    response = await client.post(
        f"/v3/projects/{startup_node.project.id}/startup-configurations/{endpoint}",
        json=body | {"node_ids": node_ids},
    )
    assert response.status_code == 404, response.text
    assert response.json()["message"] != "configuration_request_too_large"
    compute.post.assert_not_awaited()


async def test_wipe_is_refused_on_a_frozen_template_before_anything_is_touched(client, startup_node, compute):
    node = startup_node
    node._status = "stopped"
    node.project.frozen = True
    compute.post = AsyncMock()
    response = await client.post(
        f"/v3/projects/{node.project.id}/startup-configurations/wipe", json={"node_ids": [node.id]}
    )
    assert response.status_code == 403
    assert "frozen" in response.json()["message"]
    compute.post.assert_not_awaited()


async def test_wipe_ignores_layout_lock_but_rejects_unknown_nodes(client, startup_node, compute):
    node = startup_node
    node._status = "started"
    node.locked = True
    compute.post = AsyncMock()
    path = f"/v3/projects/{node.project.id}/startup-configurations/wipe"
    response = await client.post(path, json={"node_ids": [node.id]})
    assert response.json()["nodes"][node.id] == "wiped"
    assert node.locked is True
    assert node.status == "stopped"
    assert compute.post.await_args.args[0].endswith("/configuration-wipe")
    compute.post.reset_mock()
    response = await client.post(path, json={"node_ids": [node.id, "00000000-0000-0000-0000-000000000001"]})
    assert response.status_code == 404
    compute.post.assert_not_awaited()


@pytest.mark.parametrize("message", ["private diagnostic", {}, [], None])
async def test_wipe_continues_after_compute_conflict_and_hides_diagnostics(client, startup_node, compute, message):
    from gns3server.controller.controller_error import ComputeConflictError

    node = startup_node
    node._status = "started"
    other = Node(node.project, compute, "PC1", node_type="vpcs")
    other._status = "started"
    node.project._nodes[other.id] = other
    # The first node fails its preflight; the other is checked, stopped and wiped.
    compute.post = AsyncMock(side_effect=[ComputeConflictError("url", {"message": message}), None, None, None])
    response = await client.post(
        f"/v3/projects/{node.project.id}/startup-configurations/wipe", json={"node_ids": [node.id, other.id]}
    )
    assert response.status_code == 200
    assert response.json()["nodes"] == {node.id: "configuration_wipe_failed", other.id: "wiped"}
    assert "private diagnostic" not in response.text


async def test_wipe_skips_only_the_nodes_a_running_job_works_on(client, startup_node, compute):
    node = startup_node
    node._node_type = "iou"
    other = Node(node.project, compute, "PC1", node_type="vpcs")
    other._status = "stopped"
    node.project._nodes[other.id] = other
    compute.post = AsyncMock()
    state(node.project)["jobs"]["capture"] = {"status": "running", "node_ids": [node.id]}
    response = await client.post(f"/v3/projects/{node.project.id}/startup-configurations/wipe", json={"all": True})
    assert response.status_code == 200, response.text
    assert response.json()["nodes"] == {node.id: "configuration_operation_in_progress", other.id: "wiped"}
    paths = [call.args[0] for call in compute.post.await_args_list]
    assert not any(node.id in path for path in paths)
    # A job that has finished no longer holds anything back.
    state(node.project)["jobs"]["capture"]["status"] = "finished"
    response = await client.post(f"/v3/projects/{node.project.id}/startup-configurations/wipe", json={"all": True})
    assert response.json()["nodes"][node.id] == "wiped"


async def test_capture_job_stores_running_configuration_and_retains_disabled_startup(client, startup_node, compute):
    node = startup_node
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    exported = export_result(
        node, Engine.qemu, Source.running, "running-config.cfg", b"ASA Version 9.19(1)\nhostname captured\n: end\n"
    )
    compute.post = AsyncMock(return_value=MagicMock(json=exported.model_dump(mode="json")))
    response = await client.post(path + "/capture", json={"set_id": document["selected"]})
    assert response.status_code == 202, response.text
    task = state(node.project)["tasks"].get(response.json()["id"])
    if task:
        await asyncio.wait_for(task, timeout=2)
    status = (await client.get(path + "/status")).json()
    assert status["jobs"][0]["status"] == "finished"
    assert status["jobs"][0]["nodes"][node.id] == "captured"
    stored = (await client.get(path)).json()["sets"][0]["nodes"][node.id]
    assert "hostname captured" in stored["content"]
    assert stored["enabled"] is False
    assert compute.post.await_args.kwargs["data"]["backup"] is True


@pytest.mark.parametrize("denied", ["everything", "console"])
@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("PUT", "", "document"),
        ("POST", "/capture", {"set_id": "00000000-0000-0000-0000-000000000000"}),
        ("POST", "/sets", {"name": "lab", "revision": 0}),
        ("POST", "/wipe", {"all": True}),
        ("POST", "node-apply", {"set_id": "00000000-0000-0000-0000-000000000000", "revision": 0}),
    ],
)
async def test_write_routes_require_modify_and_console_permissions(
    client, startup_node, test_user, compute, method, suffix, body, denied
):
    node = startup_node
    node._status = "stopped"
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    if suffix == "node-apply":
        path, suffix = f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-apply", ""
    token = auth_service.create_access_token("user1", secret_key=DEFAULT_JWT_SECRET_KEY)

    async def permission(user_id, path, privilege):
        return denied == "console" and privilege != "Node.Console"

    compute.post = AsyncMock()
    with user1_with(permission) as headers:
        response = await client.request(
            method,
            path + suffix,
            json=document if body == "document" else body,
            headers=headers,
        )
    assert response.status_code == 403
    compute.post.assert_not_called()


@pytest.mark.parametrize(
    "node_type,driver", [("vpcs", "cisco_ios"), ("iou", "cisco_asa"), ("qemu", "linux_interfaces")]
)
async def test_saved_formats_must_match_node_engine(client, startup_node, compute, node_type, driver):
    node = Node(startup_node.project, compute, "invalid-format", node_type=node_type)
    node.project._nodes[node.id] = node
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    document["sets"][0]["nodes"][node.id] = {"device_type": driver, "content": "config", "enabled": True}
    response = await client.put(path, json=document)
    assert response.status_code == 422
    assert response.json()["message"] == "configuration_apply_unsupported"


async def test_bulk_capture_excludes_infrastructure_nodes(client, startup_node, compute):
    node = startup_node
    cloud = Node(node.project, compute, "Cloud1", node_type="cloud")
    node.project._nodes[cloud.id] = cloud
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    with patch("gns3server.api.routes.controller.configurations.launch_capture", return_value={"id": "test"}) as launch:
        response = await client.post(path + "/capture", json={"set_id": document["selected"]})
    assert response.status_code == 202
    assert launch.call_args.args[2] == [node.id]
    response = await client.post(path + "/capture", json={"set_id": document["selected"], "node_ids": [cloud.id]})
    assert response.status_code == 422


async def test_webterm_http_save_then_capture_from_empty_editor(client, startup_node, compute):
    node = startup_node
    node._node_type = "docker"
    node.netmiko_device_type = None
    node._status = "stopped"
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    document["sets"][0]["nodes"][node.id] = {"device_type": "linux_interfaces", "content": "", "enabled": False}
    response = await client.put(path, json=document)
    assert response.status_code == 200, response.text
    content = b"auto eth0\niface eth0 inet dhcp\n"
    result = export_result(node, Engine.docker, Source.saved_files, "etc/network/interfaces", content)
    compute.post = AsyncMock(return_value=MagicMock(json=result.model_dump(mode="json")))
    response = await client.post(path + "/capture", json={"set_id": document["selected"], "node_ids": [node.id]})
    assert response.status_code == 202, response.text
    task = state(node.project)["tasks"].get(response.json()["id"])
    if task:
        await asyncio.wait_for(task, timeout=2)
    stored = (await client.get(path)).json()["sets"][0]["nodes"][node.id]
    assert stored["content"] == content.decode()


async def test_invalid_set_response_reports_safe_fields_and_reasons(client, startup_node):
    path = f"/v3/projects/{startup_node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    document["sets"][0]["nodes"][startup_node.id] = {
        "device_type": "invalid-secret-value",
        "content": "sensitive-config",
        "enabled": False,
    }
    response = await client.put(path, json=document)
    assert response.status_code == 422
    assert response.json()["details"]["validation_errors"]
    assert "device_type" in response.text
    assert "invalid-secret-value" not in response.text and "sensitive-config" not in response.text


@pytest.mark.parametrize("driver", ["cisco_asa", "cisco_nxos"])
async def test_live_apply_uses_saved_configuration_and_credentials_without_enabling_startup(
    client, startup_node, compute, driver
):
    from gns3server.services.configurations.sets.store import StartupStore

    node = startup_node
    node.netmiko_device_type = driver
    content = "hostname live\n"
    node.default_username = "admin"
    node.default_password = "saved-login"
    store = StartupStore(node.project)
    document = save_startup(store, node.id, driver, content, enabled=False)
    compute.post = AsyncMock()
    response = await client.post(
        f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-apply",
        json={"set_id": str(document.selected), "revision": document.revision},
    )
    assert response.status_code == 202, response.text
    task = state(node.project)["tasks"].get("apply:" + node.id)
    if task:
        await task
    job = state(node.project)["jobs"][response.json()["id"]]
    # Nothing reads a live apply back: the job only reports that the node took the commands.
    assert job["nodes"][node.id] == "configuration_apply_accepted"
    assert job["status"] == "finished"
    payload = compute.post.await_args.kwargs["data"]
    assert payload["running"] is True and payload["wait_ready"] is False
    assert payload["credentials"]["username"] == "admin"
    assert payload["credentials"]["password"] == "saved-login"
    assert payload["content"] == content
    assert payload["device_type"] == driver
    assert store.read() == document
    assert node.id not in state(node.project)["nodes"]


@pytest.mark.parametrize(
    "condition,code",
    [
        ("stale", "startup_configurations_changed"),
        ("locked", "node_locked"),
        ("stopped", "start_required"),
        ("mismatched_recipe", "configuration_profile_mismatch"),
    ],
)
async def test_live_apply_rejects_invalid_state_before_compute(client, startup_node, compute, condition, code):
    from gns3server.services.configurations.sets.store import StartupStore

    node = startup_node
    store = StartupStore(node.project)
    document = save_startup(store, node.id, "cisco_asa", "hostname live\n", enabled=False)
    if condition == "locked":
        node.locked = True
    if condition == "stopped":
        node._status = "stopped"
    if condition == "mismatched_recipe":
        node.netmiko_device_type = "cisco_nxos"
    compute.post = AsyncMock()
    response = await client.post(
        f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-apply",
        json={"set_id": str(document.selected), "revision": 0 if condition == "stale" else document.revision},
    )
    assert response.status_code == 409
    assert response.json()["message"] == code
    compute.post.assert_not_awaited()


@pytest.mark.parametrize("large", [False, True])
async def test_set_archive_export_and_import_round_trip(client, startup_node, compute, large):
    node = startup_node
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    content = "hostname ASA1\n"
    if large:
        # Varied comments keep the ZIP large enough to exercise the import limit.
        content += "".join(f"! {uuid4().hex}\n" for _ in range(1024))
    document["sets"][0]["nodes"][node.id] = {"device_type": "cisco_asa", "content": content, "enabled": True}
    saved = (await client.put(path, json=document)).json()
    export = await client.get(path + f"/sets/{saved['sets'][0]['id']}/export")
    assert export.status_code == 200, export.text
    if large:
        assert len(export.content) > 16 * 1024
    assert export.headers["content-type"] == "application/zip"
    assert export.headers["cache-control"] == "no-store"
    assert export.headers["x-configuration-content"] == "may-contain-secrets"
    assert "attachment;" in export.headers["content-disposition"]

    other = Node(node.project, compute, "ASA2", node_type="qemu")
    other.netmiko_device_type = "cisco_asa"
    other._status = "stopped"
    node.project._nodes[other.id] = other
    imported = await client.post(
        path + "/import",
        json={
            "archive": base64.b64encode(export.content).decode("ascii"),
            "name": "Imported",
            "nodes": {node.id: other.id},
        },
    )
    assert imported.status_code == 201, imported.text
    result = imported.json()
    assert result["set"]["name"] == "Imported"
    assert result["mapped"] == {node.id: other.id}
    imported_document = (await client.get(path)).json()
    imported_set = next(item for item in imported_document["sets"] if item["name"] == "Imported")
    assert imported_set["nodes"][other.id]["content"] == content
    # Import neither selects the new set nor marks nodes as managed.
    assert (await client.get(path)).json()["selected"] == saved["selected"]
    assert other.id not in SelectionStore(node.project).selections()["nodes"]


@pytest.mark.parametrize("assignment", [None, "assign_nodes", "select"])
async def test_archive_import_requires_console_privilege_only_for_changed_choices(
    client, startup_node, test_user, compute, assignment
):
    from gns3server.services.configurations.sets import archive
    from gns3server.services.configurations.sets.store import StartupStore

    node = startup_node
    other = Node(node.project, compute, "ASA2", node_type="qemu")
    node.project._nodes[other.id] = other
    store = StartupStore(node.project)
    document = save_startup(store, node.id, "cisco_asa", "hostname ASA1\n")
    _, payload = archive.build(node.project, document.selected)
    body = {"archive": base64.b64encode(payload).decode(), "nodes": {node.id: other.id}}
    if assignment:
        body[assignment] = True
    denied_node = node if assignment == "select" else other

    async def permission(user_id, path, privilege):
        return not (privilege == "Node.Console" and path.endswith(f"/nodes/{denied_node.id}"))

    with user1_with(permission) as headers:
        response = await client.post(
            f"/v3/projects/{node.project.id}/startup-configurations/import",
            json=body,
            headers=headers,
        )
    assert response.status_code == (403 if assignment else 201), response.text
    if assignment:
        assert store.read() == document


async def test_set_archive_import_rejects_invalid_archives(client, startup_node):
    path = f"/v3/projects/{startup_node.project.id}/startup-configurations"
    for archive in (base64.b64encode(b"not a zip").decode("ascii"), "***"):
        response = await client.post(path + "/import", json={"archive": archive})
        assert response.status_code == 422
        assert response.json()["message"] == "invalid_configuration_archive"
    assert (await client.get(path)).json()["revision"] == 0


async def test_set_creation_and_revision_guards(client, startup_node):
    path = f"/v3/projects/{startup_node.project.id}/startup-configurations"
    created = await client.post(path + "/sets", json={"name": "lab", "revision": 0})
    assert created.status_code == 201, created.text
    assert created.json()["revision"] == 1
    assert created.json()["set"]["name"] == "lab" and created.json()["set"]["entries"] == 0
    assert [item["name"] for item in (await client.get(path)).json()["sets"]] == ["Default", "lab"]

    # A stale revision and a duplicate name never overwrite existing state.
    stale = await client.post(path + "/sets", json={"name": "other", "revision": 0})
    assert stale.status_code == 409 and stale.json()["message"] == "startup_configurations_changed"
    duplicate = await client.post(path + "/sets", json={"name": "LAB", "revision": 1})
    assert duplicate.status_code == 409 and duplicate.json()["message"] == "duplicate_configuration_set_names"


async def test_editing_startup_file_preserves_explicit_off_assignment(client, startup_node):
    from gns3server.schemas.configurations import Selection
    from gns3server.services.configurations.sets.selections import SelectionStore

    node = startup_node
    assignments = SelectionStore(node.project)
    assignments.assign(node.id, Selection(), 0)
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    document["sets"][0]["nodes"][node.id] = {
        "device_type": "cisco_asa",
        "content": "hostname Uploaded\n",
        "enabled": True,
    }
    response = await client.put(path, json=document)
    assert response.status_code == 200, response.text
    source = assignments.selections()["nodes"][node.id]
    assert source == {"kind": "none", "set_id": None}
    revision = assignments.selections()["revision"]
    stale = await client.put(path, json=document)
    assert stale.status_code == 409
    assert assignments.selections()["revision"] == revision


async def test_node_assignments_boot_independently_and_bulk_apply_replaces_them(client, startup_node, compute):
    from gns3server.controller.configurations import assigned_entry, selected_entry

    node = startup_node
    node._node_type = "vpcs"
    neighbor = Node(node.project, compute, "PC2", node_type="vpcs")
    node.project._nodes[neighbor.id] = neighbor
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    default = document["selected"]
    alternate = str(uuid4())

    def entry(name):
        return {"device_type": "vpcs", "content": f"set pcname {name}\n", "enabled": True}

    document["sets"][0]["nodes"] = {node.id: entry("A1"), neighbor.id: entry("A2")}
    document["sets"].append({"id": alternate, "name": "Alternate", "nodes": {node.id: entry("B1")}})
    document["selections"] = {node.id: {"kind": "set", "set_id": alternate}}
    response = await client.put(path, json=document)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["selected"] == default
    assert selected_entry(node)[1].content == "set pcname B1\n"
    assert selected_entry(neighbor)[1].content == "set pcname A2\n"
    # Wipe's setup check and native startup must resolve the same per-node set.
    assert assigned_entry(node)[0] == UUID(alternate)

    # Editing Default does not replace the node's Alternate assignment.
    saved["sets"][0]["nodes"][node.id] = entry("EditedA1")
    response = await client.put(path, json=saved)
    assert response.status_code == 200, response.text
    assert selected_entry(node)[1].content == "set pcname B1\n"
    disabled = response.json()
    disabled["sets"][1]["nodes"][node.id]["enabled"] = False
    response = await client.put(path, json=disabled)
    assert response.status_code == 200, response.text
    assert selected_entry(node) is None
    bulk = response.json()
    bulk["selections"] = {identifier: {"kind": "set", "set_id": default} for identifier in (node.id, neighbor.id)}
    response = await client.put(path, json=bulk)
    assert response.status_code == 200, response.text
    assert selected_entry(node)[1].content == "set pcname EditedA1\n"
    assert selected_entry(neighbor)[1].content == "set pcname A2\n"

    # Explicit OFF remains OFF when another set's text is edited.
    off = response.json()
    off["selections"][node.id] = {"kind": "none"}
    off["sets"][1]["nodes"][node.id] = entry("ChangedB1")
    response = await client.put(path, json=off)
    assert response.status_code == 200, response.text
    assert selected_entry(node) is None
    assert selected_entry(neighbor)[1].content == "set pcname A2\n"


async def test_assignment_conflict_rejects_configuration_write_before_mutation(client, startup_node):
    node = startup_node
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    response = await client.put(
        path + "/selections", json={"revision": 0, "node_ids": [node.id], "selection": {"kind": "none"}}
    )
    assert response.status_code == 200, response.text
    document["sets"][0]["nodes"][node.id] = {
        "device_type": "cisco_asa",
        "content": "hostname stale\n",
        "enabled": True,
    }
    response = await client.put(path, json=document)
    assert response.status_code == 409, response.text
    current = (await client.get(path)).json()
    assert current["revision"] == 0
    assert current["sets"][0]["nodes"] == {}
    assert current["selections"][node.id]["kind"] == "none"


async def test_deleting_assigned_set_disables_node_and_invalid_assignments_do_not_save(client, startup_node):
    node = startup_node
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    alternate = str(uuid4())
    document["sets"].append({"id": alternate, "name": "Empty alternate", "nodes": {}})
    document["selections"][node.id] = {"kind": "set", "set_id": alternate}
    response = await client.put(path, json=document)
    assert response.status_code == 200, response.text
    saved = response.json()
    saved["sets"].pop()
    response = await client.put(path, json=saved)
    assert response.status_code == 200, response.text
    assert response.json()["selections"][node.id]["kind"] == "none"
    invalid = response.json()
    invalid["selections"][node.id] = {"kind": "set", "set_id": str(uuid4())}
    response = await client.put(path, json=invalid)
    assert response.status_code == 404, response.text
    assert (await client.get(path)).json()["revision"] == invalid["revision"]


async def test_deleting_project_default_disables_nodes_that_inherited_it(client, startup_node):
    from gns3server.controller.configurations import selected_entry

    node = startup_node
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    default = document["selected"]
    alternate = str(uuid4())
    entry = {"device_type": "cisco_asa", "content": "hostname Default\n", "enabled": True}
    document["sets"][0]["nodes"][node.id] = entry
    document["sets"].append({"id": alternate, "name": "Alternate", "nodes": {node.id: entry}})
    document["selected"] = alternate
    response = await client.put(path, json=document)
    assert response.status_code == 200, response.text
    assert selected_entry(node)[0] == UUID(alternate)
    saved = response.json()
    saved["sets"].pop()
    saved["selected"] = default
    response = await client.put(path, json=saved)
    assert response.status_code == 200, response.text
    assert response.json()["selected"] == default
    assert response.json()["selections"][node.id]["kind"] == "none"
    assert selected_entry(node) is None


@pytest.mark.parametrize(
    "engine,driver",
    [
        ("qemu", "cisco_asa"),
        ("vpcs", "vpcs"),
        ("docker", "linux_interfaces"),
        ("iou", "cisco_ios_telnet"),
        ("dynamips", "cisco_ios_telnet"),
    ],
)
@pytest.mark.parametrize("status", ["started", "stopped", "suspended"])
async def test_startup_switch_off_and_on_only_updates_saved_choices(
    client, startup_node, compute, engine, driver, status
):
    node = startup_node
    node._node_type, node._status = engine, status
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    document = (await client.get(path)).json()
    selected = document["selected"]
    content = "saved configuration\n"
    document["sets"][0]["nodes"][node.id] = {"device_type": driver, "content": content, "enabled": True}
    document["selections"][node.id] = {"kind": "set", "set_id": selected}
    response = await client.put(path, json=document)
    assert response.status_code == 200, response.text
    compute.get, compute.post = AsyncMock(), AsyncMock()
    for enabled in (False, True, False):
        document = response.json()
        previous_revision = document["revision"]
        previous_selection_revision = document["selection_revision"]
        document["sets"][0]["nodes"][node.id]["enabled"] = enabled
        document["selections"][node.id] = {"kind": "set", "set_id": selected} if enabled else {"kind": "none"}
        response = await client.put(path, json=document)
        assert response.status_code == 200, response.text
        saved = response.json()
        assert saved["selected"] == selected
        assert saved["revision"] == previous_revision + 1
        assert saved["selection_revision"] == previous_selection_revision + 1
        assert saved["sets"][0]["nodes"][node.id]["enabled"] is enabled
        assert saved["sets"][0]["nodes"][node.id]["content"] == content
        assert saved["selections"][node.id]["kind"] == ("set" if enabled else "none")
        assert node.status == status
        compute.get.assert_not_awaited()
        compute.post.assert_not_awaited()
        assert (await client.get(path)).json() == saved


async def test_unauthenticated_request_is_rejected_before_its_body_is_buffered(client, startup_node, monkeypatch):
    from starlette.requests import Request

    def forbidden(self):
        raise AssertionError("body read before authentication")

    monkeypatch.setattr(Request, "stream", forbidden)
    path = f"/v3/projects/{startup_node.project.id}/startup-configurations"
    response = await client.post(
        path + "/import",
        content=b"x" * (1024 * 1024),
        headers={"Authorization": "Bearer invalid_token", "Content-Type": "application/json"},
    )
    assert response.status_code == 401


# The read-only boot media profile catalog.
async def test_the_catalog_lists_every_profile(app, client):
    response = await client.get(app.url_path_for("get_startup_media_profiles"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [
        {"id": p.id, "title": p.title, "device_type": p.device_types[0], "description": p.description}
        for p in PROFILES.values()
    ]
    assert response.json()[0].keys() == {"id", "title", "device_type", "description"}


async def test_a_selection_of_nodes_gets_one_choice_in_one_write(client, startup_node, compute):
    first = startup_node
    second = Node(first.project, compute, "ASA2", node_type="qemu")
    second.netmiko_device_type = "cisco_asa"
    first.project._nodes[second.id] = second
    store = StartupStore(first.project)
    document, extra = store.create_set("Core", revision=store.read().revision)
    store.put_entry(
        extra.id,
        first.id,
        StartupEntry(device_type="cisco_asa", content="hostname A\n", enabled=True),
        revision=document.revision,
    )
    path = f"/v3/projects/{first.project.id}/startup-configurations"
    body = {"revision": 0, "node_ids": [first.id, second.id], "selection": {"kind": "set", "set_id": str(extra.id)}}
    response = await client.put(f"{path}/selections", json=body)
    assert response.status_code == 200
    # The node without an enabled entry in the set is named: it would boot with its image defaults.
    assert response.json() == {"revision": 1, "node_ids": [first.id, second.id], "without_startup": [second.id]}
    chosen = (await client.get(path)).json()["selections"]
    assert chosen == {
        first.id: {"kind": "set", "set_id": str(extra.id)},
        second.id: {"kind": "set", "set_id": str(extra.id)},
    }

    # Clearing keeps the saved texts and only changes the choice.
    cleared = {"revision": 1, "node_ids": [first.id, second.id, first.id], "selection": {"kind": "none"}}
    response = await client.put(f"{path}/selections", json=cleared)
    assert response.json() == {"revision": 2, "node_ids": [first.id, second.id], "without_startup": []}
    assert set(item["kind"] for item in (await client.get(path)).json()["selections"].values()) == {"none"}
    assert store.set(extra.id)[1].nodes[UUID(first.id)].content == "hostname A\n"

    stale = await client.put(f"{path}/selections", json=cleared)
    assert stale.status_code == 409
    compute.post.assert_not_called()


@pytest.mark.parametrize(
    ("case", "code"),
    [("unknown_node", 404), ("unknown_set", 404), ("wrong_engine", 422), ("no_nodes", 422)],
)
async def test_a_bulk_choice_is_all_or_nothing(client, startup_node, compute, case, code):
    node = startup_node
    store = StartupStore(node.project)
    document, extra = store.create_set("Core", revision=store.read().revision)
    other = Node(node.project, compute, "PC1", node_type="vpcs")
    node.project._nodes[other.id] = other
    store.put_entry(
        extra.id,
        other.id,
        StartupEntry(device_type="vpcs", content="ip dhcp\n", enabled=True),
        revision=document.revision,
    )
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    selection = {"kind": "set", "set_id": str(extra.id)}
    body = {"revision": 0, "node_ids": [node.id, other.id], "selection": selection}
    if case == "unknown_node":
        body["node_ids"] = [node.id, str(uuid4())]
    elif case == "unknown_set":
        body["selection"] = {"kind": "set", "set_id": str(uuid4())}
    elif case == "wrong_engine":
        # The VPCS node would get an entry of a device its engine cannot apply.
        store.put_entry(
            extra.id,
            other.id,
            StartupEntry(device_type="cisco_asa", content="hostname x\n", enabled=True),
            revision=store.read().revision,
        )
    else:
        body["node_ids"] = []
    response = await client.put(f"{path}/selections", json=body)
    assert response.status_code == code, response.text
    assert (await client.get(path)).json()["selections"] == {}


@pytest.mark.parametrize(("kind", "needs_console"), [("set", True), ("none", False)])
async def test_a_bulk_choice_needs_rights_only_on_the_chosen_nodes(
    client, startup_node, compute, test_user, kind, needs_console
):
    node = startup_node
    stranger = Node(node.project, compute, "other", node_type="qemu")
    node.project._nodes[stranger.id] = stranger
    store = StartupStore(node.project)
    selection = {"kind": "none"} if kind == "none" else {"kind": "set", "set_id": str(store.read().selected)}
    asked = []

    async def permission(user_id, path, privilege):
        asked.append((path.rsplit("/", 1)[-1], privilege))
        return not path.endswith(stranger.id)

    with user1_with(permission) as headers:
        response = await client.put(
            f"/v3/projects/{node.project.id}/startup-configurations/selections",
            json={"revision": 0, "node_ids": [node.id], "selection": selection},
            headers=headers,
        )
    assert response.status_code == 200, response.text
    assert ((node.id, "Node.Console") in asked) is needs_console
    assert not any(identifier == stranger.id for identifier, _ in asked)


ASA_TEXT = "ASA Version 9.19(1)\nhostname asa\n: end\n"


async def test_a_set_that_start_would_refuse_cannot_be_enabled_or_assigned(client, startup_node, compute):
    node = startup_node  # An ASA console node: an IOS entry fits its engine, not its console recipe.
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    wrong = {"device_type": "cisco_ios_telnet", "content": "hostname R1\n", "enabled": True}
    document = (await client.get(path)).json()
    document["sets"][0]["nodes"][node.id] = wrong
    refused = await client.put(path, json=document)
    assert (refused.status_code, refused.json()["message"]) == (409, "configuration_profile_mismatch")
    # The text can still be kept and edited with startup off.
    document["sets"][0]["nodes"][node.id] = wrong | {"enabled": False}
    assert (await client.put(path, json=document)).status_code == 200
    # An enabled entry in a set nothing uses is fine until a node is pointed at it.
    document = (await client.get(path)).json()
    other = str(uuid4())
    document["sets"].append({"id": other, "name": "other", "nodes": {node.id: wrong}})
    saved = await client.put(path, json=document)
    assert saved.status_code == 200, saved.text
    selection = {"kind": "set", "set_id": other}
    revision = saved.json().get("selection_revision", 0)
    response = await client.put(
        path + "/selections", json={"revision": revision, "node_ids": [node.id], "selection": selection}
    )
    assert (response.status_code, response.json()["message"]) == (409, "configuration_profile_mismatch")


async def test_capture_uses_the_nodes_current_driver_not_the_old_entrys(client, startup_node, compute):
    node = startup_node
    store = StartupStore(node.project)
    selected = store.read().selected
    store.put_entry(
        selected,
        node.id,
        StartupEntry(device_type="cisco_ios_telnet", content="hostname old\n", enabled=False),
        revision=0,
    )
    result = export_result(node, Engine.qemu, Source.running, "running-config.cfg", ASA_TEXT.encode())
    compute.post = AsyncMock(return_value=MagicMock(json=result.model_dump(mode="json")))
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    response = await client.post(path + "/capture", json={"set_id": str(selected), "node_ids": [node.id]})
    assert response.status_code == 202, response.text
    await asyncio.wait_for(state(node.project)["tasks"][response.json()["id"]], timeout=2)
    assert compute.post.await_args.kwargs["data"]["device_type"] == "cisco_asa"
    assert store.read().sets[0].nodes[UUID(node.id)].device_type == "cisco_asa"


async def test_a_set_export_is_refused_when_the_set_changed_since_it_was_confirmed(client, startup_node):
    node = startup_node
    store = StartupStore(node.project)
    selected = store.read().selected
    path = f"/v3/projects/{node.project.id}/startup-configurations/sets/{selected}/export"
    assert (await client.get(path + "?revision=0")).status_code == 200
    store.put_entry(selected, node.id, StartupEntry(device_type="cisco_asa", content="hostname B\n"), revision=0)
    stale = await client.get(path + "?revision=0")
    assert (stale.status_code, stale.json()["message"]) == (409, "startup_configurations_changed")
    assert (await client.get(path)).status_code == 200


async def test_a_failed_live_apply_keeps_where_it_failed(client, startup_node, compute):
    node = startup_node
    store = StartupStore(node.project)
    document = save_startup(store, node.id, "cisco_asa", "hostname x\n", enabled=False)
    body = {"message": "configuration_apply_failed", "details": {"phase": "prepare", "command_index": 2}}
    compute.post = AsyncMock(side_effect=ComputeConflictError("url", body))
    response = await client.post(
        f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-apply",
        json={"set_id": str(document.selected), "revision": document.revision},
    )
    task = state(node.project)["tasks"].get("apply:" + node.id)
    if task:
        await task
    job = state(node.project)["jobs"][response.json()["id"]]
    assert job["nodes"][node.id] == "configuration_apply_failed"
    assert job["details"][node.id]["phase"] == "prepare" and job["details"][node.id]["command_index"] == 2


async def _saved_entry(node):
    store = StartupStore(node.project)
    save_startup(store, node.id, "cisco_asa", "enable secret TOPSECRET\n", enabled=False)
    return store


async def test_a_closed_project_neither_shows_nor_loses_its_saved_configurations(client, startup_node):
    """A closed project has no loaded nodes: nothing can be authorized per node, and nothing is "absent"."""
    node = startup_node
    store = await _saved_entry(node)
    before = store.read()
    path = f"/v3/projects/{node.project.id}/startup-configurations"
    node.project._status = "closed"
    node.project._nodes.clear()
    empty = {"version": 1, "revision": before.revision, "selected": str(before.selected), "sets": []}
    for response in (
        await client.get(path),
        await client.get(path + f"/sets/{before.selected}/export"),
        await client.put(path, json=empty),
        await client.post(path + "/sets", json={"name": "x", "revision": before.revision}),
    ):
        assert "TOPSECRET" not in response.text
        assert response.status_code in (409, 422), response.text
    assert store.read() == before


@pytest.mark.parametrize("route", ["put", "create", "selections", "capture", "export_save"])
async def test_a_frozen_project_refuses_every_configuration_change(client, startup_node, compute, route):
    node = startup_node
    store = await _saved_entry(node)
    before = store.read()
    base = f"/v3/projects/{node.project.id}"
    path = f"{base}/startup-configurations"
    document = (await client.get(path)).json()
    node.project.frozen = True
    compute.post = AsyncMock()
    selected, revision = str(before.selected), before.revision
    requests = {
        "put": ("PUT", path, document),
        "create": ("POST", path + "/sets", {"name": "x", "revision": revision}),
        "selections": (
            "PUT",
            path + "/selections",
            {"revision": 0, "node_ids": [node.id], "selection": {"kind": "none"}},
        ),
        "capture": ("POST", path + "/capture", {"set_id": selected, "node_ids": [node.id]}),
        "export_save": ("POST", f"{base}/nodes/{node.id}/configuration-export?save_to_set=true", {}),
    }
    method, url, body = requests[route]
    response = await client.request(method, url, json=body)
    assert response.status_code == 403, response.text
    compute.post.assert_not_called()
    assert store.read() == before
