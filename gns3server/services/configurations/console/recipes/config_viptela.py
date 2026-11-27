"""Console recipe for Cisco Viptela (capture only).

Viptela startup is not replayed through the console: it is delivered as native
boot media (see ``services/configurations/boot_media/profiles/cisco_viptela.py``).
This recipe only serves the console capture of ``show running-config``.
"""

import re

from ..capture_format import ConfigurationFormat, complete_quotes
from ..platforms import ERROR, ConsolePlatform

VIPTELA_PROMPT = re.compile(r"[A-Za-z0-9_./:@-]{1,192}#")

PLATFORM = ConsolePlatform(
    "cisco_viptela",
    ("paginate false", "screen-width 256"),
    ConfigurationFormat(r"^system\s*$", required=(r"^[ \t]+host-name[ \t]+\S+",), end="!", validator=complete_quotes),
    operational=VIPTELA_PROMPT,
    configuration=None,
    errors=re.compile(ERROR.pattern + r"|^\s*Aborted:", re.I | re.M),
    restorer=None,
)
