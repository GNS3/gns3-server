"""Cisco Catalyst 8000v (IOS XE) in autonomous mode: Day-0 ``iosxe_config.txt``.

The guest reads the file from a CD-ROM on its first boot and uses it as its
startup configuration. Verified on 17.18.03a (volume label and ISO flavour do
not matter).
"""

from ..media_profile import text_profile

PROFILE = text_profile(
    "cisco-c8000v-autonomous",
    "Cisco C8000v autonomous",
    "Delivers the startup entry as iosxe_config.txt on a CD-ROM read at the first boot.",
    ("cisco_ios_telnet",),
    "iosxe_config.txt",
    "GNS3_BOOT",
)
