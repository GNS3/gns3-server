"""Wipe of a native Docker IOL node: its container is deleted and recreated for a fresh writable layer.

Only node-owned binds can be reconstructed by DockerVM.create(), so unexpected mounts fail the preflight rather
than losing their attachment during recreation. No Docker volume is removed, unrelated files in the runtime
directory survive, and the runtime journal records the reset so a failed recreation blocks the next start
until another wipe completes.
"""

import os
import re
import tempfile
from pathlib import Path

from gns3server.compute.docker.container_state import docker_container, docker_stopped
from gns3server.compute.docker.docker_error import DockerError, DockerHttp404Error
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.safe_io import linked, validate_owned_paths, write_json
from gns3server.services.configurations.shared.startup_journal import journal_path, runtime


class DockerIOLWipe:
    def __init__(self, node):
        self.node = node

    async def ensure_stopped(self):
        if not await docker_stopped(self.node):
            raise ConfigurationError("stop_required")

    async def inspect(self):
        try:
            image = await self.node._get_image_information()
            info = await docker_container(self.node)
        except DockerError:
            raise ConfigurationError("container_state_unavailable") from None
        identity = image.get("Id") if isinstance(image, dict) else None
        if not isinstance(identity, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", identity):
            raise ConfigurationError("configuration_image_required")
        if self.node._image_id and self.node._image_id != identity:
            raise ConfigurationError("configuration_image_changed")
        if info is not None and info.get("Image") != identity:
            raise ConfigurationError("configuration_image_changed")
        self.image_id = identity
        self.volumes = self.node._persistent_volume_list(image, include_network_config=False)
        self.validate_volumes()
        if info is not None:
            self.validate_mounts(info)
        self.preflight()

    def validate_volumes(self):
        # The runner, socket bind and host NVRAM path require these exact roots.
        if (
            self.node.extra_configs
            or any(
                not isinstance(volume, str)
                or volume in ("/", self.node._unix_socket_dir)
                or volume == "/gns3"
                or volume.startswith("/gns3/")
                or not volume.startswith("/")
                or str(Path(volume)) != volume
                or ".." in volume.split("/")
                or any(c in volume for c in ("\x00", "\r", "\n", ":"))
                for volume in self.volumes
            )
            or not {self.node._IOL_CONFIG_DIR, self.node._IOL_RUN_DIR} <= set(self.volumes)
        ):
            raise ConfigurationError("configuration_mount_shadowed")

        if any(
            parent != child and child.startswith(parent.rstrip("/") + "/")
            for parent in self.volumes
            for child in self.volumes
        ):
            raise ConfigurationError("configuration_mount_shadowed")

    def validate_mounts(self, info):
        root = Path(self.node.working_dir).absolute()
        allowed = {volume: (str(root / volume.lstrip("/")), True) for volume in self.volumes}
        allowed["/gns3"] = (str(Path(self.node.manager.resources_path()).absolute()), False)
        if getattr(self.node, "_unix_socket_nio", False):
            socket_root = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
            allowed[self.node._unix_socket_dir] = (str(Path(socket_root) / "gns3" / "unixio" / self.node.id), True)
        mounts = info.get("Mounts")
        if not isinstance(mounts, list):
            raise ConfigurationError("configuration_mount_shadowed")
        seen = set()
        for mount in mounts:
            if not isinstance(mount, dict):
                raise ConfigurationError("configuration_mount_shadowed")
            target = mount.get("Destination")
            expected = allowed.get(target) if isinstance(target, str) else None
            if (
                expected is None
                or target in seen
                or mount.get("Type") != "bind"
                or mount.get("Source") != expected[0]
                or mount.get("RW") is not expected[1]
            ):
                raise ConfigurationError("configuration_mount_shadowed")
            seen.add(target)
        if not set(allowed) <= seen:
            raise ConfigurationError("configuration_mount_shadowed")

    def paths(self, root):
        run = root / "tmp/run"
        paths = [run / f"nvram_{self.node.application_id:05d}"]
        candidates = [*run.glob("nvram_*"), *run.glob("vlan.dat*")]
        paths += [path for path in candidates if re.fullmatch(r"nvram_[0-9]{5}|vlan\.dat(?:-[0-9]{1,5})?", path.name)]
        return list(dict.fromkeys(paths))

    def preflight(self):
        """Refuse a wipe that could not complete. An interrupted reset does not fail it: a new wipe finishes it."""
        if type(self.node.application_id) is not int or not 1 <= self.node.application_id <= 1022:
            raise ConfigurationError("application_id_unavailable")
        root = Path(self.node.working_dir).absolute()
        if linked(root):
            raise ConfigurationError("unsafe_configuration_path")
        root = root.resolve(strict=True)
        validate_owned_paths(
            root,
            [
                *self.paths(root),
                root / journal_path(self.node).name,
                # Also protect volume seeding, which happens during container creation.
                *(root / volume.lstrip("/") / ".gns3_perms" for volume in self.volumes),
            ],
        )
        runtime(self.node)

    async def reset_runtime(self):
        """Recreate the container (fresh writable layer) and remove owned runtime files."""
        await self.ensure_stopped()
        await self.inspect()
        await self.ensure_stopped()
        value = {"version": 1, "generation": runtime(self.node)["generation"] + 1, "state": "resetting"}
        write_json(journal_path(self.node), value)
        try:
            if self.node._cid:
                try:
                    # Never force-kill here, and never delete anonymous/named volumes.
                    await self.node.manager.query("DELETE", f"containers/{self.node._cid}", params={"force": 0, "v": 0})
                except DockerHttp404Error:
                    pass
            self.node._cid = None
            # Resolve the mutable tag once; creation uses exactly the inspected image.
            self.node._startup_restore_image = self.image_id
            try:
                await self.node.create()
            finally:
                self.node._startup_restore_image = None
            await self.ensure_stopped()
            root = Path(self.node.working_dir).absolute()
            owned = self.paths(root)
            validate_owned_paths(root, owned)
            for path in owned:
                path.unlink(missing_ok=True)
            self.node._startup_config_content = None
            self.node._startup_config_dirty = False
        except DockerError:
            raise ConfigurationError("configuration_operation_failed") from None
        value["state"] = "clean"
        write_json(journal_path(self.node), value)
        return value
