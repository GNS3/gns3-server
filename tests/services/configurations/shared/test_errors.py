"""The public configuration error codes live in one registry and cannot drift."""

import ast
import re
from pathlib import Path

import pytest

from gns3server.services.configurations.shared import errors
from gns3server.services.configurations.shared.errors import (
    CAPTURE_FAILURES,
    CONTROLLER_ERRORS,
    EXPORT_ERRORS,
    JOB_FAILURES,
    PUBLIC_ERRORS,
    STARTUP_PREPARE_ERRORS,
    WORKER_ERRORS,
    error_status,
)

ROOT = Path(errors.__file__).resolve().parents[3]


def test_registry_layers_are_nested():
    assert WORKER_ERRORS <= CAPTURE_FAILURES <= EXPORT_ERRORS <= JOB_FAILURES <= PUBLIC_ERRORS
    assert CONTROLLER_ERRORS <= PUBLIC_ERRORS


@pytest.mark.parametrize("code", sorted(PUBLIC_ERRORS))
def test_every_public_code_maps_to_a_client_error_status(code):
    assert re.fullmatch(r"[a-z][a-z0-9_]*", code)
    assert 400 <= error_status(code) < 500


def test_prepare_messages_only_describe_registered_codes():
    assert set(STARTUP_PREPARE_ERRORS) <= PUBLIC_ERRORS
    assert all(STARTUP_PREPARE_ERRORS.values())


def unregistered_codes(paths, allowed=frozenset()):
    """Literal codes passed to ``ConfigurationError(...)`` that clients could not be told about."""
    found = set()
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "ConfigurationError"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value not in PUBLIC_ERRORS | allowed
            ):
                found.add(node.args[0].value)
    return found


def test_literal_error_codes_raised_by_the_controller_and_boot_media_are_registered():
    # Otherwise failure()/safe_error() would silently degrade the code to a generic one.
    generic = {"configuration_operation_failed", "configuration_export_failed", "configuration_compute_unavailable"}
    controller = [ROOT / "controller/configurations.py"]
    assert not unregistered_codes(controller, generic)
    assert not unregistered_codes((ROOT / "services/configurations/boot_media").rglob("*.py"))


def test_failure_context_phases_used_by_the_console_are_all_declared():
    """Every phase passed to session.mark() must survive failure_context()."""
    from gns3server.services.configurations.shared.failure_context import FAILURE_PHASES, failure_context

    used = set()
    for path in (ROOT / "services/configurations/console").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "attr", None) == "mark"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                used.add(node.args[0].value)
    assert used and used <= FAILURE_PHASES
    assert all(failure_context({"phase": phase}) == {"phase": phase} for phase in FAILURE_PHASES)


def test_boot_media_codes_are_registered():
    codes = {
        "startup_media_profile_unknown",
        "boot_media_tool_missing",
        "boot_media_build_failed",
        "boot_media_too_large",
    }
    assert codes <= CONTROLLER_ERRORS <= PUBLIC_ERRORS and codes <= JOB_FAILURES
    assert codes <= set(STARTUP_PREPARE_ERRORS)
