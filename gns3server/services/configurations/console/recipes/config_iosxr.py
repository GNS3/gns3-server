"""Console recipe for Cisco IOS XR."""

from ..capture_format import ConfigurationFormat
from ..platforms import ConsolePlatform, Step

PLATFORM = ConsolePlatform(
    "cisco_xr",
    ("terminal length 0", "terminal width 511"),
    ConfigurationFormat(r"^!! IOS XR Configuration \d", end="end", banners=True),
    configuration=None,
    finish=(Step("commit"), Step("end")),
    verifiable=True,
)
