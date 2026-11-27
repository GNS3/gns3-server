"""Cisco Nexus 9000v (NX-OS): bootstrap ``nxos_config.txt``.

The guest reads ``nxos_config.txt`` from a CD-ROM at its first boot, waits for its ethernet module and
applies the file as CLI configuration ("The bootstrap configure is applied successfully"). The file has to
define the ``admin`` account: without one the guest stops at its System Admin Account Setup dialog on the
console. A text captured with ``show running-config`` already carries ``username admin password 5 <hash>``,
which loads as is. Otherwise the node's saved console password becomes the ``admin`` password (an NX-OS
``password`` line is rejected without a word when it fails the password strength policy, which would leave
the account unusable, so the policy check is switched off for it).
"""

import re

from ..media_profile import BootMediaProfile, cli_text, plain_password

ADMIN_LINE = re.compile(r"^username admin password .*\n?", re.M)
# ``password [0|5|7] <secret>``: only a secret that is neither masked (``*****``) nor the empty ``!`` hash of a
# factory account can be loaded back.
ADMIN_SECRET = re.compile(r"^username admin password (?:[057] +)?(\S+)", re.M)
UNUSABLE_SECRET = re.compile(r"[*!]+")
STRENGTH_CHECK_OFF = "no password strength-check"


def has_usable_admin(text):
    return any(not UNUSABLE_SECRET.fullmatch(match[1]) for match in ADMIN_SECRET.finditer(text))


def render(content, context):
    """The text, with the node's saved password as the ``admin`` password when the text has no usable account."""
    text = cli_text(content)
    password = plain_password(context)
    if not has_usable_admin(text) and password:
        header = "" if re.search(rf"^{STRENGTH_CHECK_OFF}\s*$", text, re.M) else STRENGTH_CHECK_OFF + "\n"
        header += f"username admin password {password} role network-admin\n"
        text = header + ADMIN_LINE.sub("", text)
    return {"nxos_config.txt": text.encode("utf-8")}


PROFILE = BootMediaProfile(
    id="cisco-nxosv9k",
    title="Cisco Nexus 9000v",
    description="Delivers the startup entry as nxos_config.txt on a CD-ROM applied at the first boot.",
    device_types=("cisco_nxos",),
    volume_label="CONFIG",
    render=render,
    uses_admin_password=True,
)
