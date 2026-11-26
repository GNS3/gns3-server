"""What a device needs from its native boot media: a profile.

A profile turns the text of a startup entry into the files of a small boot media (an ISO or a FAT
disk) that the guest reads on its first boot. Profiles are plain data plus one function;
adding a device means adding one profile module and one line in ``profiles/__init__.py``.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from gns3server.services.configurations.shared.errors import ConfigurationError

MAX_CONTENT_BYTES = 2 * 1024 * 1024
# A file name, or a path of up to four of them (``config/bootstrap.xml``). A trailing ``/`` names an empty directory.
NAME = r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}"
FILENAME = re.compile(rf"{NAME}(?:/{NAME}){{0,3}}/?")
VOLUME_LABEL = re.compile(r"[A-Za-z0-9_-]{1,32}")
# ``cdrom``: an ISO9660 image attached as an IDE CD-ROM. ``disk``: a small FAT disk attached as a virtio disk.
# ``none``: nothing is attached; the profile only prepares the node's own disk (``prepare_disk``).
MEDIA_KINDS = ("cdrom", "disk", "none")
# FAT volume labels are at most 11 characters.
DISK_LABEL_LENGTH = 11
# A plain password that stays one token on a configuration line (printable, no spaces).
PLAIN_PASSWORD = re.compile(r"[!-~]{1,127}")


@dataclass(frozen=True)
class MediaContext:
    """Facts about the node the media is built for (never the configuration)."""

    node_id: str
    # The node's saved console password, for profiles with ``uses_admin_password``.
    # Never logged or shown; profiles must not place it on the media in clear.
    admin_password: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class BootMediaProfile:
    id: str
    title: str
    description: str
    # Entry ``device_type`` values this profile accepts. The entry keeps its
    # console recipe, so the same text can still be captured from the guest.
    device_types: tuple[str, ...]
    volume_label: str
    # Validates the entry text and returns the files of the media. Raises
    # ConfigurationError("configuration_invalid_content") for unusable text.
    render: Callable[[str, MediaContext], dict[str, bytes]]
    # True when the profile can make use of the node's saved console password.
    uses_admin_password: bool = False
    # Optional ``async (node, files, workdir) -> Path`` returning a private qcow2 disk the node must boot from (a
    # guest that imports the media only from a factory-state disk, or whose configuration lives on its own disk).
    # ``files`` are the rendered files and ``workdir`` a scratch directory that is removed afterwards. Staging it
    # can take minutes: ``stage_seconds``.
    prepare_disk: Callable | None = None
    check_disk: Callable | None = None
    stage_seconds: int = 120
    # QEMU machine type the guest needs to see the media (None: the node's own default).
    machine: str | None = None
    # How the media reaches the guest: one of ``MEDIA_KINDS``.
    media: str = "cdrom"

    def __post_init__(self):
        if not VOLUME_LABEL.fullmatch(self.volume_label):
            raise ValueError(f"Invalid volume label for profile {self.id}")
        if self.media not in MEDIA_KINDS:
            raise ValueError(f"Invalid media kind for profile {self.id}")
        if self.media == "none" and self.prepare_disk is None:
            raise ValueError(f"Profile {self.id} has no media and no disk to prepare")
        if self.media == "disk" and len(self.volume_label) > DISK_LABEL_LENGTH:
            raise ValueError(f"Volume label of profile {self.id} is too long for a FAT disk")

    def files(self, content, context):
        """The validated files of the media for this entry text."""
        if not isinstance(content, str):
            raise ConfigurationError("configuration_invalid_content")
        files = self.render(content, context)
        if not files or not all(valid_entry(name, data) for name, data in files.items()):
            raise ConfigurationError("configuration_invalid_content")
        return files


def valid_entry(name, data):
    """A file has a valid path and content; a directory (trailing ``/``) has a valid path and no content."""
    return bool(FILENAME.fullmatch(name)) and isinstance(data, bytes) and bool(data) != name.endswith("/")


def plain_password(context):
    """The node's saved console password when it can be written as one token on a line, else None."""
    password = context.admin_password
    return password if password and PLAIN_PASSWORD.fullmatch(password) else None


def checked_text(content, *, limit=MAX_CONTENT_BYTES):
    """Entry text that can be placed on media: non-blank, no NUL, bounded."""
    if not content.strip() or "\x00" in content or len(content.encode("utf-8")) > limit:
        raise ConfigurationError("configuration_invalid_content")
    return content


def cli_text(content):
    """``checked_text`` with LF line endings, for profiles that parse the text or feed it to a CLI loader.

    Uploaded files can carry CRLF (a Windows editor).
    """
    return checked_text(content).replace("\r\n", "\n")


def text_profile(profile_id, title, description, device_types, filename, volume_label):
    """A profile that stores the entry text, unchanged, in one file."""
    return BootMediaProfile(
        id=profile_id,
        title=title,
        description=description,
        device_types=device_types,
        volume_label=volume_label,
        render=lambda content, context: {filename: checked_text(content).encode("utf-8")},
    )
