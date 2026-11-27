"""Cisco Catalyst 9000v (IOS XE): Day-0 ``iosxe_config.txt``.

The guest reads the file from a CD-ROM on its first boot, like the Catalyst 8000v in autonomous mode, and
applies it as its startup configuration. The text is stored unchanged: a ``show running-config`` capture
loads as is. The UADP and Q200 variants of the image differ only in the virtual switch definition
(``vswitch.xml``), not in how the file is read.
"""

from ..media_profile import text_profile

PROFILE = text_profile(
    "cisco-cat9kv",
    "Cisco Catalyst 9000v",
    "Delivers the startup entry as iosxe_config.txt on a CD-ROM read at the first boot.",
    ("cisco_ios_telnet",),
    "iosxe_config.txt",
    "GNS3_BOOT",
)
