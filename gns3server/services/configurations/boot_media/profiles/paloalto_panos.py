"""Palo Alto PAN-OS (VM-Series): bootstrap package ``config/bootstrap.xml`` on a CD-ROM.

A VM-Series firewall in factory state looks for a bootstrap package on an attached CD-ROM at its first boot: the
directories ``config``, ``content``, ``license`` and ``software``, with ``config/init-cfg.txt`` (the management
settings, derived from the document) and ``config/bootstrap.xml`` (the whole configuration, loaded and committed).
The entry text is that XML document, as captured by the console recipe (``<config>``), or the same document inside
the CLI's ``<response><result>`` envelope.

The configuration replaces the factory one, so it has to define an administrator that can log in: a text
captured from a device already carries ``<phash>`` for its users. Otherwise the node's saved console password
becomes the ``admin`` superuser (hashed with SHA-256 crypt, the format of the device's own ``__telemetryuser``).
"""

import re
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Interface

from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.password_hash import sha256_crypt
from gns3server.services.configurations.shared.xml_config import parse_config, serialize

from ..media_profile import BootMediaProfile, checked_text, plain_password

DECLARATION = re.compile(r"^\s*<\?xml[^>]*\?>\s*")
ENVELOPE = re.compile(
    r'^\s*<response status="success"><result>\s*(<config\b.*</config>)\s*</result></response>\s*$', re.S
)
EMPTY_DIRECTORIES = ("content/", "license/", "software/")


def document(content):
    """The ``<config>`` element of the text; ConfigurationError for anything else."""
    text = checked_text(content)
    envelope = ENVELOPE.match(text)
    root = parse_config(DECLARATION.sub("", envelope[1] if envelope else text, count=1))
    if root is None:
        raise ConfigurationError("configuration_invalid_content")
    return root


def init_cfg(root):
    """``config/init-cfg.txt`` matching the configuration's own management settings.

    PAN-OS gives the values of ``init-cfg.txt`` precedence over ``bootstrap.xml``, so they are derived from the
    document instead of being invented: the management address (DHCP or static), the jumbo-frame operational mode
    when an interface uses an MTU above 1500 (it is local state that the XML alone does not restore, and the first
    commit is rejected without it), and advanced routing when the configuration enables it.
    """
    system = root.find("devices/entry/deviceconfig/system")
    lines = ["type=dhcp-client"]
    if system is not None and system.find("type/dhcp-client") is None:
        address = (system.findtext("ip-address") or "").strip()
        if address:
            try:
                lines = ["type=static"]
                for key in ("ip-address", "netmask", "default-gateway"):
                    value = (system.findtext(key) or "").strip()
                    IPv4Address(value)
                    if key == "netmask":
                        IPv4Network(f"0.0.0.0/{value}")
                    lines.append(f"{key}={value}")
                for key, check in (("ipv6-address", IPv6Interface), ("ipv6-default-gateway", IPv6Address)):
                    value = (system.findtext(key) or "").strip()
                    if value:
                        check(value)
                        lines.append(f"{key}={value}")
            except ValueError:
                raise ConfigurationError("configuration_invalid_content") from None
        elif system.find("type/static") is not None:
            raise ConfigurationError("configuration_invalid_content")
    mtus = root.findall("devices/entry/network/interface//mtu") + root.findall(
        "devices/entry/deviceconfig/setting/jumbo-frame/mtu"
    )
    if any((item.text or "").strip().isdigit() and int(item.text.strip()) > 1500 for item in mtus):
        lines.append("op-command-modes=jumbo-frame")
    if (root.findtext("devices/entry/deviceconfig/setting/advanced-routing") or "").strip() == "yes":
        lines.append("plugin-op-commands=advance-routing:enable")
    return ("\n".join(lines) + "\n").encode("ascii")


def has_usable_admin(root):
    """True when a user (other than the device's own ``__`` accounts) is a superuser with a loadable hash."""
    for entry in root.findall("mgt-config/users/entry"):
        name = entry.get("name", "")
        phash = (entry.findtext("phash") or "").strip()
        superuser = (entry.findtext("permissions/role-based/superuser") or "").strip() == "yes"
        if superuser and phash and not name.startswith("__") and not re.fullmatch(r"\*+", phash):
            return True
    return False


def add_admin(root, password):
    """Define ``admin`` as a superuser with the password, replacing an ``admin`` that cannot log in."""
    management = root.find("mgt-config")
    if management is None:
        management = root.makeelement("mgt-config", {})
        root.insert(0, management)
    users = management.find("users")
    if users is None:
        users = management.makeelement("users", {})
        management.insert(0, users)
    for entry in users.findall("entry"):
        if entry.get("name") == "admin":
            users.remove(entry)
    entry = users.makeelement("entry", {"name": "admin"})
    users.insert(0, entry)
    phash = entry.makeelement("phash", {})
    phash.text = sha256_crypt(password)
    entry.append(phash)
    permissions = entry.makeelement("permissions", {})
    role = permissions.makeelement("role-based", {})
    superuser = role.makeelement("superuser", {})
    superuser.text = "yes"
    role.append(superuser)
    permissions.append(role)
    entry.append(permissions)


def render(content, context):
    root = document(content)
    password = plain_password(context)
    if has_usable_admin(root) or not password:
        # Text that already works is delivered as it was written, only with the declaration the device expects.
        text = DECLARATION.sub("", ENVELOPE.sub(r"\1", checked_text(content), count=1), count=1).strip()
        bootstrap = f'<?xml version="1.0"?>\n{text}\n'.encode()
    else:
        add_admin(root, password)
        bootstrap = serialize(root)
    files = {"config/bootstrap.xml": bootstrap, "config/init-cfg.txt": init_cfg(root)}
    files.update({name: b"" for name in EMPTY_DIRECTORIES})
    return files


PROFILE = BootMediaProfile(
    id="paloalto-panos",
    title="Palo Alto PAN-OS",
    description="Delivers the startup entry as a bootstrap package (config/bootstrap.xml) on a CD-ROM applied at the first boot.",
    device_types=("paloalto_panos",),
    volume_label="PAN_BOOT",
    render=render,
    uses_admin_password=True,
)
