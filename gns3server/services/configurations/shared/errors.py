"""Stable configuration failures shared by API, controller, compute and worker: the exceptions, the public error-code
registry and the HTTP status of each code."""

from .failure_context import failure_context


class ConfigurationError(ValueError):
    def __init__(self, code: str, *, previous_error: str | None = None, console_reusable: bool = False, context=None):
        self.code = code
        self.context = failure_context(context)
        self.previous_error = previous_error
        self.console_reusable = console_reusable
        super().__init__(code)


class CaptureFailure(Exception):
    def __init__(self, code, *, console_reusable=False):
        self.context = {}
        self.console_reusable = console_reusable
        super().__init__(code)


WORKER_ERRORS = frozenset(
    {
        "console_authentication_failed",
        "console_enable_secret_required",
        "console_not_ready",
        "console_unsafe_mode",
        "console_output_limit",
        "console_incomplete_output",
        "console_invalid_encoding",
        "console_driver_unavailable",
        "console_capture_failed",
        "device_version_unsupported",
        "configuration_apply_failed",
        "configuration_apply_timeout",
        "console_unavailable",
        "configuration_invalid_content",
        "configuration_apply_unsupported",
        "configuration_save_unsupported",
        "device_type_unsupported",
    }
)


CAPTURE_FAILURES = WORKER_ERRORS | {"configuration_capture_timeout", "runtime_changed_during_capture"}


AUTHENTICATION_FAILURES = frozenset({"console_authentication_failed", "console_enable_secret_required"})


# Only fixed reason codes cross the compute boundary; diagnostics can contain secrets.
EXPORT_ERRORS = CAPTURE_FAILURES | {
    "stop_required",
    "start_required",
    "source_unsupported",
    "device_type_required",
    "hypervisor_unavailable",
    "configuration_not_found",
    "configuration_not_saved",
    "configuration_frr_volume_required",
    "invalid_nvram",
    "native_extraction_failed",
    "configuration_read_failed",
    "configuration_mount_shadowed",
    "container_state_unavailable",
    "application_id_unavailable",
    "runtime_changed_during_capture",
    "unsafe_configuration_file",
    "unsafe_configuration_path",
    "configuration_too_large",
    "configuration_changed_during_capture",
    "configuration_unavailable",
    "no_declared_files",
    "invalid_declared_files",
    "invalid_configuration_output",
    "capture_capacity_exhausted",
    "console_busy",
    "console_recovery_required",
    "console_lease_unsupported",
    # Raised by the compute service, not the console worker: the replay was
    # accepted but the guest's own configuration does not contain the upload.
    "configuration_apply_unverified",
    "configuration_verification_unavailable",
}


# ---------------------------------------------------------------------------
# Single registry of every code that may be shown to API clients. Each
# boundary (controller job status, compute RPC, route handler, node start)
# filters through one of these sets; tests/services/configurations/
# shared/test_errors.py keeps them consistent.
# ---------------------------------------------------------------------------

# Native boot media (services/configurations/boot_media): reported by a compute, a job and a wipe.
BOOT_MEDIA_ERRORS = frozenset(
    {
        "startup_media_profile_unknown",
        "boot_media_tool_missing",
        "boot_media_build_failed",
        "boot_media_too_large",
        "configuration_factory_reset_failed",
        "configuration_topology_unsupported",
    }
)

# Codes the controller accepts from compute RPC.
CONTROLLER_ERRORS = BOOT_MEDIA_ERRORS | {
    "configuration_image_required",
    "configuration_image_changed",
    "configuration_profile_mismatch",
    "duplicate_configuration_set_names",
    "configuration_set_limit_reached",
    "configuration_outcome_unknown",
    "configuration_not_savable",
    "configuration_frr_volume_required",
    "startup_configurations_changed",
    "configuration_compute_unavailable",
    "configuration_node_not_found",
    "node_locked",
    "project_closed",
    "configuration_operation_in_progress",
    "stop_required",
    "unsafe_configuration_path",
    "unsafe_configuration_file",
    "configuration_invalid_content",
    "invalid_startup_runtime",
    "application_id_unavailable",
    "hypervisor_unavailable",
    "container_state_unavailable",
    "configuration_mount_shadowed",
    "invalid_declared_files",
}

# Extra codes a capture/apply job may report (on top of EXPORT_ERRORS).
JOB_ONLY_ERRORS = BOOT_MEDIA_ERRORS | {
    "configuration_set_not_found",
    "startup_configurations_changed",
    "configuration_identity_mismatch",
    "configuration_apply_failed",
    "configuration_apply_unsupported",
    "configuration_apply_unverified",
    "configuration_verification_unavailable",
    "configuration_invalid_content",
    "configuration_login_required",
    "configuration_media_slot_unavailable",
    "configuration_profile_mismatch",
}
JOB_FAILURES = EXPORT_ERRORS | JOB_ONLY_ERRORS

# Reasons a wipe reports per node, from the compute or the controller's own checks.
WIPE_ERRORS = frozenset(
    {
        "stop_required",
        "configuration_wipe_unsupported",
        "configuration_extra_storage",
        "configuration_image_required",
        "configuration_image_changed",
        "configuration_mount_shadowed",
        "configuration_outcome_unknown",
        "configuration_operation_failed",
        "container_state_unavailable",
        "application_id_unavailable",
        "invalid_startup_runtime",
        "unsafe_configuration_path",
        "unsafe_configuration_file",
    }
)

ARCHIVE_ERRORS = frozenset({"invalid_configuration_archive", "configuration_archive_too_large"})

# Raised straight to the route handler without passing through a filter.
DIRECT_ERRORS = frozenset({"configuration_restore_console_required"})

# Every code a client can legitimately receive.
PUBLIC_ERRORS = JOB_FAILURES | CONTROLLER_ERRORS | WIPE_ERRORS | ARCHIVE_ERRORS | DIRECT_ERRORS

# User-facing explanations for startup configuration preparation failures.
STARTUP_PREPARE_ERRORS = {
    "device_type_required": "Choose the node's Netmiko device type in its settings before using a saved startup configuration.",
    "device_type_unsupported": "The node's Netmiko device type has no console recipe, so its startup configuration cannot be applied.",
    "configuration_profile_mismatch": "The node's Netmiko device type does not match the device type of its saved startup configuration.",
    "configuration_restore_console_required": "Startup configuration is applied through the node's console. Set its console type to Telnet or SSH.",
    "configuration_apply_unsupported": "This device's startup configuration cannot be applied through the console. Select a startup boot media profile for the node, or disable its startup entry.",
    "configuration_frr_volume_required": "This FRR container does not keep /etc/frr. Add /etc/frr to the node's additional persistent directories.",
    "configuration_login_required": (
        "The saved controller-mode startup configuration needs a username entry. "
        "Netmiko credentials sign in to an existing account. Add a username entry or turn startup off."
    ),
    "configuration_invalid_content": "The saved startup configuration is not valid for this node's restore method.",
    "startup_media_profile_unknown": "The node's startup boot media profile is not known to the server.",
    "boot_media_tool_missing": "Preparing startup boot media needs xorriso, genisoimage or mkisofs (CD-ROM media), mtools (disk media) or debugfs and e2fsck from e2fsprogs (vEOS flash) on the compute that runs the node.",
    "boot_media_build_failed": "The startup boot media could not be built.",
    "boot_media_too_large": "The startup configuration is too large for the startup boot media.",
    "configuration_factory_reset_failed": "The node's disk could not be returned to its factory state for the startup boot media.",
    "configuration_topology_unsupported": "This node cannot be prepared for its startup boot media: ASAv needs KVM, at least 2048 MB RAM and a virtio disk; vEOS needs one linked-clone disk holding its flash.",
    "configuration_media_slot_unavailable": "Free a compatible QEMU drive slot before using startup boot media.",
}

# Only these field names are echoed back in validation errors; anything else is
# reduced to "field" so a request can never reflect attacker-chosen keys.
VALIDATION_FIELDS = frozenset(
    {
        "body",
        "sets",
        "nodes",
        "content",
        "enabled",
        "device_type",
        "revision",
        "version",
        "selected",
        "selections",
        "selection_revision",
        "id",
        "name",
        "credentials",
        "username",
        "password",
        "enable_secret",
        "set_id",
        "source",
        "kind",
        "node_ids",
        "all",
        "save_to_set",
        "archive",
        "select",
        "assign_nodes",
        "text",
        "profile",
    }
)

VALIDATION_REASONS = frozenset(
    {
        "duplicate_configuration_set_ids",
        "duplicate_configuration_set_names",
        "selected_configuration_set_not_found",
        "configuration_invalid_content",
        "configuration_wipe_selection_required",
    }
)


def error_status(code):
    if code.endswith("not_found"):
        return 404
    if code == "capture_capacity_exhausted":
        return 429
    if code == "configuration_capture_timeout":
        return 408
    if code == "invalid_configuration_archive":
        return 422
    if code == "configuration_archive_too_large":
        return 413
    return 409
