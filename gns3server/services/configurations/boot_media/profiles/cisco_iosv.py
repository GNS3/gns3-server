"""Cisco IOSv and IOSvL2 (vIOS): ``ios_config.txt`` on a second disk.

These images have no CD-ROM driver. Their bootstrap looks for ``ios_config.txt`` on a second (virtio) disk
that holds a small FAT filesystem, reports ``% Applying bootstrap config from flash2:...`` and applies the
file as CLI configuration. ``ios_config_checksum`` next to it holds the MD5 of the file, as the vendor's
own startup disk does. IOS needs no account in the file (the console line has no login by default), so the
node's saved password is not used. ``show running-config`` prints a banner delimiter as the two characters
``^C``, which a configuration file does not read as one delimiter: like the console replay, the banners are
rewritten with a plain delimiter that is not part of their text.
"""

import hashlib
import re

from gns3server.services.configurations.shared.banners import delimited_banner
from gns3server.services.configurations.shared.errors import ConfigurationError

from ..media_profile import BootMediaProfile, cli_text

BANNER = re.compile(r"^banner (\S+) (.+)$")
# Lines a listing starts with (``show running-config`` or ``more system:running-config``) that are not configuration.
LISTING_HEADER = re.compile(
    r"^(?:Building configuration\.\.\.|Current configuration : \d+ bytes|Using \d+ out of \d+ bytes)[ \t]*\n", re.M
)


def normalize_banners(text):
    """The text with every banner written as ``banner <type> <delimiter>body<delimiter>``."""
    lines = iter(text.split("\n"))
    result = []
    for line in lines:
        banner = BANNER.match(line)
        if banner is None:
            result.append(line)
            continue
        delimited = delimited_banner(banner[2], lines)
        if delimited is None:
            raise ConfigurationError("configuration_invalid_content")
        result.append(f"banner {banner[1]} {delimited}")
    return "\n".join(result)


def render(content, context):
    text = normalize_banners(LISTING_HEADER.sub("", cli_text(content)))
    if not text.endswith("\n"):
        text += "\n"
    data = text.encode("utf-8")
    checksum = hashlib.md5(data, usedforsecurity=False).hexdigest()  # a file format, not a security check
    return {"ios_config.txt": data, "ios_config_checksum": checksum.encode("ascii") + b"\n"}


PROFILE = BootMediaProfile(
    id="cisco-iosv",
    title="Cisco IOSv / IOSvL2",
    description="Delivers the startup entry as ios_config.txt on a second disk applied at the first boot.",
    device_types=("cisco_ios_telnet",),
    volume_label="IOSCFG",
    render=render,
    media="disk",
)
