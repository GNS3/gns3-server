"""
MCP tool parameter consistency tests.

Verifies that the parameters defined in each MCP tool function (in __init__.py)
match what the corresponding handler function actually reads via params.get().

This catches issues like:
  - A tool parameter is defined but never passed to the handler
  - A handler reads a param that was never defined or passed
"""
import ast
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MCP_DIR = REPO_ROOT / "gns3server" / "agent" / "mcp"
# Node/link handlers live in the shared REST client layer, not MCP_DIR.
API_HANDLERS_FILE = "gns3server/agent/gns3_copilot/gns3_client/api_handlers.py"
TOOL_FILE = MCP_DIR / "__init__.py"

HANDLER_FILES = {
    "list_projects_handler": "projects.py",
    "get_project_handler": "projects.py",
    "create_project_handler": "projects.py",
    "delete_project_handler": "projects.py",
    "open_project_handler": "projects.py",
    "close_project_handler": "projects.py",
    "get_project_stats_handler": "projects.py",
    "update_project_handler": "projects.py",
    "duplicate_project_handler": "projects.py",
    "get_project_readme_handler": "projects.py",
    "update_project_readme_handler": "projects.py",
    "lock_project_handler": "projects.py",
    "unlock_project_handler": "projects.py",
    "get_locked_project_handler": "projects.py",
    "get_nodes_handler": API_HANDLERS_FILE,
    "get_node_handler": API_HANDLERS_FILE,
    "start_node_handler": API_HANDLERS_FILE,
    "stop_node_handler": API_HANDLERS_FILE,
    "suspend_node_handler": API_HANDLERS_FILE,
    "create_node_handler": API_HANDLERS_FILE,
    "delete_node_handler": API_HANDLERS_FILE,
    "update_node_handler": API_HANDLERS_FILE,
    "get_node_console_info_handler": API_HANDLERS_FILE,
    "list_node_files_handler": API_HANDLERS_FILE,
    "get_node_file_handler": API_HANDLERS_FILE,
    "write_node_file_handler": API_HANDLERS_FILE,
    "delete_node_file_handler": API_HANDLERS_FILE,
    "start_all_nodes_handler": API_HANDLERS_FILE,
    "stop_all_nodes_handler": API_HANDLERS_FILE,
    "suspend_all_nodes_handler": API_HANDLERS_FILE,
    "duplicate_node_handler": API_HANDLERS_FILE,
    "isolate_node_handler": API_HANDLERS_FILE,
    "unisolate_node_handler": API_HANDLERS_FILE,
    "get_node_links_handler": API_HANDLERS_FILE,
    "available_filters_handler": API_HANDLERS_FILE,
    "get_links_handler": API_HANDLERS_FILE,
    "get_link_handler": API_HANDLERS_FILE,
    "create_link_handler": API_HANDLERS_FILE,
    "delete_link_handler": API_HANDLERS_FILE,
    "update_link_handler": API_HANDLERS_FILE,
    "reset_link_handler": API_HANDLERS_FILE,
    "start_capture_handler": API_HANDLERS_FILE,
    "stop_capture_handler": API_HANDLERS_FILE,
    "download_capture_file_handler": API_HANDLERS_FILE,
    "link_marker_handler": API_HANDLERS_FILE,
    "marker_definition_handler": API_HANDLERS_FILE,
    "list_templates_handler": "templates.py",
    "get_template_handler": "templates.py",
    "create_template_handler": "templates.py",
    "update_template_handler": "templates.py",
    "delete_template_handler": "templates.py",
    "list_computes_handler": "computes.py",
    "get_compute_handler": "computes.py",
    "get_compute_images_handler": "computes.py",
    "get_snapshots_handler": "snapshots.py",
    "create_snapshot_handler": "snapshots.py",
    "delete_snapshot_handler": "snapshots.py",
    "restore_snapshot_handler": "snapshots.py",
    "get_drawings_handler": "drawings.py",
    "create_drawing_handler": "drawings.py",
    "get_drawing_handler": "drawings.py",
    "update_drawing_handler": "drawings.py",
    "delete_drawing_handler": "drawings.py",
    "get_symbols_handler": "symbols.py",
    "get_symbol_handler": "symbols.py",
    "get_symbol_dimensions_handler": "symbols.py",
    "get_default_symbols_handler": "symbols.py",
    "upload_symbol_handler": "symbols.py",
    "delete_symbol_handler": "symbols.py",
    "get_appliances_handler": "appliances.py",
    "get_appliance_handler": "appliances.py",
    "install_appliance_handler": "appliances.py",
    "get_version_handler": "server.py",
    "get_statistics_handler": "server.py",
    "get_images_handler": "images.py",
    "get_image_handler": "images.py",
    "delete_image_handler": "images.py",
    "prune_images_handler": "images.py",
    "install_images_handler": "images.py",
    "device_config_send_handler": "device_config.py",
    "device_show_run_handler": "device_config.py",
    "vpcs_config_set_handler": "device_config.py",
}


def _get_handler_params(handler_name):
    """Parse handler file and extract all params.get('xxx') calls."""
    filename = HANDLER_FILES.get(handler_name)
    if not filename:
        return None
    filepath = (MCP_DIR if not filename.startswith('gns3server/') else REPO_ROOT) / filename
    if not filepath.exists():
        return None

    tree = ast.parse(filepath.read_text())

    params = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != handler_name:
            continue
        # A handler that forwards params.items() generically (e.g. building the
        # request body from all params) accepts any key — return a wildcard and
        # let the caller skip static consistency checks for it.
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "items"
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id in ("params", "params_data")):
                return {"*"}
        # Found the handler function, search for params.get("xxx")
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            if not hasattr(sub.func, "attr") or sub.func.attr != "get":
                continue
            # params.get("xxx") or params_data.get("xxx")
            func_obj = sub.func
            if (hasattr(func_obj.value, "id") and func_obj.value.id in ("params", "params_data", "link_data", "node_data")) or \
               (hasattr(func_obj.value, "attr") and func_obj.value.attr == "get"):
                if sub.args and isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str):
                    params.add(sub.args[0].value)
    return params


def test_handler_params_all_readable():
    """Every handler registered in __init__.py should have a corresponding file."""
    # Extract all handler names from __init__.py by looking for dispatch calls
    tree = ast.parse(TOOL_FILE.read_text())
    handlers_found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        handler_name, _ = _dispatch_args(node)
        if handler_name:
            handlers_found.add(handler_name)

    unknown = [h for h in handlers_found if h not in HANDLER_FILES]
    assert not unknown, f"Handlers not mapped in HANDLER_FILES: {unknown}"


def _dict_literal_keys(d):
    """String keys of an ast.Dict literal (non-constant keys like **spread are skipped)."""
    keys = set()
    for k in d.keys:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            keys.add(k.value)
    return keys


def _initial_params_keys(fn_node):
    """Keys of the initial 'params = {...}' dict literal inside a tool function, or None.

    Conditional additions (params["k"] = v) after the literal are not included.
    """
    for stmt in ast.walk(fn_node):
        if isinstance(stmt, ast.Assign):
            if (len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)
                    and stmt.targets[0].id == "params" and isinstance(stmt.value, ast.Dict)):
                return _dict_literal_keys(stmt.value)
    return None


def _dispatch_args(node):
    """Extract (handler_name, payload_arg) from a handler dispatch call.

    Matches both forms used by tools:
      - _run_handler_sync(handler, payload)
      - asyncio.to_thread(_run_handler_sync, handler, payload)
    Returns (None, None) if the call is neither.
    """
    if isinstance(node.func, ast.Name) and node.func.id == "_run_handler_sync":
        args = node.args
    elif (isinstance(node.func, ast.Attribute) and node.func.attr == "to_thread"
            and node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == "_run_handler_sync"):
        args = node.args[1:]
    else:
        return None, None
    if len(args) < 2 or not isinstance(args[0], ast.Name):
        return None, None
    return args[0].id, args[1]


def test_tool_handler_param_consistency():
    """For each tool, the params passed to the handler should match what the handler reads."""
    tree = ast.parse(TOOL_FILE.read_text())

    # Group dispatch calls by (tool, handler): a tool may dispatch the same
    # handler from multiple branches (e.g. node_create single/batch modes),
    # each passing only its branch's keys — the union covers all of them.
    groups = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        handler_name, second_arg = _dispatch_args(node)
        if not handler_name:
            continue

        # Find the tool function name (enclosing function)
        tool_name = None
        for parent in ast.walk(tree):
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(parent):
                    if child is node:
                        tool_name = parent.name
                        break
        if not tool_name:
            continue

        exact = False
        if isinstance(second_arg, ast.Dict):
            passed_keys = _dict_literal_keys(second_arg)
            exact = True
        elif isinstance(second_arg, ast.Name) and second_arg.id == "params":
            # Tool builds 'params' as a variable — resolve its initial dict literal.
            fn = next((n for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == tool_name), None)
            passed_keys = _initial_params_keys(fn) if fn is not None else None
        else:
            passed_keys = None
        if not passed_keys:
            continue

        group = groups.setdefault((tool_name, handler_name), {"passed": set(), "exact": False})
        group["passed"] |= passed_keys
        group["exact"] = group["exact"] or exact

    for (tool_name, handler_name), group in groups.items():
        handler_params = _get_handler_params(handler_name)
        if handler_params is None or "*" in handler_params:
            continue

        passed_keys = group["passed"]

        # Check: every passed key is read by the handler
        extra_passed = passed_keys - handler_params
        assert not extra_passed, (
            f"[{tool_name}] Params passed to handler '{handler_name}' but not read: {extra_passed}"
        )

        if not group["exact"]:
            # The initial literal underestimates what the tool passes (keys may be
            # added conditionally), so only the extra-passed direction is checked.
            continue

        # Check: every handler param is passed (except common/optional ones)
        missing = handler_params - passed_keys
        # Filter out well-known optional params that handlers check
        known_optional = {"fields", "template", "name", "version", "compute_id",
                         "x", "y", "link_type", "filters", "suspend", "link_style",
                         "show_filters_icon", "label"}
        truly_missing = missing - known_optional
        if truly_missing:
            pytest.fail(
                f"[{tool_name}] Handler '{handler_name}' reads params not passed: {truly_missing}"
            )
