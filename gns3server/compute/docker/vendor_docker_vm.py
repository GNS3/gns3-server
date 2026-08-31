#
# Copyright (C) 2025 GNS3 Technologies Inc.
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
Vendor NOS Docker container subclass.

Provides support for vendor NOS containers (Nokia SR Linux, Arista cEOS,
Juniper cRPD, …) whose CLI is a separate TUI process not exposed on PID 1
stdio, and whose boot model requires skipping GNS3's init.sh bootstrapping.

The subclass is selected automatically when ``console_type == "docker_exec"``.
All vendor features are opt-in — without GNS3_* environment variables the
container behaves identically to DockerVM.
"""

import asyncio
import contextlib
import json
import logging
import os
import shutil

from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer
from gns3server.compute.docker.docker_vm import DockerVM
from gns3server.compute.docker.docker_error import DockerError, DockerHttp304Error, DockerHttp404Error

log = logging.getLogger(__name__)


class VendorDockerVM(DockerVM):
    """
    DockerVM subclass for vendor NOS containers.

    Opt-in features, activated by GNS3_-prefixed environment entries
    (host-side only — GNS3_ entries are never forwarded into the container):

    * ``GNS3_SKIP_INIT=1`` — do not prepend /gns3/init.sh; the container runs
      its own entrypoint (e.g. SR Linux's ``sr_linux``). Persistent volumes
      are seeded host-side and bound directly at their real in-container
      paths at create time (see ``_prepare_volumes`` / ``_mount_binds``), so
      the NOS sees its saved configuration from the very first process —
      no post-start mount pass that could race the NOS reading its config.
    * ``GNS3_INTERFACE_NAMES=mgmt0,e1-1,e1-2`` — rename injected interfaces
      (adapter order) instead of default ``eth{N}``.
    * ``GNS3_CONSOLE_CMD=/opt/srlinux/bin/sr_cli`` — command run inside the
      container by the ``docker_exec`` console (defaults to ``/bin/sh``).
    * ``GNS3_CONSOLE_RESIZE=0`` — ignore client-driven console resizes
      (WS terminal-size frames / telnet NAWS). Set for CLIs that page on the
      PTY window size (IOS-XR): the exec PTY must stay at the tall
      no-NAWS default for every client, including concurrent netmiko
      sessions on the shared exec.
    * ``GNS3_STOP_TIMEOUT=60`` — SIGTERM grace period in seconds when stopping
      the container (default 60; Docker SIGKILLs once it expires).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._console_exec_writer = None
        # Parsed eagerly so _get_container_ifname can return the right name,
        # and re-parsed on every create() so a PUT to the node's environment
        # takes effect on the next (re)create instead of the next reload.
        self._parse_vendor_environment()

    def _parse_vendor_environment(self):
        """
        (Re)parse the GNS3_* knobs from the current ``environment`` value,
        resetting to defaults first so removed entries stop applying.
        """

        self._gns3_init = True
        self._interface_names = []
        self._console_cmd = None
        self._console_resize = True
        self._stop_timeout = 60
        if self._environment:
            for _line in self._environment.splitlines():
                _line = _line.strip().rstrip(",")
                if _line.startswith("GNS3_SKIP_INIT="):
                    self._gns3_init = _line.split("=", 1)[1].strip().lower() not in ("1", "true", "yes")
                elif _line.startswith("GNS3_INTERFACE_NAMES="):
                    self._interface_names = [
                        n.strip() for n in _line.split("=", 1)[1].split(",") if n.strip()
                    ]
                elif _line.startswith("GNS3_CONSOLE_CMD="):
                    self._console_cmd = _line.split("=", 1)[1].strip()
                elif _line.startswith("GNS3_CONSOLE_RESIZE="):
                    self._console_resize = _line.split("=", 1)[1].strip().lower() not in ("0", "false", "no")
                elif _line.startswith("GNS3_STOP_TIMEOUT="):
                    try:
                        timeout = int(_line.split("=", 1)[1].strip())
                        # Ceiling is derived from the call chain, not arbitrary:
                        # the controller's stop request times out at 240 s
                        # (controller/node.py) and the Docker stop query gets
                        # this value +30 s as its HTTP timeout — so anything
                        # above 210 would abort upstream first.
                        if 1 <= timeout <= 210:
                            self._stop_timeout = timeout
                    except ValueError:
                        pass

    async def create(self):
        # The environment may have changed since __init__ (PUT on the node) —
        # re-parse the knobs so the recreated container picks them up.
        self._parse_vendor_environment()
        return await super().create()

    # ---- hook overrides ---------------------------------------------------

    def _mount_binds(self, image_info):
        """
        Override: for SKIP_INIT containers, drop GNS3's hardcoded
        /etc/network volume. It holds GNS3's own network config consumed by
        init.sh's `ifup`; init.sh never runs for SKIP_INIT containers (the
        NOS manages its own interfaces), so the mount would be dead weight.
        Removes the bind, drops the volume from self._volumes (so
        GNS3_VOLUMES and the vendor passes stay consistent) and deletes the
        host-side skeleton directory the base class just created.

        Additionally, the persistent volumes are bound directly at their
        real in-container paths instead of /gns3volumes<volume>. With
        init.sh skipped there is no in-container mount pass, so a volume
        bound at /gns3volumes would only be moved into place by a post-start
        ``docker exec`` — racing the NOS reading its startup configuration
        (an SR Linux node booted factory whenever the exec lost that race,
        e.g. on the concurrent node starts of a project reload). Binding at
        the real path is safe because the content is seeded host-side before
        the container is created (see _prepare_volumes): the image's files
        are never shadowed by an empty mount.
        """
        binds = super()._mount_binds(image_info)
        if self._gns3_init:
            return binds
        binds = [b for b in binds if b.get("Target") != "/gns3volumes/etc/network"]
        self._volumes = [v for v in self._volumes if v != "/etc/network"]
        shutil.rmtree(os.path.join(self.working_dir, "etc", "network"), ignore_errors=True)
        with contextlib.suppress(OSError):
            os.rmdir(os.path.join(self.working_dir, "etc"))

        # Re-target the volume binds from /gns3volumes<volume> to <volume>.
        retargeted = []
        for bind in binds:
            target = bind.get("Target", "")
            if target.startswith("/gns3volumes"):
                volume = target[len("/gns3volumes"):]
                if volume in self._volumes:
                    bind = {**bind, "Target": volume}
            retargeted.append(bind)
        return retargeted

    async def _prepare_volumes(self, image_info):
        """
        Override: for SKIP_INIT containers, seed every persistent volume's
        host directory with the image's original content *before* the
        container is created. This is the host-side replacement of init.sh's
        first-copy: because the volume is then bound directly at its real
        in-container path (see _mount_binds), the seed must exist first or
        the NOS would boot with an empty config directory.

        ``.gns3_perms`` doubles as the seeded marker: a volume that has it
        (every node that ever started, on any GNS3 version) is never
        re-seeded — a re-seed would overwrite the node's saved
        configuration with the factory image content.
        """
        if self._gns3_init:
            return
        volumes = self._persistent_volume_list(image_info, include_network_config=False)
        to_seed = []
        for volume in volumes:
            host_dir = os.path.join(self.working_dir, os.path.relpath(volume, "/"))
            os.makedirs(host_dir, exist_ok=True)
            if not os.path.exists(os.path.join(host_dir, ".gns3_perms")):
                to_seed.append((volume, host_dir))
        if not to_seed:
            return
        seed_cid = await self._create_seed_container()
        try:
            for volume, host_dir in to_seed:
                await self._seed_volume_from_container(seed_cid, volume, host_dir)
                # Write the marker only after the copy attempt, mirroring
                # init.sh: a volume without it is (re)seeded on the next
                # create(), so a partial seed self-heals.
                open(os.path.join(host_dir, ".gns3_perms"), "a").close()
        finally:
            await self._remove_seed_container(seed_cid)

    async def _create_seed_container(self):
        """
        A throwaway ``docker create`` container (nothing executes) used as
        the copy source for seeding persistent volumes with the image's
        original content.
        """

        try:
            process = await asyncio.subprocess.create_subprocess_exec(
                "docker", "create", self._image,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
        except OSError as e:
            raise DockerError(f"Could not seed persistent volumes for '{self._name}': {e}")
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise DockerError(
                f"Could not create a seeding container for image '{self._image}': "
                f"{stderr.decode(errors='replace').strip()}"
            )
        return stdout.decode().strip()

    async def _seed_volume_from_container(self, seed_cid, volume, host_dir):
        """
        Copy one volume's original content from the seeding container to its
        host directory with ``docker cp -a`` (preserves modes/ownership; no
        dependency on tools inside the image).
        """

        try:
            process = await asyncio.subprocess.create_subprocess_exec(
                "docker", "cp", "-a", f"{seed_cid}:{volume}/.", host_dir + "/",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
        except OSError as e:
            raise DockerError(f"Could not seed persistent volume '{volume}' for '{self._name}': {e}")
        _, stderr = await process.communicate()
        if process.returncode != 0:
            # A path the image does not contain (e.g. XRd's /xr-storage-shadow)
            # is not an error: the volume starts empty. Same tolerance as
            # init.sh's first copy (cp -a ... 2>/dev/null).
            log.info(
                "Persistent volume '%s' on '%s' not seedable from image '%s' (%s); starting empty",
                volume, self._name, self._image, stderr.decode(errors="replace").strip(),
            )
            return
        log.info("Seeded persistent volume '%s' for '%s' from image '%s'", volume, self._name, self._image)

    async def _remove_seed_container(self, seed_cid):
        """
        Best-effort removal of the seeding container.
        """

        try:
            process = await asyncio.subprocess.create_subprocess_exec(
                "docker", "rm", "-f", seed_cid,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
        except OSError:
            return
        await process.communicate()

    def _prepare_init_and_interface_env(self, params):
        """
        Override: conditionally prepend init.sh, and honour
        GNS3_INTERFACE_NAMES (if set) for GNS3_MAX_ETHERNET.
        """
        if self._gns3_init:
            params["Entrypoint"].insert(0, "/gns3/init.sh")

        # Tell init.sh which last interface to wait for; honour the rename if any
        # (no-op when init is skipped, but kept consistent).
        if self._interface_names and self.adapters - 1 < len(self._interface_names):
            last_ifname = self._interface_names[self.adapters - 1]
        else:
            last_ifname = f"eth{self.adapters - 1}"
        params["Env"].append(f"GNS3_MAX_ETHERNET={last_ifname}")

    def _get_container_ifname(self, adapter_number):
        """
        Override: honour GNS3_INTERFACE_NAMES (e.g. mgmt0, e1-1) in adapter
        order; fall back to eth{N} for unlisted ports.
        """
        if self._interface_names and adapter_number < len(self._interface_names):
            return self._interface_names[adapter_number]
        return f"eth{adapter_number}"

    def _cleanup_console_resources(self):
        """
        Override: close the docker-exec pty socket, if any, so the next
        restart or stop doesn't leak it.
        """
        if self._console_exec_writer:
            try:
                self._console_exec_writer.close()
            except Exception:
                pass
            self._console_exec_writer = None

    async def _terminate_container(self, graceful: bool = False):
        """
        Override: vendor NOS containers run systemd and require a graceful
        shutdown (e.g. Cisco XRd treats an abrupt SIGKILL as an unclean
        shutdown).

        With ``graceful`` (explicit user stop), send SIGTERM and wait up to
        ``GNS3_STOP_TIMEOUT`` seconds (default 60, 1-210 — the ceiling keeps
        the +30 s HTTP margin inside the controller's 240 s stop budget) for
        the services to stop; Docker SIGKILLs the container itself once the
        grace period expires, so no fallback kill is needed.

        Without ``graceful`` (delete/update/close/crash cleanup), fall back to
        the base immediate kill: those paths force-delete or recreate the
        container right after anyway, so a grace period buys nothing but
        latency.
        """
        if not graceful:
            await super()._terminate_container(graceful=False)
            return
        try:
            response = await self.manager.http_query(
                "POST",
                f"containers/{self._cid}/stop",
                params={"t": self._stop_timeout},
                timeout=self._stop_timeout + 30,
            )
            response.close()
        except DockerHttp304Error:
            pass  # already stopped

    async def start(self):
        await super().start()
        if self.status == "started" and not self._gns3_init:
            # Persistent volumes are seeded and bound directly at create time
            # (see _prepare_volumes / _mount_binds), so there is no post-start
            # bridge to run. Fix host-side ownership right away so the
            # controller can read project files while the node runs, and reset
            # the "fixed" flag: files written by the container during runtime
            # still need the stop-time pass.
            await self._fix_permissions()
            self._permissions_fixed = False

    async def _fix_permissions(self):
        """
        Container-side override of DockerVM._fix_permissions for vendor NOS
        containers. The persistent volumes are Docker bind mounts created
        with the container (see _mount_binds), so the in-container paths
        resolve to the host-side files for the container's whole lifetime —
        no /gns3volumes aliasing is needed.

        The busybox script runs inside the container as root (a host-side
        GNS3 process may be unprivileged and cannot chown root-owned files).

        Unlike the base implementation, a stopped/exited container is NOT
        restarted just to fix permissions (vendor NOS images are heavy to
        boot): the pass is skipped and the next start fixes ownership.
        """
        try:
            state = await self._get_container_state()
        except DockerHttp404Error:
            log.warning("Container '%s' does not exist, skipping permission fix", self._name)
            return
        if state == "stopped" or state == "exited":
            log.info(
                "Container '%s' is %s, skipping permission fix (next start will fix)",
                self._name, state,
            )
            return

        uid, gid = os.getuid(), os.getgid()
        for volume in self._volumes:
            target = volume
            log.debug("Docker container '%s' fix ownership on %s", self._name, target)
            try:
                # chown prefers the container's own coreutils over /gns3/bin/busybox:
                # busybox is static, and its chown dlopens NSS modules from the
                # container, which mismatch the static glibc and abort (glibc
                # "sym != NULL") on NOS images whose glibc differs from the host's
                # (e.g. Cisco XRd). It falls back to busybox on minimal images that
                # ship no chown. cp/chmod/find/stat don't use NSS, so stay busybox.
                process = await asyncio.subprocess.create_subprocess_exec(
                    "docker",
                    "exec",
                    self._cid,
                    "/gns3/bin/busybox",
                    "sh",
                    "-c",
                    "("
                    f'/gns3/bin/busybox find "{target}" -depth -print0'
                    f" | /gns3/bin/busybox xargs -0 /gns3/bin/busybox stat -c '%a:%u:%g:%n' > \"{target}/.gns3_perms\""
                    ")"
                    f' && /gns3/bin/busybox chmod -R u+rX "{target}"'
                    f' && ( command -v chown >/dev/null 2>&1 && chown {uid}:{gid} -R "{target}" || /gns3/bin/busybox chown {uid}:{gid} -R "{target}" )',
                    stderr=asyncio.subprocess.PIPE,
                )
            except OSError as e:
                raise DockerError(f"Could not fix permissions for {volume}: {e}")
            await process.wait()
            if process.returncode != 0:
                stderr = (await process.stderr.read()).decode(errors="replace").strip()
                log.error(
                    "Failed to fix permissions on '%s' for container '%s': %s",
                    volume, self._name, stderr or f"exit code {process.returncode}",
                )
            else:
                self._permissions_fixed = True

    async def _start_console_server(self):
        """
        Override: add the ``docker_exec`` console type alongside the
        telnet/ssh/http types supported by the base class.
        """
        if self.console_type == "docker_exec":
            await self._start_docker_exec_console()
        else:
            await super()._start_console_server()

    # ---- docker_exec console implementation --------------------------------

    async def _start_docker_exec_console(self):
        """
        Start a console that runs a command inside the container via the Docker
        exec API, bridged to a telnet server. Intended for vendor NOS containers
        (e.g. Nokia SR Linux) whose CLI is a separate TUI process not exposed on
        PID 1's stdio.

        The exec is created lazily on the first client connection (not when the
        node starts) so the command's startup terminal probe has a real xterm.js
        client to answer it (CPR / prompt_toolkit). The single exec is then
        shared (broadcast) by all clients, matching GNS3's console model.
        Command from GNS3_CONSOLE_CMD.
        """

        telnet = _LazyExecTelnetServer(
            self,
            self.manager,
            self._cid,
            self._console_cmd or "/bin/sh",
            allow_resize=self._console_resize,
        )
        try:
            self._telnet_servers.append(
                await telnet.start(self._manager.port_manager.console_host, self.console)
            )
        except OSError as e:
            raise DockerError(
                f"Could not start console server on socket {self._manager.port_manager.console_host}:{self.console}: {e}"
            )
        log.debug(f"Docker container '{self.name}' started docker_exec console (lazy) on {self.console}")


class _LazyExecTelnetServer(AsyncioTelnetServer):
    """Telnet console whose docker exec (pty + command) is created lazily on
    the first client connection and recreated if the upstream dies.

    Extracted to module level (rather than a closure inside
    _start_docker_exec_console) so the reconnect/recreate logic is unit-testable.

    Lifecycle: the exec is created on the first connect. When the CLI exits
    (quit / idle timeout / crash) the exec pty closes, the broadcast task ends,
    and the *next* client connection recreates the exec — with a terminal
    attached, so the CLI's startup CPR probe is answered. No ``while true``
    wrapper: that would restart the CLI mid-session with no client to answer
    CPR, producing a blank/degraded screen on reconnect.
    """

    def __init__(self, vm, manager, cid, command, allow_resize=True):
        super().__init__(
            reader=None,
            writer=None,
            binary=True,
            echo=False,
            naws=True,
            window_size_changed_callback=self._on_naws,
        )
        self._vm = vm
        self._manager = manager
        self._cid = cid
        self._command = command
        self._allow_resize = allow_resize
        self._exec_id = None
        self._client_size = None  # size received while no exec existed yet
        self._broadcast_task = None
        self._lock = asyncio.Lock()
        self._log_name = f"docker_exec console '{vm.name}'"

    def _upstream_alive(self):
        """True if the exec pty + broadcast task are still pumping."""
        if self._exec_id is None or self._writer is None:
            return False
        if self._writer.is_closing():
            return False
        if self._broadcast_task is not None and self._broadcast_task.done():
            return False
        return True

    async def _disconnect_client(self, network_writer):
        await super()._disconnect_client(network_writer)
        # When the last client leaves, restore the tall no-NAWS default: a
        # browser client resizes the exec to its own geometry (WS terminal
        # size control frames -> NAWS), and the next non-NAWS client (netmiko,
        # bare telnet) connecting to the still-live exec would otherwise
        # inherit it and hit PTY-window paging (the IOS-XR --More-- trap).
        if self._exec_id and not await self._get_connections_snapshot():
            with contextlib.suppress(Exception):
                self._client_size = None
                await self._resize_exec(511, 10000)

    async def _resize_exec(self, columns, rows):
        if not self._exec_id:
            # No exec yet (first client still inside client_connected_hook):
            # remember the size — the hook applies it right after creation
            # instead of the tall default, so it doesn't get overwritten.
            self._client_size = (columns, rows)
            return
        try:
            await self._manager.query(
                "POST",
                f"exec/{self._exec_id}/resize",
                params={"h": str(rows), "w": str(columns)},
            )
        except DockerError:
            pass

    async def _on_naws(self, columns, rows):
        # Client-driven resize (WS terminal-size control frames, telnet NAWS).
        # Ignored for paging CLIs (GNS3_CONSOLE_RESIZE=0): with the exec shared
        # by all clients, one browser resize would break concurrent netmiko
        # sessions that rely on the tall no-paging geometry.
        if not self._allow_resize:
            return
        await self._resize_exec(columns, rows)

    async def run(self, network_reader, network_writer):
        """Catch and log any exception that kills the client session."""
        try:
            await super().run(network_reader, network_writer)
        except Exception as exc:
            log.warning(f"{self._log_name}: client session terminated: {exc}", exc_info=True)

    async def _create_exec(self):
        # create exec with a pty; run as root (vendor CLIs reject the image's
        # default unprivileged user) and export TERM=xterm.
        result = await self._manager.query(
            "POST",
            f"containers/{self._cid}/exec",
            data={
                "AttachStdin": True,
                "AttachStdout": True,
                "AttachStderr": True,
                "Tty": True,
                "User": "root",
                "Env": ["TERM=xterm"],
                "Cmd": ["sh", "-c", self._command],
            },
        )
        self._exec_id = result["Id"]
        log.info(f"{self._log_name}: exec created ({self._exec_id})")

        # start the exec via a hijacked raw HTTP request on the Docker unix
        # socket; with Tty:true the response body is a raw bidirectional pty
        # byte stream (no multiplexing).
        reader, writer = await asyncio.open_unix_connection(self._manager._server_url)
        body = json.dumps({"Detach": False, "Tty": True})
        request = (
            f"POST /v{self._manager._api_version}/exec/{self._exec_id}/start HTTP/1.1\r\n"
            "Host: docker\r\n"
            "Connection: Upgrade\r\n"
            "Upgrade: tcp\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n\r\n{body}"
        ).encode()
        writer.write(request)
        await writer.drain()
        try:
            headers = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError) as e:
            writer.close()
            raise DockerError(f"Docker exec start failed: {e}")
        status_line = headers.split(b"\r\n", 1)[0]
        log.info(f"{self._log_name}: hijacked start -> {status_line.decode(errors='ignore')}")
        if b" 101 " not in status_line and b" 200 " not in status_line:
            writer.close()
            raise DockerError(f"Docker exec start rejected: {status_line.decode(errors='ignore')}")

        # wire the exec stream as this server's upstream and start the broadcast
        # task. AsyncioTelnetServer.start() only starts the broadcast when a
        # reader is set at construction time, so with a lazy upstream we start
        # it manually here.
        self._reader = reader
        self._writer = writer
        self._vm._console_exec_writer = writer  # for stop() cleanup
        self._broadcast_task = asyncio.create_task(self._broadcast_from_upstream())
        log.info(f"{self._log_name}: broadcast task started, upstream wired, ready")

    async def client_connected_hook(self):
        await super().client_connected_hook()
        async with self._lock:
            # (Re)create the exec if it was never created or has died (CLI
            # exited → pty EOF → broadcast task ended). Doing this with a
            # client attached means the CLI's startup CPR probe is answered by
            # a real terminal.
            if not self._upstream_alive():
                log.info(f"{self._log_name}: client connected, (re)creating exec")
                # close a half-dead writer before replacing it
                if self._writer is not None and not self._writer.is_closing():
                    with contextlib.suppress(Exception):
                        self._writer.close()
                try:
                    await self._create_exec()
                except Exception as exc:
                    log.warning(f"{self._log_name}: failed to create exec: {exc}", exc_info=True)
                    raise
                try:
                    # Tall/wide default geometry before any NAWS arrives: a
                    # 24-row PTY makes CLIs that page on the PTY window size
                    # (e.g. the IOS-XR pager) park at --More-- for clients
                    # that never negotiate NAWS (netmiko, bare telnet).
                    # Width 511 matches netmiko's 'terminal width 511'.
                    # A size already pushed by this client (WS terminal-size
                    # control frames -> NAWS, racing the exec creation) wins
                    # over the default.
                    if self._client_size:
                        await self._resize_exec(*self._client_size)
                    else:
                        await self._resize_exec(511, 10000)
                except Exception:
                    pass
            else:
                log.info(f"{self._log_name}: client connected, reusing live exec")
        # ask the TUI to (re)draw for the client that just connected.
        if self._writer:
            try:
                self._writer.write(b"\x0c")  # Ctrl-L -> TUI redraws
                await self._writer.drain()
            except Exception as exc:
                log.warning(f"{self._log_name}: Ctrl-L write failed: {exc}")
        log.info(f"{self._log_name}: client_connected_hook done")
