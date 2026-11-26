"""Console recipe for Juniper Junos (capture only).

Junos startup is not replayed through the console: it is delivered as native boot media (see
``services/configurations/boot_media/profiles/juniper_vsrx.py``). This recipe serves the console capture of
``show configuration``. A vSRX NG logs in as ``root`` to a shell (``root@:~ #``) and the CLI is one command away:
the login dialog sends ``cli`` once, which leaves the node at the operational prompt (``root>``).
"""

import re

from ...shared.errors import CaptureFailure
from ...shared.junos_brace_balance import has_balanced_braces
from ..capture_format import ConfigurationFormat
from ..platforms import ConsolePlatform
from ..prompts import last_line

# ``root@:~ #`` or ``root@vsrx:~ #`` (Linux style) and ``root@vsrx%`` (FreeBSD style): the shell in front of the CLI.
SHELL_PROMPT = re.compile(r"[\w.-]*@[\w.-]*(?::[^\s#]*\s?#|%)")
# ``root>`` or ``root@vsrx>``: the CLI.
CLI_PROMPT = re.compile(r"[\w.-]{1,64}(?:@[\w.-]{0,64})?>")


class CliEntry:
    """The shell in front of the CLI: ``cli`` is sent once; a prompt that stays a shell prompt is a failure."""

    def __init__(self):
        self.sent = False

    @staticmethod
    def is_prompt(tail):
        return SHELL_PROMPT.fullmatch(tail) is not None

    def respond(self, text):
        if SHELL_PROMPT.fullmatch(last_line(text)) is None:
            return False, None
        if self.sent:
            raise CaptureFailure("console_not_ready")
        self.sent = True
        return True, "cli"


PLATFORM = ConsolePlatform(
    "juniper_junos",
    ("set cli screen-length 0", "set cli screen-width 0"),
    ConfigurationFormat(
        r"^(?:## Last (?:commit|changed):.*|version \S+;)$",
        required=(r"^version \S+;", r"^system \{"),
        end="}",
        validator=has_balanced_braces,
    ),
    capture_command="show configuration | no-more",
    operational=CLI_PROMPT,
    configuration=None,
    default_username="root",
    setup_dialog=CliEntry,
    restorer=None,
)
