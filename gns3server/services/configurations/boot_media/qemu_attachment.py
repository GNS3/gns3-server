"""How a staged media image is attached to a QEMU node at launch.

CD-ROM media (``startup-media.iso``) is attached read-only as an IDE CD-ROM, at the first of IDE index 2 / 3
that the node does not already use. Disk media (``startup-media.img``) is attached as a virtio disk at the
first free index of 1 to 3, where a vendor's own startup disk sits. The caller lists it after the node's own
disks: virtio disks get their PCI slots in command-line order and the firmware boots the first one, so the
media must never come first. The boot order is left untouched: the guests read the media themselves, none
boots from it. It is attached only for the first boot after a wipe (journal state ``prepared``).
A profile of kind ``none`` attaches nothing.
"""

from pathlib import Path

from gns3server.services.configurations.shared.startup_journal import journal_path, runtime

ISO_MEDIA_FILENAME = "startup-media.iso"
DISK_MEDIA_FILENAME = "startup-media.img"


def _qemu_error(message):
    """A QemuError, imported lazily: the qemu package imports this module."""
    from gns3server.compute.qemu.qemu_error import QemuError

    return QemuError(message)


def media_filename(profile):
    """File name of the staged media of a profile (a profile that is not registered stages a CD-ROM image)."""
    return DISK_MEDIA_FILENAME if profile is not None and profile.media == "disk" else ISO_MEDIA_FILENAME


def required_machine(node):
    """QEMU machine type the node's boot media profile needs, or None."""
    from .profiles import PROFILES

    profile = PROFILES.get(getattr(node, "startup_media_profile", None))
    return profile.machine if profile is not None else None


def _hdd_interface(node):
    """Interface the HDD position will use: the config disk takes the HDA interface when HDD has none
    (``QemuVM._disk_options``, which runs after this, only then rewrites ``hdd_disk_interface``)."""
    interface = node._hdd_disk_interface
    if node.create_config_disk and interface == "none":
        interface = getattr(node, "_hda_disk_interface", "none")
    return interface


def ide_slot(node):
    """First free IDE drive index (2 = secondary master, 3 = secondary slave)."""
    taken = set()
    if node.cdrom_image and node.cdrom_interface == "ide":
        taken.add(2)
    if node._hdc_disk_image and node._hdc_disk_interface == "ide":
        taken.add(2)
    if node.cdrom2_image and node.cdrom2_interface == "ide":
        taken.add(3)
    if (node._hdd_disk_image or node.create_config_disk) and _hdd_interface(node) == "ide":
        taken.add(3)
    for index in (2, 3):
        if index not in taken:
            return index
    raise _qemu_error("No free IDE CD-ROM slot for the startup boot media; free the second CD/DVD or an IDE disk")


def virtio_slot(node):
    """First free virtio disk index of 1 to 3 (index 0 is the boot disk)."""
    taken = set()
    for index, drive in enumerate("abcd"):
        if getattr(node, f"_hd{drive}_disk_image", "") and getattr(node, f"_hd{drive}_disk_interface", "") == "virtio":
            taken.add(index)
    # The config disk takes the HDD position.
    if node.create_config_disk and _hdd_interface(node) == "virtio":
        taken.add(3)
    for index in (1, 2, 3):
        if index not in taken:
            return index
    raise _qemu_error("No free virtio disk slot for the startup boot media; free one of the node's virtio disks")


def media_options(node):
    """QEMU arguments for the staged media; empty unless it is the first boot after staging."""
    from .profiles import PROFILES

    if not getattr(node, "startup_media_profile", None) or not journal_path(node).exists():
        return []
    if runtime(node)["state"] != "prepared":
        return []
    profile = PROFILES.get(node.startup_media_profile)
    if profile is not None and profile.media == "none":
        return []
    path = Path(node.working_dir).absolute() / media_filename(profile)
    if not path.is_file() or path.is_symlink():
        raise _qemu_error("The startup boot media is missing: wipe the node and start it again")
    image = str(path).replace(",", ",,")
    if profile is not None and profile.media == "disk":
        return ["-drive", f"file={image},if=virtio,index={virtio_slot(node)},media=disk,format=raw,id=startup-media"]
    return ["-drive", f"file={image},if=ide,index={ide_slot(node)},media=cdrom,format=raw,readonly=on"]
