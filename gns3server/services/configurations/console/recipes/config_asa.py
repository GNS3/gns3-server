"""Console recipe for Cisco ASA (ASAv)."""

import re

from ...shared.errors import CaptureFailure
from ..capture_format import ConfigurationFormat
from ..platforms import ConsolePlatform, Step
from ..prompts import ANSI_CSI
from ..replay import ReplayPolicy

ASA_MORE = re.compile(
    r"(?:\A|(?<=[\r\n]))[ \t]*(?:\x1b\[[0-?]*[ -/]*[@-~])*"
    r"(?:<---\s*More\s*--->|---More---|--More--)"
    r"(?:\x1b\[[0-?]*[ -/]*[@-~])*[ \t]*\Z",
    re.I,
)


class ASAPager:
    """Remove only pager framing and advance one page at a time.

    Cisco warns that ASA's console can hang on terminal pager 0. Keep paging
    enabled, and handle its marker and cursor erasure across transport reads.
    Configuration indentation and banner text must survive unchanged.
    """

    def __init__(self):
        self.buffer = ""
        self.erasing = False
        self.column = 0
        self.escape = ""
        self.pages = 0

    def feed(self, data):
        index = 0
        while self.erasing and index < len(data):
            char = data[index]
            index += 1
            if self.escape or char == "\x1b":
                self.escape += char
                if self.escape == "\x1b" or self.escape == "\x1b[":
                    continue
                sequence = ANSI_CSI.fullmatch(self.escape)
                if sequence:
                    code = self.escape[-1]
                    amount = self.escape[2:-1]
                    if code in ("G", "H"):
                        self.column = max(0, int(amount or "1") - 1) if amount.isdigit() or not amount else 0
                    elif code in ("C", "D") and (amount.isdigit() or not amount):
                        self.column = max(0, self.column + (1 if code == "C" else -1) * int(amount or "1"))
                    self.escape = ""
                elif len(self.escape) > 32:
                    raise CaptureFailure("console_incomplete_output")
                continue
            if char == "\b":
                self.column = max(0, self.column - 1)
            elif char == "\r":
                self.column = 0
            elif char == " ":
                self.column += 1
            elif char == "\n":
                self.erasing = False
            else:
                self.buffer += " " * self.column + char
                self.erasing = False
        self.buffer += data[index:]
        marker = ASA_MORE.search(self.buffer)
        if marker is None:
            return False
        self.pages += 1
        if self.pages > 4096:
            raise CaptureFailure("console_output_limit")
        self.column = len(ANSI_CSI.sub("", marker.group()))
        self.buffer = self.buffer[: marker.start()]
        self.erasing = True
        return True


PLATFORM = ConsolePlatform(
    "cisco_asa",
    ("terminal pager 24",),
    ConfigurationFormat(r"^ASA Version \d", end=": end"),
    replay=ReplayPolicy(skip_prefixes=("ASA Version ", "Cryptochecksum:"), banners=False),
    enable=True,
    empty_enable=True,
    pager=ASAPager,
    backup_command="more system:running-config",
    save_commands=(Step("write memory"),),
    verifiable=True,
)
