"""Cisco Viptela devices (vEdge, vSmart, vBond, vManage): cloud-init NoCloud media.

The images run stock cloud-init and look for a NoCloud seed (volume label
``cidata`` with ``user-data`` and ``meta-data``). ConfD only starts after
cloud-init has finished, so the user-data writes the native CLI configuration
and a small loader, and starts the loader in the background; it waits for ConfD
and merges the configuration with ``confd_load``, retrying while ConfD's helper
scripts are not ready yet and printing ``GNS3: startup configuration applied.`` or
``GNS3: startup configuration FAILED: <reason>`` on the serial console. The admin
account is provisioned first, in its own transaction: from the text's
``system / aaa / user admin / password <hash>``, otherwise from the node's saved
console password (hashed here with sha512-crypt, never placed on the media in clear).
"""

import base64
import hashlib
import json
import re

from ...shared.password_hash import sha512_crypt
from ..media_profile import BootMediaProfile, MediaContext, cli_text

ROOT = "/var/lib/gns3-startup"
LOADER = r"""#!/bin/sh
# GNS3 startup configuration loader (runs once, in the background).
root=/var/lib/gns3-startup
exec > "$root/import.log" 2>&1
export CONFD_IPC_ACCESS_FILE=/etc/confd/confd_ipc_secret
console() { echo "$1" > /dev/ttyS0; }
# Load one file into ConfD. Early in the boot ConfD's helper scripts are not ready
# yet (usmentry write errors, lost connections, locks): wait and try again.
# Anything else is final.
load() {
    attempt=0
    while [ "$attempt" -lt 40 ]; do
        attempt=$((attempt+1))
        : > "$root/attempt.log"
        if timeout 240 /usr/bin/confd --wait-started 240 &&
            timeout 120 /usr/bin/confd_load -l -m -F c $2 -u admin -g netadmin "$1" > "$root/attempt.log" 2>&1; then
            cat "$root/attempt.log"
            return 0
        fi
        cat "$root/attempt.log"
        grep -Eq 'usmentry|Failed to set usm|communication failure|Lost connection|Failed to connect|database is locked' "$root/attempt.log" || return 1
        sleep 10
    done
    return 1
}
fail() {
    reason=$(grep -m1 confd_load "$root/attempt.log" | sed -E 's/^confd_load: [0-9]+: //; s/\$[0-9a-z]+\$[^ "]*/<hash>/g' | cut -c1-200)
    echo failed > "$root/status"
    console "GNS3: startup configuration FAILED: ${reason:-ConfD was not ready} (see $root/import.log)"
    exit 1
}
# The admin account first, in its own transaction, so its password is in place
# before the main configuration is merged.
if [ -f "$root/initial-admin.cfg" ]; then
    load "$root/initial-admin.cfg" "" || fail
fi
# Viptela puts the factory interfaces in vpn 0/512; a configuration that defines
# vpn sections replaces them (one transaction, so the mandatory vpns stay valid).
scope=""
[ -f "$root/replace-vpn" ] && scope="-p /vpn"
load "$root/startup.cfg" "$scope" || fail
sync
echo applied > "$root/status"
console 'GNS3: startup configuration applied.'
"""


def _admin_password_lines(text):
    """Indexes of the lines ``system / aaa / user admin / password <value>`` in the text."""
    stack, found = [], []
    for index, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if not line or line.startswith(("!", "#")):
            continue
        indent = len(raw.expandtabs(8)) - len(raw.expandtabs(8).lstrip())
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if tuple(entry for _, entry in stack) == ("system", "aaa", "user admin") and line.startswith("password "):
            found.append(index)
        stack.append((indent, line))
    return found


def admin_hash(text):
    """The ``$n$...`` hash of ``system / aaa / user admin / password`` in the text, or None."""
    lines = text.splitlines()
    for index in _admin_password_lines(text):
        value = lines[index].strip().split(None, 1)[1].strip()
        return value if value.startswith("$") else None
    return None


def without_plaintext_admin_password(text):
    """The text without an ``admin`` password that is not a hash.

    ConfD stores a plaintext value verbatim and the account becomes unusable, so
    it must not be merged back after the admin step has set the real password.
    """
    if admin_hash(text) is not None:
        return text
    drop = set(_admin_password_lines(text))
    if not drop:
        return text
    kept = [line for index, line in enumerate(text.splitlines()) if index not in drop]
    return "\n".join(kept) + "\n"


def initial_admin(text, context):
    """CLI text that sets the admin password first, or None to keep the factory admin.

    The text's own admin hash wins; otherwise the node's saved console password is
    hashed here (sha512-crypt) so the plaintext never reaches the media.
    """
    value = admin_hash(text)
    if value is None and context.admin_password:
        salt = hashlib.sha256(context.node_id.encode()).hexdigest()[:16]
        value = sha512_crypt(context.admin_password, salt)
    if value is None:
        return None
    return f"system\n aaa\n  user admin\n   password {value}\n  !\n !\n!\n"


def defines_vpns(text):
    """True when the text has top-level ``vpn <n>`` sections."""
    return re.search(r"(?m)^vpn[ \t]+\d+[ \t]*$", text) is not None


def render(content, context: MediaContext):
    text = cli_text(content)
    # The admin account is provisioned from ``initial_admin``; a plaintext password would break it in the merge.
    text = without_plaintext_admin_password(text)
    admin = initial_admin(text, context)
    encoded = lambda data: base64.b64encode(data).decode("ascii")  # noqa: E731
    entries = [
        (f"{ROOT}/startup.cfg", "0600", text.encode()),
        (f"{ROOT}/load.sh", "0700", LOADER.encode()),
    ]
    if defines_vpns(text):
        entries.append((f"{ROOT}/replace-vpn", "0600", b"1\n"))
    if admin is not None:
        entries.append((f"{ROOT}/initial-admin.cfg", "0600", admin.encode()))
    document = {
        "write_files": [
            {"path": path, "permissions": mode, "encoding": "b64", "content": encoded(data)}
            for path, mode, data in entries
        ],
        "runcmd": [["sh", "-c", f"nohup timeout 1500 sh {ROOT}/load.sh </dev/null >/dev/null 2>&1 &"]],
    }
    return {
        "meta-data": f"instance-id: gns3-{context.node_id}\n".encode(),
        # JSON is valid YAML, so the document needs no YAML quoting rules.
        "user-data": b"#cloud-config\n" + json.dumps(document).encode() + b"\n",
    }


PROFILE = BootMediaProfile(
    id="cisco-viptela",
    title="Cisco Viptela",
    description="Delivers the startup entry through a cloud-init NoCloud CD-ROM loaded into ConfD at the first boot.",
    device_types=("cisco_viptela",),
    volume_label="cidata",
    render=render,
    uses_admin_password=True,
)
