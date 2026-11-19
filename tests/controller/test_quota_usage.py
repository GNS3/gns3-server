#
# Copyright (C) 2026 GNS3 Technologies Inc.
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

import json
import uuid
import zipfile
from unittest.mock import MagicMock

import pytest

from gns3server.controller.compute import ComputeError
from gns3server.controller.controller_error import ControllerForbiddenError
from gns3server.controller.import_project import import_project
from gns3server.controller.quota_usage import (
    QUOTA_COUNTED_TYPES,
    count_usage,
    reserve_import,
    reset_quota_usage_state,
)
from gns3server.db.user_quota_state import QuotaLimits, UserQuotaState, _aggregate, _normalize
from tests.utils import AsyncioMagicMock

pytestmark = pytest.mark.asyncio


@pytest.fixture
def quota_state():

    UserQuotaState._reset()
    reset_quota_usage_state()
    state = UserQuotaState.instance()
    yield state
    UserQuotaState._reset()
    reset_quota_usage_state()


@pytest.fixture
def quota_state_sync(quota_state):
    """
    Quota state for the synchronous tests, which take no controller
    fixture: drop the Controller singleton another test may have left
    behind, so count_usage starts from a clean project list.
    """

    from gns3server.controller import Controller

    saved = getattr(Controller, "_instance", None)
    Controller._instance = None
    yield quota_state
    Controller._instance = saved


@pytest.fixture
def compute():

    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)
    return compute


async def test_counted_types_match_always_running_complement():
    """
    The quota-counted types are exactly the complement of
    Node.is_always_running() over the builtin node types.
    """

    from gns3server.controller.node import Node
    from gns3server.controller.node_types import BUILTIN_NODE_TYPES

    for node_type in BUILTIN_NODE_TYPES:
        node = Node.__new__(Node)
        node._node_type = node_type
        if node.is_always_running():
            assert node_type not in QUOTA_COUNTED_TYPES, node_type
        else:
            assert node_type in QUOTA_COUNTED_TYPES, node_type


async def test_normalize():

    assert _normalize(None) is None
    assert _normalize(-1) is None
    assert _normalize(-100) is None
    assert _normalize(0) == 0
    assert _normalize(42) == 42


async def test_aggregate():

    assert _aggregate([]) is None  # no group: unlimited
    assert _aggregate([None]) is None  # unlimited group default
    assert _aggregate([None, 100]) is None  # one unlimited group wins
    assert _aggregate([-1, 100]) is None  # explicit -1 unlimited as well
    assert _aggregate([10, 100]) == 100  # widest numeric default wins
    assert _aggregate([10]) == 10


async def test_add_node_blocked_at_limit(controller, project, compute, quota_state):

    quota_state._limits = {"alice": QuotaLimits(max_nodes=2, max_running_nodes=None)}
    project.created_by = "alice"

    await project.add_node(compute, "n1", None, node_type="vpcs")
    await project.add_node(compute, "n2", None, node_type="vpcs")
    with pytest.raises(ControllerForbiddenError, match="maximum number of nodes"):
        await project.add_node(compute, "n3", None, node_type="vpcs")
    assert len(project.nodes) == 2


async def test_add_node_unlimited_without_quota(controller, project, compute, quota_state):

    quota_state._limits = {}  # no entry for this user: unlimited
    project.created_by = "bob"

    for i in range(5):
        await project.add_node(compute, f"n{i}", None, node_type="vpcs")
    assert len(project.nodes) == 5


async def test_always_running_nodes_are_free(controller, project, compute, quota_state):

    quota_state._limits = {"alice": QuotaLimits(max_nodes=1, max_running_nodes=None)}
    project.created_by = "alice"

    # Ethernet switches/hubs/clouds/nats never count against the quota
    for i in range(3):
        await project.add_node(compute, f"sw{i}", None, node_type="ethernet_switch")

    # the first resource node fits the quota, a second one is refused
    await project.add_node(compute, "n1", None, node_type="vpcs")
    with pytest.raises(ControllerForbiddenError):
        await project.add_node(compute, "n2", None, node_type="vpcs")


async def test_free_node_types_are_allowed_at_the_limit(controller, project, compute, quota_state):
    """
    Free node types never take a quota slot, so a user who already used
    every counted slot can still create them. The check is about the
    counted types only: count_usage() does not count free nodes either.
    """

    quota_state._limits = {"alice": QuotaLimits(max_nodes=1, max_running_nodes=None)}
    project.created_by = "alice"

    # fill the only quota slot
    await project.add_node(compute, "n1", None, node_type="vpcs")

    # the free types stay available while the quota is exhausted
    await project.add_node(compute, "sw1", None, node_type="ethernet_switch")
    await project.add_node(compute, "hub1", None, node_type="ethernet_hub")
    await project.add_node(compute, "cloud1", None, node_type="cloud")
    await project.add_node(compute, "nat1", None, node_type="nat")
    assert len(project.nodes) == 5

    # a second counted node is still refused
    with pytest.raises(ControllerForbiddenError, match="maximum number of nodes"):
        await project.add_node(compute, "n2", None, node_type="vpcs")


async def test_quota_spans_projects_and_closed_projects(controller, project, compute, quota_state):
    """
    The node quota covers every project owned by the user, including the
    projects that are closed (counted from their .gns3 file).
    """

    quota_state._limits = {"alice": QuotaLimits(max_nodes=3, max_running_nodes=None)}
    project.created_by = "alice"

    for i in range(3):
        await project.add_node(compute, f"n{i}", None, node_type="vpcs")

    # simulate a closed project: the nodes are gone from memory, the
    # topology file on disk carries them
    project._status = "closed"
    project._nodes = {}
    assert count_usage("alice") == (3, 0)

    other = await controller.add_project(name="Second")
    other.created_by = "alice"
    with pytest.raises(ControllerForbiddenError):
        await other.add_node(compute, "n4", None, node_type="vpcs")


async def test_project_open_loading_bypasses_quota(controller, project, compute, quota_state):
    """
    Opening a project replays its existing nodes through add_node: they
    are not new creations and must not be quota-checked.
    """

    quota_state._limits = {"alice": QuotaLimits(max_nodes=1, max_running_nodes=None)}
    project.created_by = "alice"

    project._loading = True
    try:
        for i in range(3):
            await project.add_node(compute, f"n{i}", None, node_type="vpcs", dump=False)
    finally:
        project._loading = False
    assert len(project.nodes) == 3


async def test_start_blocked_at_running_limit(controller, project, compute, quota_state):

    quota_state._limits = {"alice": QuotaLimits(max_nodes=None, max_running_nodes=1)}
    project.created_by = "alice"

    n1 = await project.add_node(compute, "n1", None, node_type="vpcs")
    n2 = await project.add_node(compute, "n2", None, node_type="vpcs")

    await n1.start()
    assert n1.status == "started"
    with pytest.raises(ControllerForbiddenError, match="maximum number of running nodes"):
        await n2.start()


async def test_start_already_started_is_idempotent(controller, project, compute, quota_state):

    quota_state._limits = {"alice": QuotaLimits(max_nodes=None, max_running_nodes=1)}
    project.created_by = "alice"

    n1 = await project.add_node(compute, "n1", None, node_type="vpcs")
    await n1.start()
    # starting it again takes no additional slot and must not be refused
    await n1.start()


async def test_reload_blocked_when_stopped(controller, project, compute, quota_state):

    quota_state._limits = {"alice": QuotaLimits(max_nodes=None, max_running_nodes=1)}
    project.created_by = "alice"

    n1 = await project.add_node(compute, "n1", None, node_type="vpcs")
    n2 = await project.add_node(compute, "n2", None, node_type="vpcs")

    await n1.start()
    with pytest.raises(ControllerForbiddenError):
        await n2.reload()


async def test_reserve_import(quota_state_sync):

    quota_state_sync._limits = {"alice": QuotaLimits(max_nodes=5, max_running_nodes=None)}

    reservation = reserve_import("alice", 3)
    try:
        # while the import is in flight, a concurrent check sees the slots taken
        with pytest.raises(ControllerForbiddenError):
            reserve_import("alice", 3)
    finally:
        reservation.release()

    # released: the full budget is available again
    reserve_import("alice", 5).release()

    with pytest.raises(ControllerForbiddenError):
        reserve_import("alice", 6)

    # no future owner: not checked at all
    reserve_import(None, 1000).release()


async def test_inflight_reservation_released_on_release(quota_state_sync):

    quota_state_sync._limits = {"alice": QuotaLimits(max_nodes=5, max_running_nodes=None)}

    reservation = reserve_import("alice", 5)
    with pytest.raises(ControllerForbiddenError):
        reserve_import("alice", 1)
    reservation.release()
    reservation.release()  # idempotent
    reserve_import("alice", 5).release()


async def test_failed_create_releases_reservation(controller, project, quota_state):

    quota_state._limits = {"alice": QuotaLimits(max_nodes=1, max_running_nodes=None)}
    project.created_by = "alice"

    compute = MagicMock()
    compute.id = "local"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(side_effect=ComputeError("boom"))

    with pytest.raises(ComputeError):
        await project.add_node(compute, "n1", None, node_type="vpcs")

    # the retry first re-posts /projects (the first attempt died before
    # registering the compute), then posts the node creation
    compute.post = AsyncioMagicMock(return_value=response)

    # the failed creation must have released its reservation: the retry
    # fits the quota again and succeeds
    node = await project.add_node(compute, "n1-retry", None, node_type="vpcs")
    assert node.name == "n1-retry"


async def test_count_usage_running(controller, project, compute, quota_state):

    quota_state._limits = {"alice": QuotaLimits(max_nodes=10, max_running_nodes=5)}
    project.created_by = "alice"

    n1 = await project.add_node(compute, "n1", None, node_type="vpcs")
    await project.add_node(compute, "sw", None, node_type="ethernet_switch")
    assert count_usage("alice") == (1, 0)  # the switch is not counted
    await n1.start()
    assert count_usage("alice") == (1, 1)
    assert count_usage("nobody") == (0, 0)


async def test_import_project_quota_denied(controller, quota_state, tmpdir):
    """
    Importing a project for a user past its node quota is refused before
    anything is extracted; the always-running node types in the archive
    are free.
    """

    quota_state._limits = {"alice": QuotaLimits(max_nodes=2, max_running_nodes=None)}

    def build_zip(node_types):
        topology = {
            "project_id": str(uuid.uuid4()),
            "name": "test",
            "revision": 6,
            "type": "topology",
            "topology": {
                "computes": [],
                "drawings": [],
                "links": [],
                "nodes": [
                    {
                        "node_id": str(uuid.uuid4()),
                        "node_type": t,
                        "compute_id": "local",
                        "name": f"n{i}",
                        "properties": {},
                        "x": 0,
                        "y": 0,
                        "z": 0,
                    }
                    for i, t in enumerate(node_types)
                ],
            },
            "version": "2.0.0",
        }
        topology_file = tmpdir / "project.gns3"
        with open(str(topology_file), "w+") as f:
            json.dump(topology, f)
        zip_path = str(tmpdir / "project.zip")
        with zipfile.ZipFile(zip_path, "w") as myzip:
            myzip.write(str(topology_file), "project.gns3")
        return zip_path

    # 2 resource nodes + 1 free switch: fits the quota of 2
    with open(build_zip(["vpcs", "vpcs", "ethernet_switch"]), "rb") as f:
        project = await import_project(controller, str(uuid.uuid4()), f, user="alice")
    assert project.created_by == "alice"

    # a second import of the same archive no longer fits
    with open(build_zip(["vpcs", "vpcs", "ethernet_switch"]), "rb") as f:
        with pytest.raises(ControllerForbiddenError, match="import"):
            await import_project(controller, str(uuid.uuid4()), f, user="alice")

    # imports without a future owner are not checked (system paths)
    with open(build_zip(["vpcs"] * 10), "rb") as f:
        await import_project(controller, str(uuid.uuid4()), f)
