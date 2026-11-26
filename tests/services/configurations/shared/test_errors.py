"""The public configuration error codes live in one registry and cannot drift."""

import re

import pytest

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


def test_boot_media_codes_are_registered():
    codes = {
        "startup_media_profile_unknown",
        "boot_media_tool_missing",
        "boot_media_build_failed",
        "boot_media_too_large",
    }
    assert codes <= CONTROLLER_ERRORS <= PUBLIC_ERRORS and codes <= JOB_FAILURES
    assert codes <= set(STARTUP_PREPARE_ERRORS)
