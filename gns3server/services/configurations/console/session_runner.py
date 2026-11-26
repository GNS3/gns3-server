"""Run one console session (capture or startup restore) for a node, in an isolated subprocess.

The compute leases the node's console from its proxy, bridges it to a loopback port and starts
``session`` as a child process that does the blocking Telnet session. This module owns everything around
that child: admission limits, deadlines, cancellation, noticing that the node stopped or was replaced, reaping the
child, and recovering the console transport when a session ends in an uncertain state.
"""

import asyncio
import base64
import binascii
import contextlib
import json
import logging
import sys

from gns3server.schemas.configurations import CONSOLE_DEVICE_TYPES, ConsoleCredentials, normalize_device_type
from gns3server.services.configurations.shared.node_lease import (
    node_lease,
    runtime_replaced,
    runtime_stopped_or_replaced,
)
from gns3server.utils.asyncio import loop_limit, saturated
from gns3server.utils.asyncio.console_lease import ConsoleLeaseError
from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer

from ..shared.errors import AUTHENTICATION_FAILURES, CAPTURE_FAILURES, WORKER_ERRORS, ConfigurationError
from ..shared.failure_context import mask_text
from .platforms import get_platform
from .prompts import ANSI_CSI

log = logging.getLogger(__name__)

MAX_CONSOLE_BYTES = 2 * 1024 * 1024
MAX_WORKER_BYTES = 3 * 1024 * 1024
CONSOLE_RECOVERY_TIMEOUT = 5


async def _complete(awaitable, *, defer_cancellation=False):
    """Keep ownership until cleanup/spawn finishes despite repeated cancellation."""
    task = asyncio.create_task(awaitable)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    result = task.result()
    if cancelled and not defer_cancellation:
        raise asyncio.CancelledError
    return (result, cancelled) if defer_cancellation else result


async def _stop_worker(process):
    async def discard_output():
        while await process.stdout.read(64 * 1024):
            pass

    # A malformed/flooding child can fill asyncio's pipe buffer. Drain without
    # retaining or logging data so wait() can observe EOF after termination.
    drain = asyncio.create_task(discard_output())
    try:
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=1)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                await process.wait()
    finally:
        await drain


async def _drain_cleanup(process, listener):
    async def stop():
        try:
            if process is not None:
                await _stop_worker(process)
        finally:
            listener.close()
            await listener.wait_closed()

    await _complete(stop())


async def _spawn_worker():
    # Defer cancellation until the caller owns and can reap a newly spawned child.
    return await _complete(
        asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "gns3server.services.configurations.console.session",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        ),
        defer_cancellation=True,
    )


async def _recover_console_transport(node, proxy, instance):
    """Use the node's normal reset operation after its export worker is gone.

    Never reset a replacement runtime or somebody else's console connection.
    Repeated request cancellation must not abandon transport recovery halfway.
    """

    def still_owned():
        return node.status == "started" and getattr(node, "_process", None) is instance

    async def reconnect():
        reset = getattr(node, "reset_console", None)
        if not callable(reset) or not still_owned() or node._configuration_console_proxy is not proxy:
            return False
        try:
            async with asyncio.timeout(CONSOLE_RECOVERY_TIMEOUT):
                await reset()
        except Exception:
            # Some reset implementations clear the reference before reconnecting.
            # Retain a blocked reference for the existing manual-recovery path.
            if still_owned() and node._configuration_console_proxy is None:
                node._configuration_console_proxy = proxy
            return False
        current = node._configuration_console_proxy
        if current is None and still_owned():
            node._configuration_console_proxy = proxy
        return current is not None and current is not proxy and not current._console_recovery_required

    return await _complete(reconnect())


async def _finish_session(process, listener, node, proxy, instance, needs_recovery):
    try:
        await _drain_cleanup(process, listener)
    finally:
        if needs_recovery and (process is None or process.returncode is not None):
            await _recover_console_transport(node, proxy, instance)


def _readiness_context(readiness):
    """The last two console lines seen while waiting, masked and bounded."""
    text = readiness.tail.decode("utf-8", errors="ignore").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ANSI_CSI.sub("", line).strip() for line in text.split("\n")]
    lines = [mask_text(line, 120) for line in lines if line.strip()][-2:]
    return {"phase": "ready", "device_error": " | ".join(lines)}


async def wait_for_console_ready(node, device_type, deadline, *, startup=False):
    """Wait for an actionable, quiet guest prompt without reserving the console."""
    if startup:
        return await _wait_for_startup_console(
            node,
            device_type,
            deadline,
            getattr(node, "_process", None),
            getattr(node, "_configuration_console_proxy", None),
        )
    if node.status != "started":
        raise ConfigurationError("start_required")
    proxy = getattr(node, "_configuration_console_proxy", None)
    readiness = getattr(proxy, "_console_readiness", None)
    if node.console_type not in ("telnet", "ssh") or readiness is None:
        raise ConfigurationError("console_lease_unsupported")
    instance = getattr(node, "_process", None)
    try:
        platform = get_platform(device_type)
        await readiness.wait_for(platform.console_ready, deadline, settle_seconds=1)
    except TimeoutError:
        context = _readiness_context(readiness)
        log.warning(
            "Console of %s was not ready after %s s: %s",
            getattr(node, "name", None) or getattr(node, "id", "?"),
            deadline,
            context["device_error"] or "(no console output)",
        )
        raise ConfigurationError("configuration_apply_timeout", context=context) from None
    except ConsoleLeaseError as error:
        raise ConfigurationError(str(error)) from None
    if runtime_stopped_or_replaced(node, instance, proxy):
        raise ConfigurationError("runtime_changed_during_capture")


def _check_startup_runtime(node, instance, proxy):
    if runtime_replaced(node, instance, proxy):
        raise ConfigurationError("runtime_changed_during_capture")


async def _wait_for_startup_console(node, device_type, deadline, instance, proxy):
    # Retire obsolete console work promptly when the guest process or its
    # console proxy is replaced, even if the guest stays silent during its boot.
    _check_startup_runtime(node, instance, proxy)
    ready = asyncio.create_task(wait_for_console_ready(node, device_type, deadline))
    try:
        while not ready.done():
            await asyncio.wait({ready}, timeout=0.2)
            _check_startup_runtime(node, instance, proxy)
        await ready
    finally:
        ready.cancel()
        await asyncio.gather(ready, return_exceptions=True)


async def run_console_session(
    node,
    credentials: ConsoleCredentials,
    *,
    device_type: str = "cisco_ios_telnet",
    deadline: float = 25,
    backup: bool = False,
    content: str | None = None,
    wait_ready: bool = False,
    running: bool = False,
    save: bool = False,
) -> bytes:
    device_type = normalize_device_type(device_type)
    if device_type not in CONSOLE_DEVICE_TYPES:
        raise ConfigurationError("device_type_unsupported")
    if not 0 < deadline <= (600 if content is not None else 30):
        raise ValueError("Invalid console deadline")
    automatic = wait_ready and content is not None and not running
    instance = getattr(node, "_process", None)
    proxy = getattr(node, "_configuration_console_proxy", None)
    if wait_ready and content is not None:
        await wait_for_console_ready(node, device_type, deadline, startup=automatic)
    if save:
        if content is not None:
            raise ValueError("Save and restore are mutually exclusive")
        # Refuse before touching guest state when the platform declares no
        # tested way to persist its running configuration.
        if not get_platform(device_type).supports_save:
            raise ConfigurationError("configuration_save_unsupported")
    if saturated("console-capture"):
        raise ConfigurationError("capture_capacity_exhausted")
    async with loop_limit("console-capture"):
        async with node_lease(node) if automatic else contextlib.nullcontext():
            if automatic:
                # Configure may have selected native media while this job was
                # observing boot. Never replay the old upload into that guest.
                _check_startup_runtime(node, instance, proxy)
            return await _run_leased_session(
                node,
                credentials,
                device_type=device_type,
                deadline=deadline,
                backup=backup,
                content=content,
                wait_ready=wait_ready,
                save=save,
            )


async def _read_result(process):
    length = int.from_bytes(await process.stdout.readexactly(4), "big")
    if not 0 < length <= MAX_WORKER_BYTES:
        raise ConfigurationError("console_output_limit")
    reply = json.loads(await process.stdout.readexactly(length))
    if await process.stdout.read(1) or await process.wait() != 0:
        raise ConfigurationError("console_capture_failed")
    if "error" in reply:
        code = reply["error"]
        raise ConfigurationError(
            code if code in WORKER_ERRORS else "console_capture_failed",
            console_reusable=(reply.get("console_reusable") is True and code in AUTHENTICATION_FAILURES),
            context=reply.get("context"),
        )
    content = base64.b64decode(reply["content_base64"], validate=True)
    if not content or len(content) > MAX_CONSOLE_BYTES:
        raise ConfigurationError("console_output_limit")
    return content


async def _owned_result(process, node, instance, proxy):
    result = asyncio.create_task(_read_result(process))
    try:
        while not result.done():
            await asyncio.wait({result}, timeout=0.2)
            if runtime_stopped_or_replaced(node, instance, proxy):
                raise ConfigurationError("runtime_changed_during_capture")
        return result.result()
    finally:
        if not result.done():
            result.cancel()
        await asyncio.gather(result, return_exceptions=True)


PREFLIGHT_REFUSALS = frozenset({"console_unsafe_mode", "console_not_ready", "console_authentication_failed"})


def _needs_recovery(lease, error, failure, complete):
    """Whether the console transport must be recreated after this session.

    True when the session wrote to the guest and did not finish cleanly. A preflight refusal, or an
    authentication prompt the worker confirmed, leaves the guest at a prompt a user can still use.
    """
    if complete or lease.written_bytes <= 0:
        return False
    safe_preflight = lease.probe_only and isinstance(failure, str) and failure in PREFLIGHT_REFUSALS
    safe_authentication = (
        lease.error is None
        and isinstance(error, ConfigurationError)
        and error.console_reusable
        and isinstance(failure, str)
        and failure in AUTHENTICATION_FAILURES
    )
    return not (safe_preflight or safe_authentication)


async def _run_leased_session(
    node,
    credentials: ConsoleCredentials,
    *,
    device_type: str,
    deadline: float,
    backup=False,
    content=None,
    wait_ready=False,
    save=False,
) -> bytes:
    """Run the session (a capture, or a replay when ``content`` is given) under an exclusive console lease.

    The endpoint is resolved entirely from the owning compute's node/proxy.
    An ephemeral loopback bridge gives the subprocess access only while that
    proxy holds an exclusive lease. Callers cannot choose hosts or commands.
    Commands are fixed server-side, never supplied by a client.
    """
    if node.status != "started":
        raise ConfigurationError("start_required")
    proxy = getattr(node, "_configuration_console_proxy", None)
    if node.console_type not in ("telnet", "ssh") or proxy is None:
        raise ConfigurationError("console_lease_unsupported")
    instance = getattr(node, "_process", None)
    try:
        async with proxy.lease_console(max_bytes=MAX_CONSOLE_BYTES * (4 if content is not None else 1)) as lease:
            bridge = AsyncioTelnetServer(reader=lease.reader, writer=lease, keepalive_interval=0)
            listener = await bridge.start("127.0.0.1", 0)
            process = None
            complete = False
            try:
                async with asyncio.timeout(deadline):
                    process, cancelled = await _spawn_worker()
                    if cancelled:
                        raise asyncio.CancelledError
                    payload = {
                        "device_type": device_type,
                        "port": listener.sockets[0].getsockname()[1],
                        "username": credentials.username,
                        "password": credentials.password.get_secret_value(),
                        "enable_secret": credentials.enable_secret.get_secret_value(),
                    }
                    if backup:
                        payload["backup"] = True
                    if save:
                        payload["save"] = True
                    if content is not None:
                        payload.update(content=content, wait_ready=wait_ready)
                    process.stdin.write(json.dumps(payload).encode())
                    await process.stdin.drain()
                    process.stdin.close()
                    content = await _owned_result(process, node, instance, proxy)
                    if runtime_stopped_or_replaced(node, instance, proxy):
                        raise ConfigurationError("runtime_changed_during_capture")
                    complete = True
                    return content
            except TimeoutError:
                raise ConfigurationError("configuration_capture_timeout") from None
            except ConfigurationError:
                if lease.error is not None:
                    raise ConfigurationError(str(lease.error)) from None
                raise
            except ConsoleLeaseError:
                raise
            except (ValueError, KeyError, TypeError, binascii.Error, asyncio.IncompleteReadError, OSError):
                raise ConfigurationError(str(lease.error) if lease.error else "console_capture_failed") from None
            finally:
                error = sys.exception()
                failure = str(lease.error) if lease.error else getattr(error, "code", None)
                needs_recovery = _needs_recovery(lease, error, failure, complete)
                if needs_recovery:
                    # A killed worker does not imply the guest finished emitting
                    # sensitive output. Block admission until a fresh transport
                    # is created; never hand this uncertain session to a client.
                    proxy._console_recovery_required = True
                    proxy._configuration_capture_failure = (
                        failure
                        if isinstance(failure, str) and failure in CAPTURE_FAILURES
                        else "console_capture_failed"
                    )
                # A preflight refusal or worker-confirmed authentication prompt
                # can return to the user. Keep the lease until the worker is
                # reaped; timeouts/cancellation never take this shortcut.
                await _finish_session(process, listener, node, proxy, instance, needs_recovery)
    except ConsoleLeaseError as error:
        previous = getattr(proxy, "_configuration_capture_failure", None)
        raise ConfigurationError(
            str(error),
            previous_error=(
                previous
                if str(error) == "console_recovery_required"
                and isinstance(previous, str)
                and previous in CAPTURE_FAILURES
                else None
            ),
        ) from None
