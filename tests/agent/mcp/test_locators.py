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

"""
Name locators: name->UUID resolution and the UUID-typo "Did you mean" hint.
"""

from gns3server.agent.mcp import locators
from gns3server.agent.mcp.locators import add_did_you_mean, looks_like_uuid, resolve_locators

PROJECT_ID = "d1ab2349-2e53-4e41-a9ae-b5ffcd912408"
NODE_ID = "b78a2630-2c9e-4b43-9397-c855c8053d1a"
NODE_ID_TYPO = "b78a2630-3b9e-4b43-9397-c855c8053d1a"  # 2c9e -> 3b9e (distance 2)


def _run_factory(projects=None, nodes=None):
    """A run() callback answering the two list handlers from canned data."""

    calls = []

    def run(handler, params):
        calls.append((handler, dict(params)))
        if handler is locators.list_projects_handler:
            if isinstance(projects, Exception):
                raise projects
            return {"projects": projects if projects is not None else []}
        if handler is locators.get_nodes_handler:
            if isinstance(nodes, Exception):
                raise nodes
            return nodes if nodes is not None else []
        raise AssertionError(f"unexpected handler {handler}")

    return run, calls


def test_looks_like_uuid():

    assert looks_like_uuid(PROJECT_ID) is True
    assert looks_like_uuid(PROJECT_ID.upper()) is True
    assert looks_like_uuid("FRRDocker-4") is False
    assert looks_like_uuid("") is False
    assert looks_like_uuid(None) is False
    assert looks_like_uuid(1234) is False


def test_uuid_params_pass_through_without_calls():
    """UUID-shaped values never trigger resolution lookups."""

    run, calls = _run_factory(projects=[{"project_id": PROJECT_ID, "name": "lab"}])
    params, error = resolve_locators({"project_id": PROJECT_ID, "node_id": NODE_ID}, run)
    assert error is None
    assert params == {"project_id": PROJECT_ID, "node_id": NODE_ID}
    assert calls == []


def test_project_name_resolved():
    """A name-shaped project_id becomes the project's UUID."""

    run, calls = _run_factory(projects=[{"project_id": "11111111-1111-1111-1111-111111111111", "name": "other"},
                                        {"project_id": PROJECT_ID, "name": "my-lab"}])
    params, error = resolve_locators({"project_id": "my-lab"}, run)
    assert error is None
    assert params["project_id"] == PROJECT_ID
    assert len(calls) == 1  # only the project list


def test_project_name_not_found_lists_known_names():

    run, _calls = _run_factory(projects=[{"project_id": PROJECT_ID, "name": "my-lab"}])
    params, error = resolve_locators({"project_id": "no-such-lab"}, run)
    assert params is None
    assert "not found" in error["error"]
    assert "my-lab" in error["error"]


def test_node_name_resolved_within_project():

    run, calls = _run_factory(projects=[{"project_id": PROJECT_ID, "name": "my-lab"}],
                              nodes=[{"node_id": NODE_ID, "name": "FRRDocker-4"}])
    params, error = resolve_locators({"project_id": "my-lab", "node_id": "FRRDocker-4"}, run)
    assert error is None
    assert params["project_id"] == PROJECT_ID
    assert params["node_id"] == NODE_ID
    # node lookup went to the already-resolved project
    assert calls[1] == (locators.get_nodes_handler, {"project_id": PROJECT_ID})


def test_node_name_case_insensitive_unique_match():

    run, _calls = _run_factory(nodes=[{"node_id": NODE_ID, "name": "FRRDocker-4"}])
    params, error = resolve_locators({"project_id": PROJECT_ID, "node_id": "frrdocker-4"}, run)
    assert error is None
    assert params["node_id"] == NODE_ID


def test_node_name_not_found_lists_known_nodes():

    run, _calls = _run_factory(nodes=[{"node_id": NODE_ID, "name": "FRRDocker-4"}])
    params, error = resolve_locators({"project_id": PROJECT_ID, "node_id": "vpcs-1"}, run)
    assert params is None
    assert "FRRDocker-4" in error["error"]


def test_handler_failure_during_resolution_is_reported():

    run, _calls = _run_factory(nodes={"error": "boom"})
    params, error = resolve_locators({"project_id": PROJECT_ID, "node_id": "FRRDocker-4"}, run)
    assert params is None
    assert "Could not resolve node" in error["error"]


def test_did_you_mean_appended_for_transcription_slip():
    """The 2c9e -> 3b9e class of typo earns exactly one hint."""

    run, _calls = _run_factory(projects=[{"project_id": PROJECT_ID, "name": "my-lab"}],
                               nodes=[{"node_id": NODE_ID, "name": "FRRDocker-4"}])
    result = add_did_you_mean(
        {"error": f"Node ID {NODE_ID_TYPO} doesn't exist"}, {"project_id": PROJECT_ID}, run
    )
    assert f"Did you mean node 'FRRDocker-4' ({NODE_ID})" in result["error"]
    # original message preserved
    assert NODE_ID_TYPO in result["error"]


def test_no_hint_when_too_far_or_ambiguous():

    far = "b78a2630-9999-4b43-9397-c855c8053d1a"  # distance 3
    run, _calls = _run_factory(nodes=[{"node_id": NODE_ID, "name": "n1"}])
    result = add_did_you_mean({"error": f"Node ID {far} doesn't exist"}, {"project_id": PROJECT_ID}, run)
    assert "Did you mean" not in result["error"]

    two = [NODE_ID, "b78a2630-2b9e-4b43-9397-c855c8053d1a"]  # both within distance 2 of the typo
    run2, _calls2 = _run_factory(nodes=[{"node_id": i, "name": f"n{i}"} for i in two])
    result2 = add_did_you_mean(
        {"error": f"Node ID {NODE_ID_TYPO} doesn't exist"}, {"project_id": PROJECT_ID}, run2
    )
    assert "Did you mean" not in result2["error"]


def test_non_error_results_untouched():

    run, _calls = _run_factory(nodes=[{"node_id": NODE_ID, "name": "n1"}])
    payload = [{"node_id": NODE_ID}]
    assert add_did_you_mean(payload, {"project_id": PROJECT_ID}, run) is payload
    assert add_did_you_mean({"filters": {}}, {"project_id": PROJECT_ID}, run) == {"filters": {}}
    # errors without an id carry nothing to hint against
    result = add_did_you_mean({"error": "Node not found: no id here"}, {"project_id": PROJECT_ID}, run)
    assert result == {"error": "Node not found: no id here"}


def test_edit_distance_at_most():

    assert locators._edit_distance_at_most("abcd", "abcd", 2)
    assert locators._edit_distance_at_most("abcd", "abce", 2)
    assert locators._edit_distance_at_most("2c9e", "3b9e", 2)
    assert not locators._edit_distance_at_most("abcd", "dcba", 2)
    assert not locators._edit_distance_at_most("abc", "abcdef", 2)
