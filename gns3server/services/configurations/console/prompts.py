"""What a console line looks like: login, password and shell prompts, and the last line of a transcript."""

import re

from ..shared.errors import CaptureFailure

PROMPT = re.compile(r"[A-Za-z0-9_./:-]{1,192}[#>]")

# A fragmented post-authentication banner can end exactly at "Last login:".
# It is history output, not a fresh request for a username.
LOGIN_PROMPT = re.compile(
    r"(?!last\s+login\s*:)(?:[A-Za-z0-9_.:-]{1,64}\s+)?(?:username|login(?:\s+as)?|user name):", re.I
)
PASSWORD_PROMPT = re.compile(r"password\s*:", re.I)
ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def last_line(text):
    tail = text.replace("\r\n", "\n").replace("\r", "\n").rstrip().split("\n")[-1]
    # Strip terminal decoration only from prompt framing, never configuration.
    return ANSI_CSI.sub("", tail).strip()


def prompt_tail(text, *, operational=None):
    tail = last_line(text)
    if re.fullmatch(r"[\w./:@*+-]{1,192}\([^()\r\n]*\)[#>]", tail) and not (
        operational and operational.fullmatch(tail)
    ):
        raise CaptureFailure("console_unsafe_mode")
    if re.search(
        r"initial configuration dialog|change.*password|old password|current password|new password|confirm password",
        text,
        re.I,
    ):
        raise CaptureFailure("console_not_ready")
    return tail
