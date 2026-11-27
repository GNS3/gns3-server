"""Console recipe for Cisco NX-OS."""

from ..capture_format import ConfigurationFormat
from ..platforms import ConsolePlatform, Step
from ..replay import ReplayPolicy

PLATFORM = ConsolePlatform(
    "cisco_nxos",
    ("terminal length 0", "terminal width 511"),
    ConfigurationFormat(r"^!Command: show running-config$", required=(r"^version \d",), banners=True),
    replay=ReplayPolicy(skip_prefixes=("version ",), skip_lines=("boot-start-marker", "boot-end-marker")),
    finish=(Step("end"), Step("copy running-config startup-config", r"Copy complete|100%")),
    save_commands=(Step("copy running-config startup-config", r"Copy complete|100%"),),
    verifiable=True,
)
