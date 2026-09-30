#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: Yue Guobin
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

"""
Name locators for MCP tools.

LLM agents transcribe UUIDs unreliably (a 2-character slip invents an id
that never existed and is invisible to the eye), so MCP tool parameters
accept names wherever the server guarantees uniqueness: project names are
unique among live projects (the controller rejects duplicates) and node
names are unique within a project (auto-suffixed on collision). Links,
drawings, appliances and snapshots have no names and stay UUID-only.

Resolution happens in the single dispatch choke point (_run_handler_sync):
UUID-shaped values pass through untouched, names are resolved with one
list call, and a name that matches nothing fails fast with the known
names instead of a confusing downstream 404. As a backstop for residual
UUID typos, error replies carrying "<UUID> doesn't exist" are matched
against the ids visible in scope; a single candidate within edit
distance 2 earns a "Did you mean ..." hint.
"""

import re
from typing import Any, Callable

from .projects import list_projects_handler
from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_links_handler, get_nodes_handler

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_ID_IN_TEXT_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

# how many names to list when a locator matches nothing
_MAX_HINT_NAMES = 15


def looks_like_uuid(value: Any) -> bool:
    """
    Whether *value* is a UUID-shaped string (anything else is treated as a name).
    """

    return isinstance(value, str) and bool(_UUID_RE.match(value))


def resolve_locators(
    params: dict[str, Any], run: Callable[[Callable, dict], Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Rewrite name-shaped ``project_id``/``node_id`` values into UUIDs.

    :param params: tool params (top-level keys only; nested structures are
        left alone — link_create's node tuples require ids)
    :param run: callback running (handler, params) through the same context
    :returns: (resolved params, None) on success, (None, error dict) on failure
    """

    params = dict(params)

    project_ref = params.get("project_id")
    if project_ref is not None and not looks_like_uuid(project_ref):
        result = run(list_projects_handler, {})
        projects = _as_items(result, "projects")
        if projects is None:
            return None, {"error": f"Could not resolve project '{project_ref}': {_as_error(result)}"}
        match = _match_by_name(projects, project_ref)
        if match is None:
            return None, {"error": f"Project '{project_ref}' not found. Known projects: {_known_names(projects)}"}
        params["project_id"] = match["project_id"]

    node_ref = params.get("node_id")
    if node_ref is not None and not looks_like_uuid(node_ref) and params.get("project_id"):
        result = run(get_nodes_handler, {"project_id": params["project_id"]})
        nodes = _as_items(result, "nodes")
        if nodes is None:
            return None, {"error": f"Could not resolve node '{node_ref}': {_as_error(result)}"}
        match = _match_by_name(nodes, node_ref)
        if match is None:
            return None, {"error": f"Node '{node_ref}' not found. Known nodes: {_known_names(nodes)}"}
        params["node_id"] = match["node_id"]

    return params, None


def add_did_you_mean(
    result: Any, params: dict[str, Any], run: Callable[[Callable, dict], Any]
) -> Any:
    """
    Append a "Did you mean ...?" hint to an error reply that names a
    non-existent UUID, when exactly one in-scope id is within edit
    distance 2 of it (the signature of a transcription slip).
    """

    if not isinstance(result, dict):
        return result
    error = result.get("error")
    if not isinstance(error, str) or ("doesn't exist" not in error and "not found" not in error.lower()):
        return result
    bad_ids = set(_ID_IN_TEXT_RE.findall(error))
    if not bad_ids:
        return result

    candidates = _collect_candidates(params, run)
    if not candidates:
        return result

    hints = []
    for bad in bad_ids:
        close = [(cid, label) for cid, label in candidates if bad != cid and _edit_distance_at_most(bad.lower(), cid.lower(), 2)]
        if len(close) == 1:
            cid, label = close[0]
            hints.append(f"Did you mean {label} ({cid})?")
    if not hints:
        return result
    result = dict(result)
    result["error"] = error.rstrip() + " " + " ".join(hints)
    return result


def _as_items(result: Any, key: str) -> list | None:
    """
    Normalize a handler reply into a list of dicts (None = failure).
    """

    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        items = result.get(key)
        if isinstance(items, list):
            return items
    return None


def _as_error(result: Any) -> Any:
    return result.get("error", result) if isinstance(result, dict) else result


def _match_by_name(items: list, name: str) -> dict | None:
    """
    The unique item whose name equals *name* (exact first, then a unique
    case-insensitive match); None when absent or ambiguous.
    """

    exact = [item for item in items if item.get("name") == name]
    if len(exact) == 1:
        return exact[0]
    if not exact:
        folded = [item for item in items if isinstance(item.get("name"), str) and item["name"].lower() == name.lower()]
        if len(folded) == 1:
            return folded[0]
    return None


def _known_names(items: list) -> str:
    names = sorted(str(item.get("name", "?")) for item in items)
    if len(names) > _MAX_HINT_NAMES:
        names = [*names[:_MAX_HINT_NAMES], f"... ({len(names) - _MAX_HINT_NAMES} more)"]
    return ", ".join(names)


def _collect_candidates(params: dict[str, Any], run: Callable[[Callable, dict], Any]) -> list[tuple[str, str]]:
    """
    (id, label) pairs in scope for a hint: every project, plus the nodes
    and links of the project the call targeted. Best-effort — any failure
    just yields what was gathered so far.
    """

    candidates = []
    try:
        projects = _as_items(run(list_projects_handler, {}), "projects") or []
        candidates.extend((p["project_id"], f"project '{p.get('name', '?')}'") for p in projects if p.get("project_id"))
    except Exception:  # best-effort hint enrichment
        pass
    project_id = params.get("project_id")
    if looks_like_uuid(project_id):
        try:
            nodes = _as_items(run(get_nodes_handler, {"project_id": project_id}), "nodes") or []
            candidates.extend((n["node_id"], f"node '{n.get('name', '?')}'") for n in nodes if n.get("node_id"))
        except Exception:  # best-effort hint enrichment
            pass
        try:
            links = _as_items(run(get_links_handler, {"project_id": project_id}), "links") or []
            candidates.extend((link["link_id"], "link") for link in links if link.get("link_id"))
        except Exception:  # best-effort hint enrichment
            pass
    return candidates


def _edit_distance_at_most(a: str, b: str, cap: int) -> bool:
    """
    Levenshtein distance with an early bail above *cap* (ids are short;
    the cap keeps the DP band trivial).
    """

    if abs(len(a) - len(b)) > cap:
        return False
    if a == b:
        return True
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        best = i
        for j, char_b in enumerate(b, 1):
            substitution = previous[j - 1] + (char_a != char_b)
            value = min(previous[j] + 1, current[j - 1] + 1, substitution)
            current.append(value)
            best = min(best, value)
        if best > cap:
            return False
        previous = current
    return previous[-1] <= cap
