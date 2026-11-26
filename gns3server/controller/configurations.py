"""Configuration export, project capture jobs, startup/live application and wipe."""

import asyncio
import hashlib
import json
import logging
from contextlib import nullcontext
from dataclasses import dataclass
from functools import cached_property
from typing import Literal
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from gns3server.compute.compute_error import ComputeError
from gns3server.controller.configuration_rpc import compute_failure, compute_get
from gns3server.controller.controller_error import ComputeConflictError, ControllerError, ControllerTimeoutError
from gns3server.schemas.configurations import (
    CONSOLE_DEVICE_TYPES,
    DOCKER_FILE_DEVICE_TYPES,
    STARTUP_ENGINES,
    ConsoleCredentials,
    Engine,
    ExportOptions,
    ExportResult,
    RuntimeState,
    Selection,
    Source,
    StartupEntry,
    compatible_device_type,
    docker_network_file,
    normalize_device_type,
)
from gns3server.services.configurations.boot_media import BootMediaProfile, MediaContext, get_profile
from gns3server.services.configurations.console.platforms import get_platform, get_platforms
from gns3server.services.configurations.sets.selections import SelectionStore
from gns3server.services.configurations.sets.store import StartupStore, store_lock
from gns3server.services.configurations.shared.errors import (
    BOOT_MEDIA_ERRORS,
    CAPTURE_FAILURES,
    EXPORT_ERRORS,
    JOB_FAILURES,
    WIPE_ERRORS,
    CaptureFailure,
    ConfigurationError,
)
from gns3server.services.configurations.shared.failure_context import describe_failure, failure_context
from gns3server.services.configurations.shared.node_lease import lifecycle_action, node_lease
from gns3server.services.configurations.shared.safe_io import read_json, run_file_io, write_json
from gns3server.utils.docker_node_type import FRR_CONFIG, docker_node_kind, is_frr_node

log = logging.getLogger(__name__)

# Concurrency and history of the capture and apply jobs a project keeps.
MAX_RUNNING_JOBS = 4
MAX_JOB_HISTORY = 32
CAPTURE_CONCURRENCY = 2
# What the controller waits for the compute, in seconds (the compute's own budgets are in compute/configurations.py).
EXPORT_REQUEST_SECONDS = 35
STARTUP_APPLY_REQUEST_SECONDS = 2400
LIVE_APPLY_REQUEST_SECONDS = 630

# Statuses that report a normal outcome rather than a failure.
INFORMATIONAL_STATUSES = frozenset({"applied", "configuration_apply_accepted", "media_delivered", "saved_state_kept"})


def report_application(node, status, *, startup=True):
    code = status["status"]
    hints = {
        "saved_state_kept": "The node keeps its saved state, so the startup configuration was not delivered. Wipe the node and start it again to apply it.",
        "console_authentication_failed": "Console login failed. Check the node's saved default credentials are valid at boot.",
        "console_unsafe_mode": "Could not reach the appliance's operational prompt for startup application.",
        "configuration_apply_failed": "The appliance rejected its startup configuration; check its console before retrying.",
        "configuration_apply_timeout": "Startup configuration application timed out while waiting for the appliance or console.",
        "configuration_apply_unverified": "The appliance accepted the startup commands but does not report the saved configuration; check its console before retrying.",
        "configuration_apply_accepted": "The appliance accepted the startup commands. This device has no comparable read-back.",
        "media_delivered": "Boot media was attached. Check the node console for the result of the guest's import.",
        "configuration_verification_unavailable": "The appliance accepted the startup commands, but verification was unavailable. Check its console.",
    }
    label = "Startup configuration" if startup else "Configuration"
    if not startup:
        hints["configuration_apply_accepted"] = "The appliance accepted the commands. They were not read back."
    message = f"{label} for {getattr(node, 'name', node.id)}: {hints.get(code, code.replace('_', ' '))}"
    where = describe_failure(status)
    if where:
        message += f" ({where})"
    log.info(
        "Startup configuration node=%s engine=%s result=%s %s",
        node.id,
        getattr(node, "node_type", "unknown"),
        code,
        where,
    )
    emit = getattr(node.project, "emit_notification", None)
    if emit is not None:
        emit("log.info" if code in INFORMATIONAL_STATUSES else "log.error", {"message": message})


def conflict_code(error):
    """The public failure code of a compute conflict answer."""
    return failure(ConfigurationError(error.response().get("message", "configuration_apply_failed")))


def record_status(node, set_id, code, *, report=True):
    """Record the node's startup status for the status endpoint and, unless told not to, tell the user."""
    status = {"status": code, "set_id": str(set_id)}
    state(node.project)["nodes"][node.id] = status
    if report:
        report_application(node, status)
    return status


def state(project):
    if not hasattr(project, "_startup_configuration_state"):
        # "startup" holds the task keys of job-less startup console applies,
        # the only apply tasks a wipe may cancel (live-apply jobs refuse it).
        # "wiping" holds the nodes reserved by a running wipe: no live apply is accepted for them.
        project._startup_configuration_state = {
            "jobs": {},
            "tasks": {},
            "nodes": {},
            "startup": set(),
            "wiping": set(),
        }
    return project._startup_configuration_state


def credentials_for(node, device_type, provided=None):
    """Resolve saved defaults for login and, where required, privileged mode."""
    provided = provided or ConsoleCredentials()
    password = provided.password.get_secret_value() or node.default_password or ""
    secret = provided.enable_secret.get_secret_value()
    if "enable_secret" not in provided.model_fields_set and get_platform(device_type).enable:
        secret = password
    return ConsoleCredentials(
        username=provided.username or node.default_username or get_platform(device_type).default_username,
        password=password,
        enable_secret=secret,
    )


def console_driver(netmiko_device_type):
    """The console recipe for a Netmiko device type; raises why the node has none."""
    driver = normalize_device_type(netmiko_device_type)
    if driver not in CONSOLE_DEVICE_TYPES:
        raise ConfigurationError("device_type_required" if not driver else "device_type_unsupported")
    return driver


@dataclass(frozen=True)
class StartupDelivery:
    method: Literal["native", "media", "console"]
    driver: str | None
    profile_id: str | None = None
    native_engine: bool = False

    @cached_property
    def profile(self) -> BootMediaProfile | None:
        return get_profile(self.profile_id) if self.profile_id else None


@dataclass(frozen=True)
class PreparedStartup:
    set_id: UUID
    entry: StartupEntry
    delivery: StartupDelivery


def startup_delivery(node, entry=None):
    engine = node.node_type
    properties = getattr(node, "properties", None) or {}
    declared = getattr(node, "netmiko_device_type", None)
    native_engine = engine in ("dynamips", "iou", "vpcs") or (
        engine == "docker"
        and docker_node_kind(getattr(node, "console_type", None), properties.get("environment")) == "iol"
    )
    profile_id = properties.get("startup_media_profile") if engine == "qemu" else None
    if native_engine:
        driver = "vpcs" if engine == "vpcs" else "cisco_ios_telnet"
    elif (
        engine == "docker"
        and not declared
        and is_frr_node(getattr(node, "console_type", None), properties.get("environment"), properties.get("image"))
    ):
        driver = "frr"
    elif engine == "docker" and docker_network_file(declared):
        driver = "linux_interfaces"
    else:
        driver = normalize_device_type(declared)
    driver = entry.device_type if entry is not None else driver
    method = "media" if profile_id else "native" if native_engine or driver in DOCKER_FILE_DEVICE_TYPES else "console"
    return StartupDelivery(method, driver, profile_id, native_engine)


def driver_for(node, entry=None):
    return startup_delivery(node, entry).driver


def failure(error):
    # Terminal output and compute transport diagnostics must not become job
    # messages. Only established public configuration error codes are exposed.

    code = error.code if isinstance(error, ConfigurationError) else "configuration_operation_failed"
    if isinstance(error, HTTPException) and error.status_code == 408:
        return "configuration_capture_timeout"
    if not isinstance(code, str):
        return "configuration_operation_failed"
    return code if code in JOB_FAILURES else "configuration_operation_failed"


def new_job(project, operation, set_id, node_ids=()):
    data = state(project)
    if sum(job["status"] == "running" for job in data["jobs"].values()) >= MAX_RUNNING_JOBS:
        raise ConfigurationError("capture_capacity_exhausted")
    while len(data["jobs"]) >= MAX_JOB_HISTORY:
        oldest = next((key for key, value in data["jobs"].items() if value["status"] != "running"), None)
        if oldest is None:
            break
        del data["jobs"][oldest]
    # ``node_ids``: the nodes the job works on, known before it reports on them one by one (a wipe skips them).
    job = {
        "id": str(uuid4()),
        "operation": operation,
        "set_id": str(set_id),
        "status": "running",
        "node_ids": [str(node_id) for node_id in node_ids],
        "nodes": {},
    }
    data["jobs"][job["id"]] = job
    return job


async def capture(project, set_id, node_ids, job):
    store = StartupStore(project)
    data = state(project)
    semaphore = asyncio.Semaphore(CAPTURE_CONCURRENCY)

    async def one(node_id):
        async with semaphore:
            node = project.nodes.get(node_id)
            if node is None:
                job["nodes"][node_id] = "node_not_found"
                return
            # The node as it is now decides how it is read; the old entry only guards its revision and switch.
            driver = driver_for(node)
            network = driver in DOCKER_FILE_DEVICE_TYPES and node.node_type == "docker"
            vpcs = driver == "vpcs" and node.node_type == "vpcs"
            saved = network or vpcs
            source = Source.saved_files if network else Source.saved_startup if vpcs else Source.running
            if driver not in CONSOLE_DEVICE_TYPES and not saved:
                job["nodes"][node_id] = "device_type_required"
                return
            if node.status != "started" and not saved:
                job["nodes"][node_id] = "start_required"
                return
            job["nodes"][node_id] = "capturing"
            try:
                result = await request_export(
                    node,
                    ExportOptions(
                        source=source,
                        device_type=None if saved else driver,
                        credentials=None if saved else credentials_for(node, driver),
                        backup=True,
                    ),
                )
                if project.nodes.get(node_id) is not node:
                    job["nodes"][node_id] = "node_not_found"
                    return
                if (result.project_id, result.node_id, result.engine, result.source) != (
                    UUID(project.id),
                    UUID(node.id),
                    Engine(node.node_type),
                    source,
                ) or len(result.files) != 1:
                    raise ConfigurationError("configuration_identity_mismatch")
                if network and result.files[0].filename != DOCKER_FILES[driver]:
                    raise ConfigurationError("configuration_apply_unsupported")
                if vpcs and result.files[0].filename != "startup.vpc":
                    raise ConfigurationError("configuration_apply_unsupported")
                content = result.files[0].content.decode("utf-8", errors="strict")
                await run_file_io(save_captured_entry, node, set_id, originals.get(UUID(node_id)), driver, content)
                job["nodes"][node_id] = "captured"
            except ConfigurationError as error:
                job["nodes"][node_id] = (
                    "node_not_found" if error.code == "configuration_node_not_found" else failure(error)
                )
            except Exception as error:
                job["nodes"][node_id] = failure(error)

    try:
        _, selected = await run_file_io(store.set, set_id)
        originals = dict(selected.nodes)
        await asyncio.gather(*(one(node_id) for node_id in node_ids))
        job["status"] = "finished"
    except asyncio.CancelledError:
        job["status"] = "cancelled"
        raise
    except Exception as error:
        job["status"] = "failed"
        for node_id in node_ids:
            if job["nodes"].get(node_id) != "captured":
                job["nodes"][node_id] = failure(error)
    finally:
        data["tasks"].pop(job["id"], None)


def launch_capture(project, set_id, node_ids):
    job = new_job(project, "capture", set_id, node_ids)
    state(project)["tasks"][job["id"]] = asyncio.create_task(capture(project, set_id, node_ids, job))
    return job


def assigned_entry(node):
    """Resolve the node's startup set consistently for boot and wipe."""
    if node.node_type not in STARTUP_ENGINES:
        return None
    store = StartupStore(node.project)
    with store_lock(node.project):
        document = store.read()
        assigned = SelectionStore(node.project).selections()["nodes"].get(node.id)
    if assigned is None:
        selected = next(s for s in document.sets if s.id == document.selected)
    else:
        selection = Selection.model_validate(assigned)
        if selection.kind == "none":
            return None
        selected = next((s for s in document.sets if s.id == selection.set_id), None)
        if selected is None:
            raise ConfigurationError("configuration_set_not_found")
    entry = selected.nodes.get(UUID(node.id))
    return (selected.id, entry) if entry is not None and entry.enabled else None


def with_text(resolved):
    """A resolved ``(set id, entry)`` pair when the entry has text to deliver."""
    if resolved is None or not resolved[1].content.strip():
        return None
    return resolved


def selected_entry(node):
    return with_text(assigned_entry(node))


def managed(node):
    """True once a node's startup state is tracked by an assignment or a wipe.

    QEMU nodes are never enrolled: they only replay through their console.
    """
    if node.node_type == "qemu":
        return False
    store = SelectionStore(node.project)
    return (
        node.id in store.selections()["nodes"]
        or read_json(store.root / "managed" / f"{UUID(node.id)}.json") is not None
    )


def enroll(node):
    write_json(SelectionStore(node.project).root / "managed" / f"{UUID(node.id)}.json", {"managed": True})


def has_media_profile(node):
    return startup_delivery(node).method == "media"


def validate_startup_entry(node, entry=None, *, delivery=None):
    """Validate the resolved delivery before boot or a destructive wipe."""
    delivery = delivery or startup_delivery(node, entry)
    if node.node_type not in STARTUP_ENGINES:
        return
    if entry is not None and not compatible_device_type(node.node_type, entry.device_type):
        raise ConfigurationError("configuration_apply_unsupported")
    if node.node_type != "qemu" or entry is None or not entry.enabled or not entry.content.strip():
        return
    if delivery.method == "media":
        profile = delivery.profile
        if entry.device_type not in profile.device_types:
            raise ConfigurationError("configuration_profile_mismatch")
        profile.files(entry.content, MediaContext(node_id=node.id))
        return
    if not get_platform(entry.device_type).restorable:
        raise ConfigurationError("configuration_apply_unsupported")
    if console_driver(getattr(node, "netmiko_device_type", None)) != entry.device_type:
        raise ConfigurationError("configuration_profile_mismatch")
    if getattr(node, "console_type", None) not in (None, "telnet", "ssh"):
        raise ConfigurationError("configuration_restore_console_required")


async def startup_state(node):
    """The compute's startup journal state of a node; refuses an interrupted or unreadable one."""
    value = await compute_get(node, "/configuration-startup-state")
    try:
        startup_runtime = RuntimeState.model_validate(value)
    except ValidationError:
        raise ConfigurationError("invalid_startup_runtime") from None
    if startup_runtime.state in ("resetting", "preparing"):
        raise ConfigurationError("configuration_outcome_unknown")
    return startup_runtime.state


def preparation_marker(node):
    """Remembers that the compute holds a native preparation for this node (kept across controller restarts)."""
    return StartupStore(node.project).root / "prepared" / f"{UUID(node.id)}.json"


async def withdraw_preparation(node):
    """Take back a native preparation that this start will not repeat."""
    marker = preparation_marker(node)
    if not marker.exists():
        return
    try:
        await node.post("/configuration-withdraw")
    except ComputeConflictError as error:
        raise ConfigurationError(conflict_code(error)) from None
    marker.unlink(missing_ok=True)


async def prepare_start(node):
    """Native engines accept startup text before their emulator is started."""
    resolved = await run_file_io(assigned_entry, node)
    entry = resolved[1] if resolved else None
    delivery = startup_delivery(node, entry)
    selected = with_text(resolved)
    prepared = PreparedStartup(*selected, delivery) if selected else None
    try:
        validate_startup_entry(node, entry, delivery=delivery)
    except ConfigurationError:
        # An entry that this start would not apply must not stop an ordinary restart.
        booted = ("initialized",) if delivery.method == "media" else ("initialized", "legacy_existing")
        if prepared is None or await startup_state(node) not in booted:
            raise
        return None
    if node.node_type != "qemu" and (prepared is None or delivery.method != "native"):
        # Startup was turned off, cleared or changed to another kind since an earlier Start prepared the node.
        await withdraw_preparation(node)
    if delivery.method == "media":
        return await stage_media(node, delivery.profile, prepared)
    if prepared is None:
        return None
    selected_id = prepared.set_id
    # Console replay and file delivery must respect saved guest state. Only a
    # successful wipe authorizes injection; missing journals conservatively
    # represent an existing runtime. A native set stays "prepared", and is
    # written again, until the node has launched.
    pending = ("clean", "prepared") if delivery.method == "native" else ("clean",)
    if await startup_state(node) not in pending:
        return None
    validate_console_content(node, entry, delivery)
    if delivery.method == "native":
        # Recorded before the request: a lost reply must still lead to a withdrawal.
        write_json(preparation_marker(node), {"set_id": str(selected_id)})
        try:
            await node.post("/configuration-apply", data={"device_type": entry.device_type, "content": entry.content})
        except ComputeConflictError as error:
            code = conflict_code(error)
            record_status(node, selected_id, code)
            raise ConfigurationError(code) from None
        except ConfigurationError as error:
            record_status(node, selected_id, failure(error))
            raise
        record_status(node, selected_id, "prepared", report=False)
    return prepared


def validate_console_content(node, entry, delivery):
    if node.node_type == "qemu" and delivery.method == "console":
        try:
            get_platform(entry.device_type).preflight(entry.content)
        except CaptureFailure as error:
            raise ConfigurationError(str(error)) from None


def usable_admin_password(node, device_type):
    """The node's saved console password when it can become the device's admin or enable password.

    A device with a privileged mode takes it as its enable password, whatever the user name. Otherwise only
    the ``admin`` account (or an unset user name) and a password other than the vendor's factory one
    qualify; anything else leaves the factory admin alone.
    """
    saved = credentials_for(node, device_type)
    if get_platform(device_type).enable:
        return saved.enable_secret.get_secret_value() or None
    password = saved.password.get_secret_value()
    return password if saved.username in ("", "admin") and password not in ("", "admin") else None


def media_payload(node, profile, entry):
    data = {"profile": profile.id, "content": entry.content if entry else None}
    if entry is not None and profile.uses_admin_password:
        password = usable_admin_password(node, entry.device_type)
        if password:
            data["admin_password"] = password
    return data


async def stage_media(node, profile, prepared):
    """Stage (or withdraw) the node's boot media; returns ``prepared`` when the guest will receive it."""
    selected_id, entry = (prepared.set_id, prepared.entry) if prepared is not None else (None, None)
    data = media_payload(node, profile, entry)
    try:
        reply = await node.post("/configuration-media", data=data, timeout=profile.stage_seconds)
    except ComputeConflictError as error:
        code = conflict_code(error)
        if entry is not None:
            record_status(node, selected_id, code)
        raise ConfigurationError(code) from None
    delivered = state(node.project).setdefault("media", {})
    if entry is None:
        delivered.pop(node.id, None)
        return None
    # What this start would deliver; compared with what the node was last given or told about.
    digest = hashlib.sha256(
        "\0".join((profile.id, entry.content, data.get("admin_password", ""))).encode("utf-8")
    ).hexdigest()
    if not (reply.json or {}).get("staged"):
        # The guest already ran (or predates this feature): it keeps its own state until a wipe. Only an entry
        # that changed since it was last delivered or reported is news; a plain restart is not.
        if delivered.get(node.id) != digest:
            delivered[node.id] = digest
            record_status(node, selected_id, "saved_state_kept")
        return None
    delivered[node.id] = digest
    record_status(node, selected_id, "prepared", report=False)
    return prepared


async def apply(node, selected_id, entry, *, job=None):
    # A live apply (with a job) holds the node. Explicit console startup can wait minutes for a boot prompt: it
    # keeps its cancellation and runtime checks without blocking unrelated node actions, and a clean restore
    # rejects an active console job before its reset boundary.
    async with node_lease(node) if job is not None else nullcontext():
        return await _apply(node, selected_id, entry, job=job)


def validate_live_recipe(node, entry):
    if node.node_type == "qemu" and normalize_device_type(node.netmiko_device_type) != entry.device_type:
        raise ConfigurationError("configuration_profile_mismatch")


async def _apply(node, selected_id, entry, *, job=None):
    data = state(node.project)
    status = {
        "status": "waiting_for_console",
        "set_id": str(selected_id),
    }
    if job is None:
        data["nodes"][node.id] = status
    else:
        job["nodes"][node.id] = "applying"
    try:
        if job is not None:
            validate_live_recipe(node, entry)
        await node.post(
            "/configuration-apply",
            data={
                "device_type": entry.device_type,
                "content": entry.content,
                "credentials": credentials_for(node, entry.device_type).request_data(),
                "wait_ready": job is None,
                **({"running": True} if job is not None else {}),
            },
            timeout=STARTUP_APPLY_REQUEST_SECONDS if job is None else LIVE_APPLY_REQUEST_SECONDS,
        )
        # Only a startup replay of a verifiable platform is read back; a live apply never is.
        status["status"] = (
            "applied" if job is None and get_platform(entry.device_type).verifiable else "configuration_apply_accepted"
        )
    except asyncio.CancelledError:
        status["status"] = "cancelled"
        raise
    except ComputeConflictError as error:
        body = error.response()
        status["status"] = conflict_code(error)
        status.update(failure_context(body.get("details")))
    except (ControllerError, ComputeError, HTTPException, OSError, TimeoutError):
        status["status"] = "configuration_apply_failed"
    except ConfigurationError as error:
        status["status"] = failure(error)
        status.update(failure_context(error.context))
    finally:
        if job is not None:
            job["nodes"][node.id] = status["status"]
            where = {key: value for key, value in status.items() if key not in ("status", "set_id")}
            if where:
                job.setdefault("details", {})[node.id] = where
            job["status"] = "cancelled" if status["status"] == "cancelled" else "finished"
        if status["status"] not in ("waiting_for_console", "cancelled"):
            report_application(node, status, startup=job is None)
        if data["tasks"].get("apply:" + node.id) is asyncio.current_task():
            data["tasks"].pop("apply:" + node.id, None)
            data.setdefault("startup", set()).discard("apply:" + node.id)


def launch_apply(node, prepared):
    if prepared is None:
        return
    if prepared.delivery.method == "media":
        record_status(node, prepared.set_id, "media_delivered")
        return
    if prepared.delivery.method == "native":
        record_status(node, prepared.set_id, "applied")
        return
    cancel_apply(node)
    # Called from Node.start under the node lifecycle lease. The console apply
    # task itself takes no lease (it may wait minutes for a boot prompt), so
    # Stop cancels it and Wipe refuses while it is registered; Wipe re-checks
    # that registration after acquiring the lease.
    record_status(node, prepared.set_id, "waiting_for_console", report=False)
    data = state(node.project)
    data["tasks"]["apply:" + node.id] = asyncio.create_task(apply(node, prepared.set_id, prepared.entry))
    data.setdefault("startup", set()).add("apply:" + node.id)


def cancel_apply(node):
    data = getattr(node.project, "_startup_configuration_state", None)
    task = data["tasks"].get("apply:" + node.id) if data is not None else None
    if task is not None:
        task.cancel()


def launch_live_apply(node, set_id, entry):
    data = state(node.project)
    key = "apply:" + node.id
    if key in data["tasks"] or node.id in data["wiping"]:
        raise ConfigurationError("configuration_operation_in_progress")
    job = new_job(node.project, "apply", set_id, [node.id])
    task = asyncio.create_task(apply(node, set_id, entry, job=job))
    data["tasks"][key] = task

    def finish(finished):
        # A task cancelled while it still waited for the node never reached its own cleanup.
        if job["status"] == "running":
            job["status"] = job["nodes"][node.id] = "cancelled"
        if data["tasks"].get(key) is finished:
            data["tasks"].pop(key, None)

    task.add_done_callback(finish)
    return job


@lifecycle_action
async def request_export(node, options):
    if options.device_type is not None:
        options = options.model_copy(
            update={"credentials": credentials_for(node, options.device_type, options.credentials)}
        )
    try:
        response = await node.post("/configuration-export", data=options.request_data(), timeout=EXPORT_REQUEST_SECONDS)
    except ComputeConflictError as error:
        body = error.response()
        code = body.get("message")
        details = body.get("details")
        previous = details.get("previous_error") if isinstance(details, dict) else None
        raise ConfigurationError(
            code if isinstance(code, str) and code in EXPORT_ERRORS else "configuration_export_failed",
            previous_error=(
                previous
                if code == "console_recovery_required" and isinstance(previous, str) and previous in CAPTURE_FAILURES
                else None
            ),
        ) from None
    except ControllerTimeoutError:
        raise HTTPException(status_code=408, detail="configuration_export_timeout") from None
    except (ControllerError, HTTPException, OSError, TimeoutError) as error:
        if isinstance(error, HTTPException) and error.status_code == 429:
            raise HTTPException(status_code=429, detail="capture_capacity_exhausted") from None
        unavailable = compute_failure(node, "/configuration-export", error)
        if unavailable.code == "configuration_compute_unavailable":
            raise HTTPException(status_code=502, detail="configuration_compute_unavailable") from None
        # A reachable compute that answers with an error status is an export failure.
        raise HTTPException(status_code=502, detail="configuration_export_failed") from None
    return ExportResult.model_validate_json(json.dumps(response.json))


# The files an export holds that can become a set entry, besides each console platform's own capture file.
DOCKER_FILES = {"linux_interfaces": "etc/network/interfaces", "frr": FRR_CONFIG}
NATIVE_EXPORT_FILENAMES = frozenset({"startup-config.cfg", "startup.vpc", *DOCKER_FILES.values()})


def store_export(node, result, driver, saved):
    # Private files and arbitrary multi-file Docker exports are downloads,
    # not a reusable single startup entry.
    if result.engine == Engine.docker and result.source == Source.saved_files:
        drivers = {filename: device_type for device_type, filename in DOCKER_FILES.items()}
        if len(result.files) != 1 or result.files[0].filename not in drivers or node.properties.get("extra_configs"):
            raise ConfigurationError("configuration_not_savable")
        driver = drivers[result.files[0].filename]
    filenames = NATIVE_EXPORT_FILENAMES | {platform.filename for platform in get_platforms().values()}
    if len(result.files) != 1 or result.files[0].filename not in filenames or not driver:
        raise ConfigurationError("configuration_not_savable")
    try:
        content = result.files[0].content.decode("utf-8")
    except UnicodeError:
        raise ConfigurationError("invalid_configuration_output") from None
    save_captured_entry(node, *saved, driver, content)


def save_captured_entry(node, set_id, previous, driver, content):
    store = StartupStore(node.project)
    with store_lock(node.project):
        if node.project.nodes.get(node.id) is not node:
            raise ConfigurationError("configuration_node_not_found")
        document, current = store.set(set_id)
        if current.nodes.get(UUID(node.id)) != previous:
            raise ConfigurationError("startup_configurations_changed")
        store.put_entry(
            set_id,
            node.id,
            StartupEntry(device_type=driver, content=content, enabled=previous.enabled if previous else False),
            revision=document.revision,
        )


MEDIA_PREFLIGHT_CODES = BOOT_MEDIA_ERRORS | {
    "configuration_profile_mismatch",
    "configuration_invalid_content",
    "configuration_login_required",
}
COMPUTE_WIPE_CODES = MEDIA_PREFLIGHT_CODES | WIPE_ERRORS
CONTROLLER_WIPE_CODES = COMPUTE_WIPE_CODES | {
    "device_type_required",
    "device_type_unsupported",
    "configuration_apply_unsupported",
    "configuration_restore_console_required",
}


WIPEABLE_STATUSES = ("stopped", "started", "suspended")


def wipe_failure(code, allowed):
    """Only these codes are reported per node; anything else is a generic failure."""
    return code if isinstance(code, str) and code in allowed else "configuration_wipe_failed"


def wipe_unsupported(node):
    """Docker nodes can be wiped only through the network file or as native IOL."""
    return node.node_type == "docker" and startup_delivery(node).method != "native"


async def stop_for_wipe(node, stopped):
    """Stop a running node; False when it is not confirmed stopped. ``stopped`` records a confirmed stop."""
    if node.status == "stopped":
        return True
    try:
        await node.stop(strict=True)
    except (ControllerError, TimeoutError):
        return False
    if node.status != "stopped":
        return False
    if stopped is not None:
        stopped.append(node.id)
    return True


async def cancel_startup_apply(data, node_id):
    """Cancel a pending startup console apply; True when no apply remains registered.

    A live-apply job (or anything else registered) is never cancelled here.
    """
    key = "apply:" + node_id
    task = data["tasks"].get(key)
    if task is None:
        return True
    if key not in data.setdefault("startup", set()):
        return False
    task.cancel()
    await asyncio.wait({task}, timeout=5)
    if not task.done():
        return False
    if data["tasks"].get(key) is task:
        data["tasks"].pop(key, None)
    if key in data["tasks"]:
        # Registered while the cancelled replay was finishing: not ours to cancel.
        return False
    data["startup"].discard(key)
    return True


async def preflight_wipe_restore(node):
    resolved = await run_file_io(assigned_entry, node)
    entry = resolved[1] if resolved else None
    delivery = startup_delivery(node, entry)
    validate_startup_entry(node, entry, delivery=delivery)
    if entry is None or not entry.content.strip():
        return delivery
    if delivery.method == "console":
        validate_console_content(node, entry, delivery)
    elif delivery.method == "media":
        profile = delivery.profile
        await node.post(
            "/configuration-media/preflight",
            data=media_payload(node, profile, entry),
            timeout=profile.stage_seconds,
        )
    return delivery


async def wipe_node(data, node, stopped):
    """Wipe one reserved node; returns ``wiped`` or the reason it was not."""
    try:
        async with node_lease(node):
            if node.status not in WIPEABLE_STATUSES:
                return "stop_required"
            # A pending startup replay is cancelled (the wipe stops the
            # node anyway); an explicit live apply is never interrupted.
            # Re-checked under the lease: a Start may have launched it.
            # Resolve appliance setup while the node is still intact.
            # Wipe must not discard the uploaded project source.
            delivery = await preflight_wipe_restore(node)
            # Ask the compute whether it can reset the storage before the guest is taken down.
            await node.post("/configuration-wipe/preflight")
            if not await cancel_startup_apply(data, node.id):
                return "configuration_operation_in_progress"
            # The lease prevents a concurrent Start between the confirmed
            # stop and the destructive wipe.
            if not await stop_for_wipe(node, stopped):
                return "stop_required"
            await node.post("/configuration-wipe")
            if delivery.native_engine:
                await run_file_io(enroll, node)
        data["nodes"].pop(node.id, None)
        data.get("media", {}).pop(node.id, None)
        return "wiped"
    except ComputeConflictError as error:
        return wipe_failure(error.response().get("message"), COMPUTE_WIPE_CODES)
    except ConfigurationError as error:
        return wipe_failure(error.code, CONTROLLER_WIPE_CODES)
    except (ControllerError, HTTPException, OSError):
        return "configuration_wipe_failed"


async def wipe_configurations(project, node_ids, *, stopped=None):
    """Wipe eligible nodes independently and retain saved project configurations.

    Any state is accepted: a stopped node is wiped directly, a started or
    suspended node is stopped first. When ``stopped`` is a list, the ids of the
    nodes that had to be stopped are appended to it.
    """
    data = state(project)
    results = {}
    for node_id in node_ids:
        node = project.nodes.get(node_id)
        key = "apply:" + node_id
        # Only the nodes a running capture, apply or wipe works on are refused; the others are wiped as usual.
        busy = node_id in data["wiping"] or any(
            job["status"] == "running" and node_id in job["node_ids"] for job in data["jobs"].values()
        )
        if node is None:
            results[node_id] = "node_not_found"
        elif busy:
            results[node_id] = "configuration_operation_in_progress"
        elif node.status not in WIPEABLE_STATUSES:
            results[node_id] = "stop_required"
        elif wipe_unsupported(node):
            results[node_id] = "configuration_wipe_unsupported"
        elif key in data["tasks"] and key not in data["startup"]:
            results[node_id] = "configuration_operation_in_progress"
        else:
            data["wiping"].add(node_id)
            try:
                results[node_id] = await wipe_node(data, node, stopped)
            finally:
                data["wiping"].discard(node_id)
    return results
