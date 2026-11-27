"""Juniper vSRX NG (vSRX 3.0): ``juniper.conf`` on a CD-ROM.

The image's first-boot script (``/etc/vsrx.configdrive``) takes an attached CD-ROM (``/dev/cd0``) for a config drive. When
the drive holds no OpenStack metadata it copies ``juniper.conf`` from its root to ``/config``, and ``mgd`` commits it as
the initial configuration. It does that once: the script skips every later boot, so a file that does not load is not
tried again. The entry text is therefore checked when it is staged: it has to be the hierarchical configuration
``show configuration`` prints (braces balanced), not ``set`` commands. Its ``##`` comments (the ``Last commit`` header,
``## Warning``, ``## SECRET-DATA``) are ignored by the loader and the text is stored unchanged. A configuration without
``root-authentication`` commits too; ``root`` then logs in without a password.
"""

from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.junos_brace_balance import has_balanced_braces

from ..media_profile import BootMediaProfile, checked_text


def render(content, context):
    text = checked_text(content).replace("\r\n", "\n")
    if "{" not in text or not has_balanced_braces(text):
        raise ConfigurationError("configuration_invalid_content")
    return {"juniper.conf": (text if text.endswith("\n") else text + "\n").encode("utf-8")}


PROFILE = BootMediaProfile(
    id="juniper-vsrx",
    title="Juniper vSRX NG",
    description="Delivers the startup entry as juniper.conf on a CD-ROM read at the first boot.",
    device_types=("juniper_junos",),
    volume_label="CONFIG",
    render=render,
)
