"""Console recipe for Palo Alto PAN-OS (capture only).

PAN-OS startup is not replayed through the console: it is delivered as native boot media (see
``services/configurations/boot_media/profiles/paloalto_panos.py``). This recipe serves the console capture of
the running configuration, as the XML document the device itself loads (``<config>``). With
``set cli op-command-xml-output on`` the CLI prints that document inside a ``<response><result>`` envelope,
which the parser removes.
"""

import re

from ...shared.xml_config import DECLARATION, parse_config
from ..platforms import ERROR, ConsolePlatform
from ..prompts import last_line

# ``admin@PA-VM>``, with the HA state (``admin@PA-VM(active)>``) and the configure-mode ``#`` variant.
PANOS_PROMPT = re.compile(r"[\w.-]{1,64}@[\w.-]{1,64}(?:\([\w-]{1,32}\))?>")
ENVELOPE = re.compile(r'<response status="success"><result>\s*(<config\b.*?</config>)\s*</result></response>', re.S)


def parse(transcript, prompt):
    """The ``<config>`` document of a complete capture, or None while the transcript is still arriving."""
    text = transcript.replace("\r\n", "\n").replace("\r", "\n")
    # The CLI repeats its prompt when a line ends in both CR and LF: the final line is one or more prompts.
    final = last_line(text)
    if prompt not in final or final.replace(prompt, "").strip():
        return None
    matches = ENVELOPE.findall(text)
    if len(matches) != 1 or parse_config(matches[0]) is None:
        return None
    return (DECLARATION + "\n" + matches[0].strip() + "\n").encode("utf-8")


PLATFORM = ConsolePlatform(
    "paloalto_panos",
    ("set cli pager off", "set cli scripting-mode on", "set cli op-command-xml-output on"),
    parse,
    capture_command="show config running",
    filename="running-config.xml",
    operational=PANOS_PROMPT,
    configuration=None,
    errors=re.compile(ERROR.pattern + r"|^\s*Invalid syntax\.|^\s*Unknown command", re.I | re.M),
    default_username="admin",
    restorer=None,
)
