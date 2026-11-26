"""Console recipe for Arista EOS (capture only).

EOS startup is not replayed through the console: it is delivered as native boot media (see
``services/configurations/boot_media/profiles/arista_veos.py``). This recipe serves the console capture of
``show running-config``. A factory vEOS logs in as ``admin`` and enters privileged mode with a bare
``enable``, neither asking for a password.
"""

import re

from ..capture_format import ConfigurationFormat
from ..platforms import ConsolePlatform

BANNER = re.compile(r"^banner \S+$")


def complete_banners(config):
    """True when every multi-line ``banner <type>`` block of the text is closed by its ``EOF`` line."""
    open_banner = False
    for line in config.splitlines():
        if open_banner:
            open_banner = line.strip() != "EOF"
        elif BANNER.match(line):
            open_banner = True
    return not open_banner


PLATFORM = ConsolePlatform(
    "arista_eos",
    ("terminal length 0", "terminal width 511"),
    ConfigurationFormat(r"^! Command: show running-config$", end="end", validator=complete_banners),
    default_username="admin",
    enable=True,
    restorer=None,
)
