"""Cisco IOS XRv 9000 (IOS XR): bootstrap ``iosxr_config.txt``.

The host layer of the image reads ``iosxr_config.txt`` from a CD-ROM and hands it to the XR VM as
``/etc/sysconfig/iosxr_config.txt``. Once the traffic interfaces have enumerated, the image's CVAC step
applies the file, but only while no username is configured. The file therefore has to define the
administrative user: without one the console asks for a root-system username (Administrative User Dialog)
and nothing else of the file is applied. A text captured with ``show running-config`` already carries
``username <name> group root-lr ... secret 10 <hash>`` and loads as is. Otherwise the node's saved console
password becomes the ``admin`` secret.
"""

import re

from ..media_profile import BootMediaProfile, cli_text, plain_password

# ``username <name>`` with its indented lines and the ``!`` that closes the block.
USER_BLOCK = re.compile(r"^username (\S+)[ \t]*\n((?:[ \t]+.*\n?)*)(?:!\n)?", re.M)
# ``secret`` or the older ``password``, each with an optional encryption type.
SECRET = re.compile(r"^[ \t]+(?:secret|password) (?:[0-9]+ )?(\S+)", re.M)


def has_usable_user(text):
    """True when the text defines a user with a loadable secret (a masked ``*****`` secret is not)."""
    for match in USER_BLOCK.finditer(text):
        secret = SECRET.search(match[2])
        if secret and not re.fullmatch(r"\*+", secret[1]):
            return True
    return False


def render(content, context):
    """The text, with the node's saved password as the ``admin`` secret when the text has no usable user."""
    text = cli_text(content)
    password = plain_password(context)
    if not has_usable_user(text) and password:
        admin = f"username admin\n group root-lr\n group cisco-support\n secret 0 {password}\n!\n"
        text = admin + USER_BLOCK.sub("", text)
    return {"iosxr_config.txt": text.encode("utf-8")}


PROFILE = BootMediaProfile(
    id="cisco-iosxrv9k",
    title="Cisco IOS XRv 9000",
    description="Delivers the startup entry as iosxr_config.txt on a CD-ROM applied at the first boot.",
    device_types=("cisco_xr",),
    volume_label="config-1",
    render=render,
    uses_admin_password=True,
)
