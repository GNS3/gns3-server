"""Compute-local configuration service for export, startup restore and wipe.

Native file collectors remain engine-owned; all CLI operations use the same
leased console session and platform adapters. No configuration is stored here.
"""

import asyncio
import base64
import binascii
import contextlib
import itertools
import logging
import re
import shlex
import time
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from gns3server.schemas.configurations import (
    CONSOLE_DEVICE_TYPES,
    MAX_FILE_BYTES,
    ConsoleCredentials,
    Engine,
    ExportFile,
    ExportOptions,
    ExportResult,
    Source,
    compatible_device_type,
    docker_network_file,
)
from gns3server.services.configurations.boot_media.staging import stage_media, wipe_paths
from gns3server.services.configurations.console.platforms import get_platform
from gns3server.services.configurations.console.replay import restore_seconds
from gns3server.services.configurations.console.session_runner import run_console_session, wait_for_console_ready
from gns3server.services.configurations.console.verification import restore_verified
from gns3server.services.configurations.shared import preparation
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.failure_context import describe_failure
from gns3server.services.configurations.shared.node_lease import (
    node_lease,
    require_stopped,
    runtime_stopped_or_replaced,
)
from gns3server.services.configurations.shared.safe_io import (
    atomic_write,
    run_file_io,
    stable_read,
    validate_owned_paths,
)
from gns3server.services.configurations.shared.startup_journal import (
    journal_path,
    mark_legacy_import,
    mark_set_prepared,
    mark_wiped,
    require_launchable,
    set_runtime_state,
)
from gns3server.utils.asyncio import loop_limit, saturated
from gns3server.utils.docker_node_type import FRR_CONFIG, FRR_STAGED_CONFIG, FRR_VOLUME, is_frr_node

from .docker.container_state import docker_stopped
from .docker.iol_docker_vm import IOLDockerVM
from .docker.iol_wipe import DockerIOLWipe
from .dynamips.dynamips_error import DynamipsError
from .iou.utils.iou_export import nvram_export
from .iou.utils.iou_import import checksum

log = logging.getLogger(__name__)

# Entries of these types are a file written before boot, on engines that are not natively IOS.
FILE_DEVICE_TYPES = {"vpcs": "startup.vpc", "linux_interfaces": "etc/network/interfaces", "frr": FRR_STAGED_CONFIG}

FRR_SHOW_SECONDS = 30


def restore_deadline(content):
    """Whole-restore bound for a console apply that does not wait for boot."""
    return min(600, max(120, restore_seconds(content) + 10))


# Time budgets, in seconds. One whole startup console replay, retries included, has APPLY_CONSOLE_DEADLINE; it sits
# inside apply()'s APPLY_SECONDS and the controller's 2400 s request limit.
EXPORT_SECONDS = 30
APPLY_SECONDS = 1200
APPLY_CONSOLE_DEADLINE = 900
VERIFY_SECONDS = 900
RUNNING_APPLY_SECONDS = 150
STARTUP_SESSION_SECONDS = 600  # One attempt may wait this long for the boot prompt.
READBACK_READY_SECONDS = 240  # The read-back that verifies a replay waits for a quiet console, then reads.
READBACK_SECONDS = 60
READBACK_SESSION_SECONDS = 30
MAX_APPLY_ATTEMPTS = 600
MAX_NVRAM_BYTES = 1024 * 1024
clock = time.monotonic


async def dynamips_query(node, operation: str) -> list[str]:
    """Read-only native protocol on a separate connection, with no output logs.

    The legacy shared send() intentionally drains replies after cancellation and
    logs result bytes. A capture must neither close that shared connection nor
    inherit its unbounded cancellation behavior. No hypervisor settings change.
    """
    if operation not in ("get_status", "extract_config"):
        raise ConfigurationError("unsupported_hypervisor_operation")
    name = node.name
    if not name or any(character in name for character in ('"', "\r", "\n", "\x00")):
        raise ConfigurationError("invalid_node_name")
    hypervisor = node._hypervisor
    host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(hypervisor.host, hypervisor.host)
    writer = None
    try:
        async with asyncio.timeout(10):
            reader, writer = await asyncio.open_connection(host, hypervisor.port)
            writer.write(f'vm {operation} "{name}"\n'.encode())
            await writer.drain()
            payload = bytearray()
            limit = 2 * ((MAX_FILE_BYTES + 2) // 3 * 4) + 1024
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    raise ConfigurationError("hypervisor_disconnected")
                payload.extend(chunk)
                if len(payload) > limit:
                    raise ConfigurationError("configuration_too_large")
                if not payload.endswith(b"\r\n"):
                    continue
                lines = payload[:-2].split(b"\r\n")
                if lines[-1].startswith(b"2"):
                    raise ConfigurationError("native_extraction_failed")
                if lines[-1].startswith(b"100-"):
                    result = []
                    for line in lines:
                        if len(line) < 4 or not line[:3].isdigit() or bytes(line[3:4]) not in (b" ", b"-"):
                            raise ConfigurationError("invalid_hypervisor_response")
                        value = line[4:].decode("utf-8")
                        if not (line.startswith(b"100-") and value == "OK"):
                            result.append(value)
                    return result
    except TimeoutError:
        raise
    except (OSError, UnicodeError):
        raise ConfigurationError("hypervisor_unavailable") from None
    finally:
        if writer is not None:
            writer.close()
            with contextlib.suppress(OSError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), timeout=1)


def decode_nvram(snapshot: bytes):
    if len(snapshot) < 8192 or len(snapshot) > MAX_NVRAM_BYTES or len(snapshot) % 1024:
        raise ValueError("invalid NVRAM size")
    checked = bytearray(snapshot)
    checksum(checked, 0, len(checked) // 2)
    if checked[4:6] != snapshot[4:6]:
        raise ValueError("invalid NVRAM checksum")
    return nvram_export(snapshot, MAX_FILE_BYTES)


class ConfigurationService:
    """Shared compute entry point; adapters own appliance-specific behavior."""

    def __init__(self, node, engine: Engine):
        self.node = node
        self.engine = engine
        self.native = engine in (Engine.dynamips, Engine.iou) or (
            engine == Engine.docker and isinstance(node, IOLDockerVM)
        )

    async def export(self, options: ExportOptions = ExportOptions()) -> ExportResult:
        source = options.source or (
            Source.saved_startup
            if self.native or self.engine == Engine.vpcs
            else Source.saved_files
            if self.engine == Engine.docker
            else Source.running
        )
        if saturated("capture"):
            raise ConfigurationError("capture_capacity_exhausted")
        async with loop_limit("capture"), asyncio.timeout(EXPORT_SECONDS):
            try:
                if source in (Source.running, Source.save_then_capture):
                    files = await self._running(options, save=source == Source.save_then_capture)
                elif self.engine == Engine.vpcs and source == Source.saved_startup:
                    root = Path(self.node.working_dir).resolve(strict=True)
                    content = await asyncio.to_thread(stable_read, str(root), root / "startup.vpc", MAX_FILE_BYTES)
                    files = (ExportFile(filename="startup.vpc", content=content),)
                elif self.native and source == Source.saved_startup:
                    files = await self._native_files()
                elif self.engine == Engine.docker and not self.native and source == Source.saved_files:
                    files = await self._docker_files()
                else:
                    raise ConfigurationError("source_unsupported")
                return ExportResult(
                    project_id=UUID(self.node.project.id),
                    node_id=UUID(self.node.id),
                    engine=self.engine,
                    source=source,
                    files=files,
                )
            except ConfigurationError as error:
                if error.code == "configuration_not_found":
                    # A 404 would be indistinguishable from a missing node on the
                    # controller; this is "nothing saved yet" (e.g. VPCS writes
                    # startup.vpc asynchronously after `save`).
                    raise ConfigurationError("configuration_not_saved") from None
                raise
            except ValidationError:
                raise ConfigurationError("invalid_configuration_output") from None

    async def _running(self, options, *, save=False):
        if options.device_type is None:
            raise ConfigurationError("device_type_required")
        extra = {"backup": True} if options.backup else {}
        if save:
            extra["save"] = True
        content = await run_console_session(
            self.node,
            options.credentials or ConsoleCredentials(),
            device_type=options.device_type,
            **extra,
        )
        platform = get_platform(options.device_type)
        return (ExportFile(filename=platform.filename, content=content),)

    async def preflight_wipe(self):
        """Refuse, changing nothing, a node whose storage a wipe could not reset. The node may be running."""
        try:
            if self.engine == Engine.docker and self.native:
                await DockerIOLWipe(self.node).inspect()
            else:
                await run_file_io(_plan_wipe, self.node, self.engine)
        except TimeoutError:
            raise ConfigurationError("configuration_wipe_failed") from None

    async def wipe(self):
        """Check runtime state before removing stopped-node configuration files."""
        require_stopped(self.node)
        try:
            if self.engine == Engine.dynamips and self.node._hypervisor is not None:
                if await dynamips_query(self.node, "get_status") != ["0"]:
                    raise ConfigurationError("stop_required")
            elif self.engine == Engine.docker:
                if self.native:
                    await DockerIOLWipe(self.node).reset_runtime()
                    return
                if not await docker_stopped(self.node):
                    raise ConfigurationError("stop_required")
        except TimeoutError:
            raise ConfigurationError("configuration_wipe_failed") from None
        # Runtime checks above can await. The caller holds the node lifecycle
        # lease across the stopped-state recheck, filesystem checks and reset.
        await run_file_io(_wipe_runtime, self.node, self.engine)

    async def stage_media(self, request):
        """Stage native boot media (QEMU only); see services/configurations/boot_media."""
        if self.engine != Engine.qemu:
            raise ConfigurationError("configuration_apply_unsupported")
        password = request.admin_password.get_secret_value() if request.admin_password is not None else None
        return await stage_media(self.node, request.profile, request.content, password)

    async def apply(self, options):
        """Restore native files before boot or apply CLI after the guest starts."""
        if not compatible_device_type(self.engine, options.device_type):
            raise ConfigurationError("configuration_apply_unsupported")
        if options.device_type in CONSOLE_DEVICE_TYPES and not get_platform(options.device_type).restorable:
            # Captured through the console only (Viptela): its startup is native boot media.
            raise ConfigurationError("configuration_apply_unsupported")
        if options.running:
            await self._apply_running(options)
            return
        if self.native or options.device_type in FILE_DEVICE_TYPES:
            # These write native files before boot.
            if self.node.status != "stopped":
                raise ConfigurationError("stop_required")
            # An earlier preparation is undone first, so that its text never counts as the node's own file.
            await self.withdraw()
            before = preparation.snapshot(self.node, self._replaced_files(options.device_type))
            nvram = preparation.snapshot(self.node, self._nvram_files())
            await self._prepare_files(options)
            preparation.record(self.node, before, nvram)
            return
        try:
            async with asyncio.timeout(APPLY_SECONDS):
                await self._apply_console(options)
        except TimeoutError:
            raise ConfigurationError("configuration_apply_timeout") from None
        try:
            async with asyncio.timeout(VERIFY_SECONDS):
                await self._verify_console_restore(options)
        except TimeoutError:
            raise ConfigurationError("configuration_verification_unavailable") from None

    def _replaced_files(self, device_type):
        """The files a startup preparation of this kind writes."""
        if self.native:
            if self.engine == Engine.dynamips:
                return [self.node.startup_config_path]
            return ["startup-config.cfg"] if self.engine == Engine.iou else []
        return [FILE_DEVICE_TYPES[device_type]]

    def _nvram_files(self):
        """The NVRAM an IOU or IOL launch builds from the prepared text, before the guest runs."""
        application_id = getattr(self.node, "application_id", None)
        if not self.native or self.engine == Engine.dynamips or application_id is None:
            return []
        name = f"nvram_{application_id:05d}"
        return [name if self.engine == Engine.iou else f"tmp/run/{name}"]

    async def _prepare_files(self, options):
        """Write native files before boot."""
        if self.native:
            if options.device_type != "cisco_ios_telnet":
                raise ConfigurationError("configuration_apply_unsupported")
            if self.node.status != "stopped":
                raise ConfigurationError("stop_required")
            self._write_native({"startup_config_content": options.content})
            if self.engine == Engine.docker:
                # Reapply the selected set even when its content equals the
                # last imported text but the guest subsequently saved changes.
                self.node._startup_config_dirty = True
            mark_set_prepared(self.node)
        elif options.device_type == "vpcs":
            if self.node.status != "stopped":
                raise ConfigurationError("stop_required")
            atomic_write(self.node.working_dir, "startup.vpc", options.content)
        elif options.device_type == "linux_interfaces":
            restore_network_file(self.node, options.content)
        else:
            restore_frr_config(self.node, options.content)

    async def withdraw(self):
        """Take back what a startup preparation wrote for a launch that has not happened yet."""
        if self.node.status != "stopped":
            return
        if preparation.withdraw(self.node) and self.native and self.engine == Engine.docker:
            # The text waits in memory until the launch writes it to NVRAM.
            self.node._startup_config_content = None
            self.node._startup_config_dirty = False

    async def _verify_console_restore(self, options):
        """Confirm a startup restore survived the guest's own boot.

        A mismatch can be caused by formatting, a later boot phase or an
        actual configuration difference. It does not authorize another replay.
        """
        if not options.wait_ready or not get_platform(options.device_type).verifiable:
            return
        captured = await self._console_configuration(options)
        if captured is None:
            raise ConfigurationError("configuration_verification_unavailable")
        verified, coverage = restore_verified(options.content, captured)
        if verified is None:
            raise ConfigurationError("configuration_verification_unavailable")
        if not verified:
            log.warning(
                "Startup configuration on %s could not be confirmed after replay: "
                "%d%% of comparable commands are present in their original scope",
                self.node.id,
                round(coverage * 100),
            )
            raise ConfigurationError("configuration_apply_unverified")

    async def _console_configuration(self, options):
        """Best-effort read-back; None when the guest cannot be read safely."""
        instance = getattr(self.node, "_process", None)
        proxy = getattr(self.node, "_configuration_console_proxy", None)
        try:
            await wait_for_console_ready(self.node, options.device_type, READBACK_READY_SECONDS, startup=True)
            async with node_lease(self.node):
                if runtime_stopped_or_replaced(self.node, instance, proxy):
                    return None
                async with asyncio.timeout(READBACK_SECONDS):
                    content = await run_console_session(
                        self.node,
                        options.credentials,
                        device_type=options.device_type,
                        deadline=READBACK_SESSION_SECONDS,
                        backup=True,
                    )
                if runtime_stopped_or_replaced(self.node, instance, proxy):
                    return None
            return content.decode("utf-8", errors="strict")
        except (ConfigurationError, TimeoutError, UnicodeError):
            return None

    async def _apply_running(self, options):
        if options.device_type not in CONSOLE_DEVICE_TYPES:
            raise ConfigurationError("configuration_apply_unsupported")
        if self.node.status != "started":
            raise ConfigurationError("start_required")
        try:
            async with asyncio.timeout(RUNNING_APPLY_SECONDS):
                await self._apply_console(options)
        except TimeoutError:
            raise ConfigurationError("configuration_apply_timeout") from None

    async def import_native(self, settings):
        """Direct node-property updates of the startup files; these retain their existing behavior.

        The journal changes only after the engine has written everything.
        """
        if not self.native:
            raise ConfigurationError("configuration_apply_unsupported")
        imports = self.engine in (Engine.iou, Engine.docker) and any(
            key in settings for key in ("startup_config_content", "private_config_content")
        )
        if imports:
            require_launchable(self.node)
        self._write_native(settings)
        wrote = any(settings.get(key) for key in ("startup_config_content", "private_config_content"))
        if wrote and journal_path(self.node).exists():
            # A direct import takes over from a pending preparation: it is not withdrawn with it.
            preparation.forget(self.node)
        if imports:
            mark_legacy_import(self.node)

    def _write_native(self, settings):
        """The engine owns its native file/NVRAM encoding and placeholders."""
        for key in ("startup_config_content", "private_config_content"):
            if key not in settings:
                continue
            if self.engine == Engine.dynamips:
                if settings[key]:
                    path = (
                        self.node.startup_config_path
                        if key == "startup_config_content"
                        else self.node.private_config_path
                    )
                    self.node.manager._create_config(self.node, path, settings[key])
            else:
                setattr(self.node, key, settings[key])

    async def _apply_console(self, options):
        node = self.node
        instance = getattr(node, "_process", None)
        proxy = getattr(node, "_configuration_console_proxy", None)
        name = getattr(node, "name", None) or getattr(node, "id", "?")
        # A startup replay (wait_ready) is bounded as a whole: every attempt may
        # itself wait up to 600 s for the boot prompt, so attempts alone are no bound.
        deadline = clock() + APPLY_CONSOLE_DEADLINE if options.wait_ready else None
        last_retry = None
        # Only live applies take a slot. A startup replay mostly waits for its guest to boot, and its console
        # sessions are bounded where they run; holding a slot meanwhile would use up other nodes' deadlines.
        async with contextlib.nullcontext() if options.wait_ready else loop_limit("apply"):
            for attempt in range(MAX_APPLY_ATTEMPTS):
                if runtime_stopped_or_replaced(node, instance, proxy):
                    log.info("Startup configuration apply on %s abandoned: the node was stopped or replaced", name)
                    raise ConfigurationError("runtime_changed_during_capture")
                try:
                    remaining = None if deadline is None else deadline - clock()
                    if remaining is not None and remaining <= 0:
                        raise TimeoutError
                    async with asyncio.timeout(remaining):
                        await run_console_session(
                            node,
                            options.credentials,
                            device_type=options.device_type,
                            content=options.content,
                            wait_ready=options.wait_ready,
                            running=options.running,
                            deadline=STARTUP_SESSION_SECONDS
                            if options.wait_ready
                            else restore_deadline(options.content),
                        )
                    if attempt:
                        log.info("Startup configuration applied on %s after %d attempts", name, attempt + 1)
                    return
                except TimeoutError:
                    if deadline is None:
                        raise
                    log.warning(
                        "Startup configuration apply on %s timed out after %d s (last retry reason: %s)",
                        name,
                        APPLY_CONSOLE_DEADLINE,
                        last_retry or "none",
                    )
                    context = (
                        {"phase": "console-wait", "device_error": f"last retry: {last_retry}"} if last_retry else None
                    )
                    raise ConfigurationError("configuration_apply_timeout", context=context) from None
                except ConfigurationError as error:
                    retry = error.code == "capture_capacity_exhausted" or (
                        options.wait_ready and error.code in ("console_busy", "console_unavailable")
                    )
                    if not retry or attempt == MAX_APPLY_ATTEMPTS - 1:
                        log.warning(
                            "Startup configuration apply on %s failed: %s %s",
                            name,
                            error.code,
                            describe_failure(error.context),
                        )
                        raise
                    last_retry = error.code
                    if attempt % 30 == 0:
                        (log.warning if attempt else log.info)(
                            "Startup configuration apply on %s is waiting (%s), attempt %d: "
                            "close every console client of the node",
                            name,
                            error.code,
                            attempt + 1,
                        )
                    await asyncio.sleep(1)

    async def _check_native_ready(self):
        if self.node.status != "stopped":
            raise ConfigurationError("stop_required")
        if self.engine == Engine.dynamips:
            if self.node._hypervisor is None:
                raise ConfigurationError("hypervisor_unavailable")
            if await dynamips_query(self.node, "get_status") != ["0"]:
                raise ConfigurationError("stop_required")
        else:
            running = not await docker_stopped(self.node) if self.engine == Engine.docker else self.node.is_running()
            if running:
                raise ConfigurationError("stop_required")
            if type(self.node.application_id) is not int or not 1 <= self.node.application_id <= 65535:
                raise ConfigurationError("application_id_unavailable")

    async def _native_files(self):
        await self._check_native_ready()
        if self.engine == Engine.dynamips:
            startup, _ = await self._dynamips_files()
        else:
            relative = (
                Path("tmp/run") / f"nvram_{self.node.application_id:05d}"
                if self.engine == Engine.docker
                else Path(f"nvram_{self.node.application_id:05d}")
            )
            root = Path(self.node.working_dir).resolve(strict=True)
            snapshot = await asyncio.to_thread(stable_read, str(root), root / relative, MAX_NVRAM_BYTES)
            try:
                startup, _ = await asyncio.to_thread(decode_nvram, snapshot)
            except ValueError:
                raise ConfigurationError("invalid_nvram") from None
        try:
            await self._check_native_ready()
        except ConfigurationError:
            raise ConfigurationError("runtime_changed_during_capture") from None
        return (ExportFile(filename="startup-config.cfg", content=bytes(startup or b"")),)

    async def _dynamips_files(self):
        try:
            reply = await dynamips_query(self.node, "extract_config")
            if len(reply) != 1:
                raise ConfigurationError("configuration_unavailable")
            fields = reply[0].rsplit(" ", 2)[-2:]
            if len(fields) != 2 or any(not value.startswith("'") or not value.endswith("'") for value in fields):
                raise ConfigurationError("invalid_hypervisor_response")
            encoded = tuple(value[1:-1] for value in fields)
            if not encoded[0]:
                raise ConfigurationError("configuration_unavailable")
            if any(len(value) > (MAX_FILE_BYTES + 2) // 3 * 4 for value in encoded):
                raise ConfigurationError("configuration_too_large")
            return tuple(base64.b64decode(value, validate=True) for value in encoded)
        except ConfigurationError:
            raise
        except (DynamipsError, binascii.Error, TypeError, ValueError, IndexError):
            raise ConfigurationError("native_extraction_failed") from None

    async def _docker_files(self):
        entries = self.node.extra_configs or ()
        root = Path(self.node.working_dir).resolve(strict=True)
        if not entries and getattr(self.node, "_gns3_init", True) and is_frr_container(self.node):
            # What the router runs now while it is up; what it saved while it is stopped.
            if self.node.status == "started":
                content = await frr_running_config(self.node)
            elif frr_volume_persisted(self.node):
                content = await asyncio.to_thread(stable_read, str(root), root / FRR_CONFIG, MAX_FILE_BYTES)
            else:
                raise ConfigurationError("configuration_frr_volume_required")
            return (ExportFile(filename=FRR_CONFIG, content=content),)
        if not entries and getattr(self.node, "_gns3_init", True):
            # Generic Linux containers persist this built-in configuration via
            # /etc/network. Read the saved file, never synthesize a default or
            # claim to capture transient `ip`/`ifconfig` changes.
            content = await asyncio.to_thread(stable_read, str(root), root / "etc/network/interfaces", MAX_FILE_BYTES)
            return (ExportFile(filename="etc/network/interfaces", content=content),)
        if not 1 <= len(entries) <= 64:
            raise ConfigurationError("no_declared_files")
        volumes = set(self.node.extra_volumes or ()) | set(self.node._volumes or ())
        files = []
        for entry in entries:
            target = entry.get("target") if isinstance(entry, dict) else getattr(entry, "target", None)
            if not isinstance(target, str) or not target.startswith("/"):
                raise ConfigurationError("invalid_declared_files")
            # Validate before constructing any host path. Only extra_configs
            # binds owned by the engine are eligible; volumes may shadow them.
            try:
                filename = ExportFile.safe_filename(target[1:])
            except ValueError:
                raise ConfigurationError("invalid_declared_files") from None
            if any(target == volume or target.startswith(volume.rstrip("/") + "/") for volume in volumes):
                raise ConfigurationError("configuration_mount_shadowed")
            content = await asyncio.to_thread(stable_read, str(root), root / "configs" / filename, MAX_FILE_BYTES)
            files.append(ExportFile(filename=filename, content=content))
        return tuple(files)


def restore_network_file(node, content):
    if not getattr(node, "_gns3_init", True) or node.extra_configs:
        raise ConfigurationError("configuration_apply_unsupported")
    if node.status != "stopped":
        raise ConfigurationError("stop_required")
    atomic_write(node.working_dir, "etc/network/interfaces", content)


IOU_GENERATED_FILE = re.compile(r"nvram_[0-9]{5}|vlan\.dat-[0-9]{5}")


def is_frr_container(node):
    return is_frr_node(
        getattr(node, "console_type", None), getattr(node, "environment", None), getattr(node, "_image", None)
    )


def frr_volume_persisted(node):
    """``/etc/frr`` is a volume of the image or of the node, so its files are kept in the node folder."""
    return any(
        FRR_VOLUME == volume or FRR_VOLUME.startswith(volume.rstrip("/") + "/")
        for volume in getattr(node, "_volumes", None) or ()
    )


def restore_frr_config(node, content):
    if not is_frr_container(node) or not getattr(node, "_gns3_init", True) or node.extra_configs:
        raise ConfigurationError("configuration_apply_unsupported")
    if node.status != "stopped":
        raise ConfigurationError("stop_required")
    if not frr_volume_persisted(node):
        raise ConfigurationError("configuration_frr_volume_required")
    atomic_write(node.working_dir, FRR_STAGED_CONFIG, content)


async def frr_running_config(node):
    """``show running-config`` of a running FRR container; reads only, nothing is saved in the guest."""
    try:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "exec",
            node._cid,
            "vtysh",
            "-c",
            "show running-config",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        raise ConfigurationError("configuration_read_failed") from None
    try:
        async with asyncio.timeout(FRR_SHOW_SECONDS):
            output = bytearray()
            while chunk := await process.stdout.read(65536):
                output.extend(chunk)
                if len(output) > MAX_FILE_BYTES:
                    process.kill()
                    await process.wait()
                    raise ConfigurationError("configuration_too_large")
            await process.wait()
            output = bytes(output)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise ConfigurationError("configuration_capture_timeout") from None
    # The listing starts with "Building configuration..." and ends with "end"; anything else is a daemon
    # that is not up yet.
    _, found, listing = output.decode("utf-8", errors="replace").partition("Current configuration:\n")
    if process.returncode != 0 or not found or not listing.rstrip().endswith("end"):
        raise ConfigurationError("console_not_ready")
    if len(listing) > MAX_FILE_BYTES:
        raise ConfigurationError("configuration_too_large")
    return listing.encode("utf-8")


def _wipe_paths(node, engine, root):
    if engine == "dynamips":
        # The router names its files below the folder as it knows it, which may go through a link.
        folder = Path(node.working_dir).absolute()
        paths = [Path(node.startup_config_path), Path(node.private_config_path)]
        paths = [root / path.relative_to(folder) if path.is_relative_to(folder) else path for path in paths]
        paths.append(root / f"{node.platform}_i{node.dynamips_id}_nvram")
    elif engine == "iou":
        paths = [root / "startup-config.cfg", root / "private-config.cfg"]
        # Application identifiers can change after a project is reopened.
        candidates = [*root.glob("nvram_*"), *root.glob("vlan.dat-*")]
        paths += [path for path in candidates if IOU_GENERATED_FILE.fullmatch(path.name)]
    elif engine == "vpcs":
        paths = [root / "startup.vpc"]
    elif engine == "docker":
        if (
            not getattr(node, "_gns3_init", True)
            or node.extra_configs
            or not docker_network_file(getattr(node, "netmiko_device_type", None))
        ):
            raise ConfigurationError("configuration_wipe_unsupported")
        paths = [root / "etc/network/interfaces"]
        if is_frr_container(node) and frr_volume_persisted(node):
            # Without a saved file FRR starts with an empty configuration.
            paths += [root / FRR_CONFIG, root / FRR_STAGED_CONFIG, root / (FRR_CONFIG + ".sav")]
    elif engine == "qemu":
        paths = _qemu_wipe_overlays(node, root)
        # Wipe resets per-node firmware NVRAM too. Keeping an old boot
        # entry after changing disk interfaces can strand UEFI in its shell.
        # Include absent paths so broken symlinks are validated as well.
        paths += [root / name for name in ("OVMF_VARS.fd", "OVMF_VARS_4M.fd", "AAVMF_VARS.fd")]
        paths += wipe_paths(root)
        # A factory reset: the config disk the guest writes to, its saved copy and the vTPM state go too.
        paths += [root / "config.img", root / "config.zip"]
        paths += _tpm_state_files(root)
        _refuse_extra_storage(node, root, paths)
    else:
        raise ConfigurationError("configuration_wipe_unsupported")
    return paths


def _tpm_state_files(root):
    directory = root / "tpm"
    if directory.is_symlink():
        raise ConfigurationError("unsafe_configuration_path")
    return sorted(directory.iterdir()) if directory.is_dir() else []


# QEMU flags whose argument is a disk image the guest can write.
DISK_FLAGS = frozenset({"-hda", "-hdb", "-hdc", "-hdd", "-fda", "-fdb", "-sd", "-mtdblock", "-pflash"})


def _drive_keys(value):
    """The ``key=value`` parts of a ``-drive`` argument; QEMU writes a literal comma as ``,,``."""
    keys = {}
    for part in re.split(r"(?<!,),(?!,)", value):
        key, _, text = part.partition("=")
        keys[key] = text.replace(",,", ",")
    return keys


def _written_files(options):
    """Files the additional QEMU options let the guest write to."""
    try:
        arguments = shlex.split(options)
    except ValueError:
        raise ConfigurationError("configuration_extra_storage") from None
    if "-snapshot" in arguments:
        return []
    files = []
    for flag, value in itertools.pairwise(arguments):
        flag = flag[1:] if flag.startswith("--") else flag
        if flag in DISK_FLAGS:
            files.append(value)
        elif flag == "-drive":
            keys = _drive_keys(value)
            discarded = (
                keys.get("readonly") in ("", "on") or keys.get("snapshot") == "on" or keys.get("media") == "cdrom"
            )
            if keys.get("file") and not discarded:
                files.append(keys["file"])
        elif flag == "-blockdev" and "filename" in value:
            if "read-only=on" not in value and not re.search(r'"read-only"\s*:\s*true', value):
                files.append(value)
    return files


def _refuse_extra_storage(node, root, reset_paths):
    """A disk added through the options keeps the guest's data, so such a node cannot be reset."""
    for name in _written_files(getattr(node, "options", "") or ""):
        # QEMU resolves relative names against the node folder.
        if root / name not in reset_paths:
            raise ConfigurationError("configuration_extra_storage")


def _qemu_wipe_overlays(node, root):
    if not node.linked_clone:
        raise ConfigurationError("configuration_wipe_unsupported")
    paths = []
    for drive in "abcd":
        if drive == "d" and node.create_config_disk:
            continue
        image = getattr(node, f"_hd{drive}_disk_image")
        if not image:
            continue
        # A project-local disk may be the only copy of an imported image.
        # Only the separate, generated linked-clone overlays are disposable.
        base = Path(image).resolve(strict=True)
        if base.is_relative_to(root):
            raise ConfigurationError("configuration_wipe_unsupported")
        paths.append(root / f"hd{drive}_disk.qcow2")
    if not paths:
        raise ConfigurationError("configuration_wipe_unsupported")
    return paths


def _plan_wipe(node, engine):
    """The files a wipe of this node removes, after checking that every one of them is the node's own."""
    try:
        directory = Path(node.working_dir)
        if directory.is_symlink() or ".." in directory.parts:
            raise ConfigurationError("unsafe_configuration_path")
        root = directory.resolve(strict=True)
        paths = _wipe_paths(node, engine, root)
        validate_owned_paths(root, [root / journal_path(node).name, *paths])
    except OSError:
        raise ConfigurationError("configuration_wipe_failed") from None
    return paths


def wipe_configuration(node, engine):
    # Validation and unlinking are one blocking section (run via to_thread by the
    # service): the stopped-state check and the deletes happen under the lease.
    require_stopped(node)
    paths = _plan_wipe(node, engine)
    try:
        # The files go one by one. A failure in between must not leave a node that looks as if it booted
        # normally: Start refuses it until the wipe is repeated, which finishes the job (a gone file is fine).
        set_runtime_state(node, "resetting")
        for path in paths:
            path.unlink(missing_ok=True)
    except OSError:
        raise ConfigurationError("configuration_wipe_failed") from None


def _wipe_runtime(node, engine):
    wipe_configuration(node, engine)
    mark_wiped(node)
