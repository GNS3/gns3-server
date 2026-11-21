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
#

"""
Node quota usage accounting and enforcement.

Quotas are resolved per user (user columns over group defaults, see
gns3server.db.user_quota_state) but accounted per project owner: every
node counts against the quota of the user owning the project
(``project.created_by``), including nodes created or started by someone
else in a project shared with them. A project without an owner can only
be used by superadmins, who are never limited.

Only the node types that consume resources are counted (a QEMU, Docker,
Dynamips, IOU, VPCS, VirtualBox or VMware node); always-running node
types (Ethernet switch, hub, cloud, NAT) are free.
Usage covers every project known to the controller, opened or closed:
opened projects are counted from memory, closed projects from their
.gns3 file (cached by file mtime). Running nodes only exist in opened
projects — closing a project stops its nodes.

The checks count in-flight creations/starts on top of the current usage:
the node registration (or the compute accepting the start) happens after
the check, so without the in-flight part a burst of concurrent requests
(start all, a pool of clients) would each pass the check before any of
them is accounted.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from ..db.user_quota_state import UserQuotaState
from .controller_error import ControllerError, ControllerForbiddenError

if TYPE_CHECKING:
    from .project import Project

log = logging.getLogger(__name__)

# The node types that count against a quota. Keep in sync with the
# complement of Node.is_always_running().
QUOTA_COUNTED_TYPES = frozenset({"qemu", "docker", "dynamips", "vpcs", "vmware", "virtualbox", "iou"})

# In-flight reservations, keyed by owner username. The plain dict/Counter
# operations here never await, so they are atomic on the event loop.
_inflight_creates: Counter = Counter()
_inflight_starts: Counter = Counter()

# Cache for the closed-project node counts: topology file path ->
# (mtime, counted node count). Invalidated by mtime.
_closed_counts: Dict[str, Tuple[float, int]] = {}


def _closed_project_count(project: Project) -> int:
    """
    Count the quota-relevant nodes of a closed project from its .gns3
    file, cached by file mtime. An unreadable topology counts as zero —
    it must not block the checks.
    """

    try:
        path = project._topology_file()
    except ControllerError:
        return 0

    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return 0

    cached = _closed_counts.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    count = 0
    try:
        with open(path, encoding="utf-8") as f:
            topology = json.load(f)
        for node in topology.get("topology", {}).get("nodes", []):
            if node.get("node_type") in QUOTA_COUNTED_TYPES:
                count += 1
    except (OSError, ValueError) as e:
        log.warning(f"Could not read topology '{path}' for the quota usage: {e}")
        return 0

    _closed_counts[path] = (mtime, count)
    return count


def count_usage(username: str) -> Tuple[int, int]:
    """
    Return (total, running) quota-relevant node counts over every project
    owned by the user, opened or closed.
    """

    from . import Controller  # local import: the controller package imports this module

    total = 0
    running = 0
    for project in Controller.instance().projects.values():
        if project.created_by != username:
            continue
        if project.status == "opened":
            for node in project._nodes.values():
                if node.node_type not in QUOTA_COUNTED_TYPES:
                    continue
                total += 1
                if node.status == "started":
                    running += 1
        else:
            total += _closed_project_count(project)
    return total, running


class QuotaReservation:
    """
    A reserved slice of a user quota. Released exactly once when the
    checked operation completes (or fails): the release is idempotent so
    an exception path cannot double-release.
    """

    def __init__(self, counter: Counter, username: Optional[str], count: int):

        self._counter = counter
        self._username = username
        self._count = count

    def release(self) -> None:

        if self._count <= 0 or not self._username:
            self._count = 0
            return
        self._counter[self._username] -= self._count
        if self._counter[self._username] <= 0:
            del self._counter[self._username]
        self._count = 0


def _reserve(
    counter: Counter, username: Optional[str], count: int, limit: Optional[int], usage: int, message: str
) -> QuotaReservation:
    """
    Check `usage + in-flight + count <= limit` and reserve `count` slots.
    Runs entirely on the event loop (no await), so the check and the
    reservation are atomic with respect to concurrent requests.
    """

    if not username or limit is None:
        return QuotaReservation(counter, username, 0)
    current = usage + counter[username]
    if current + count > limit:
        raise ControllerForbiddenError(message.format(current=current, limit=limit))
    counter[username] += count
    return QuotaReservation(counter, username, count)


def reserve_create(project: Project, count: int = 1) -> QuotaReservation:
    """
    Reserve the creation of `count` nodes against the project owner's
    node quota. Raises ControllerForbiddenError past the limit.
    """

    username = project.created_by
    limits = UserQuotaState.instance().get(username)
    if limits is None or limits.max_nodes is None:
        return QuotaReservation(_inflight_creates, username, 0)
    return _reserve(
        _inflight_creates,
        username,
        count,
        limits.max_nodes,
        count_usage(username)[0],
        f"Cannot create node in project '{project.name}': user '{username}' reached "
        f"the maximum number of nodes ({{limit}})",
    )


def reserve_start(project: Project) -> QuotaReservation:
    """
    Reserve the start of one node against the project owner's running
    node quota. Raises ControllerForbiddenError past the limit.
    """

    username = project.created_by
    limits = UserQuotaState.instance().get(username)
    if limits is None or limits.max_running_nodes is None:
        return QuotaReservation(_inflight_starts, username, 0)
    return _reserve(
        _inflight_starts,
        username,
        1,
        limits.max_running_nodes,
        count_usage(username)[1],
        f"Cannot start node in project '{project.name}': user '{username}' reached "
        f"the maximum number of running nodes ({{limit}})",
    )


def reserve_import(username: Optional[str], node_count: int) -> QuotaReservation:
    """
    Reserve the nodes of a project being imported / duplicated /
    distributed to the user against its node quota. No reservation when
    the future owner is unknown (imports without a user keep their
    original owner and are not quota-checked).
    """

    limits = UserQuotaState.instance().get(username)
    if not username or limits is None or limits.max_nodes is None:
        return QuotaReservation(_inflight_creates, username, 0)
    return _reserve(
        _inflight_creates,
        username,
        node_count,
        limits.max_nodes,
        count_usage(username)[0],
        f"Cannot import a project with {{limit}} node(s) or less for user '{username}': "
        f"the quota is already used ({{current}} nodes)",
    )


def reset_quota_usage_state() -> None:
    """
    Clear the module-level caches and counters (test isolation).
    """

    _inflight_creates.clear()
    _inflight_starts.clear()
    _closed_counts.clear()
