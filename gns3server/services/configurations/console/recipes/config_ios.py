"""Console recipe for Cisco IOS and IOS-XE."""

import re
import secrets

from ...shared.errors import CaptureFailure
from ..capture_format import ConfigurationFormat
from ..platforms import ConsolePlatform, Step
from ..prompts import PROMPT, last_line
from ..replay import ReplayPolicy, restore_ios


class IOSInitialConfiguration:
    def __init__(self):
        self.phase = "idle"
        self.secret = ""
        self.autoinstall_terminated = False

    @staticmethod
    def is_prompt(tail):
        return (
            re.fullmatch(
                r"Would you like to enter the initial configuration dialog\?\s*\[yes/no\]:|"
                r"Would you like to terminate autoinstall\?\s*\[yes\]:|"
                r"(?:Enter|Confirm) enable secret:|Enter your selection\s*\[2\]:",
                tail,
                re.I,
            )
            is not None
        )

    def respond(self, text):
        """Return (handled, command); None waits for more of the dialogue."""
        tail = last_line(text)
        if re.fullmatch(r"Would you like to enter the initial configuration dialog\?\s*\[yes/no\]:", tail, re.I):
            if self.phase != "idle":
                raise CaptureFailure("console_not_ready")
            self.phase = "waiting"
            return True, "no"
        if re.fullmatch(r"Would you like to terminate autoinstall\?\s*\[yes\]:", tail, re.I):
            return self.terminate_autoinstall()
        if "initial configuration dialog" in text.lower():
            # A serial read can end before the rest of the question arrives.
            return True, None
        if re.fullmatch(r"Enter enable secret:", tail, re.I):
            if self.phase not in ("idle", "waiting"):
                raise CaptureFailure("console_not_ready")
            # 23 characters, including upper/lower case and a digit; hex cannot
            # contain the forbidden word "cisco". Never persist this value.
            self.secret = "Aa1" + secrets.token_hex(10)
            self.phase = "confirmation"
            return True, self.secret
        if re.fullmatch(r"Confirm enable secret:", tail, re.I):
            if self.phase != "confirmation":
                raise CaptureFailure("console_not_ready")
            secret, self.secret = self.secret, ""
            self.phase = "selection"
            return True, secret
        if re.fullmatch(r"Enter your selection\s*\[2\]:", tail, re.I):
            discard = re.search(r"\[0\]\s+Go to the IOS command prompt without saving this config\.", text, re.I)
            if self.phase != "selection" or not discard:
                raise CaptureFailure("console_not_ready")
            self.phase = "cli"
            return True, "0"
        if self.phase != "idle":
            if re.search(r"%\s*(?:Invalid input|No defaulting allowed|.*(?:do not match|mismatch))", text, re.I):
                raise CaptureFailure("console_not_ready")
            if re.fullmatch(r"Press (?:RETURN|ENTER) to get started[.!]?", tail, re.I):
                return True, ""
            if PROMPT.fullmatch(tail):
                self.secret = ""
                self.phase = "idle"
                return False, None
            return True, None
        return False, None

    def terminate_autoinstall(self):
        if self.phase not in ("idle", "waiting") or self.autoinstall_terminated:
            raise CaptureFailure("console_not_ready")
        self.autoinstall_terminated = True
        self.phase = "waiting"
        return True, "yes"


PLATFORM = ConsolePlatform(
    "cisco_ios_telnet",
    ("terminal length 0", "terminal width 511"),
    ConfigurationFormat(
        r"^[ \t]*Current configuration : \d+ bytes[ \t]*$",
        required=(r"^version \d",),
        end="end",
        banners=True,
        skip_header=True,
    ),
    replay=ReplayPolicy(
        skip_prefixes=("version ",), skip_lines=("boot-start-marker", "boot-end-marker"), certificates=True
    ),
    enable=True,
    setup_dialog=IOSInitialConfiguration,
    restorer=restore_ios,
    save_commands=(Step("write memory"),),
    verifiable=True,
)
