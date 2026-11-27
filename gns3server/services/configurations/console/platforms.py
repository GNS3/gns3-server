"""Shared console platform contracts and lazily loaded device recipes."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache

from gns3server.schemas.configurations import normalize_device_type

from ..shared.errors import CaptureFailure
from .prompts import LOGIN_PROMPT, PASSWORD_PROMPT, PROMPT, last_line
from .replay import ReplayPolicy, cli_commands, restore_cli

COMMAND_PROMPT = re.compile(r"[\w./:@*\[\] -]{1,192}(?:\([^\r\n]*\))?[#>]$")
PRIVILEGED_PROMPT = re.compile(r"[A-Za-z0-9_./:-]{1,192}#")
CONFIG_PROMPT = re.compile(r"[A-Za-z0-9_./:-]{1,192}\(config[^\r\n)]*\)#")
ERROR = re.compile(
    r"(?im)^(?:%\s*(?:Invalid|Error|Incomplete|Ambiguous|Unrecognized|Unknown|Failed|Access denied|Cannot|Unable|Certificate.*failed)|"
    r"\s*(?:syntax error|error:|error |invalid input|unknown command|bad command name|failure:|"
    r"MINOR:|MAJOR:|CRITICAL:|commit failed|failed to commit|Server error\s*:|Invalid syntax\.|Validation failed|"
    r"access denied|permission denied)|\s*<response\b[^>]*\bstatus=[\"']error[\"'])"
)


@dataclass(frozen=True)
class Step:
    command: str
    success: str | None = None
    prompt: str | None = None

    def run(self, session):
        response = session.execute(self.command)
        if self.success and not re.search(self.success, response, re.I):
            raise session.failure("configuration_apply_failed")
        if self.prompt and not re.fullmatch(self.prompt, last_line(response)):
            raise session.failure("configuration_apply_failed")
        return response


LOADER_PROMPT = re.compile(r"(?:rommon(?:\s+\d+)?\s*|grub|loader|boot)[>#]", re.I)

# A boot message that waits for Enter.
PRESS_RETURN = re.compile(r"Press (?:RETURN|ENTER) to get started[.!]?", re.I)


@dataclass(frozen=True)
class ConsolePlatform:
    name: str
    commands: tuple[str, ...]
    parser: Callable[[str, str], bytes | None]
    capture_command: str = "show running-config"
    filename: str = "running-config.cfg"
    operational: re.Pattern = PRIVILEGED_PROMPT
    command_prompt: re.Pattern = COMMAND_PROMPT
    errors: re.Pattern = ERROR
    # Errors that only report an item the device already has (a factory default added again): a replay goes on.
    tolerated_errors: re.Pattern | None = None
    # A prompt asking for a missing mandatory value. A replay cannot answer it: it cancels the prompt and fails.
    input_prompt: re.Pattern | None = None
    setup_dialog: Callable | None = None
    strict_prompt: bool = False
    username_suffix: str = ""
    # The account a console login uses when the node saves none.
    default_username: str = ""
    configuration: re.Pattern | None = CONFIG_PROMPT
    enable: bool = False
    empty_enable: bool = False
    empty_password: bool = False
    # A factory for the object that pages through output the device pauses (ASA "<--- More --->").
    pager: Callable[[], object] | None = None
    replay: ReplayPolicy = field(default_factory=ReplayPolicy)
    enter: tuple[Step, ...] = (Step("configure terminal"),)
    finish: tuple[Step, ...] = (Step("end"), Step("write memory"))
    # None: the platform can be captured but its startup is never replayed through
    # the console (it is delivered as native boot media instead).
    restorer: Callable | None = restore_cli
    backup_command: str | Callable | None = None
    # Declared only where the guest persists its running state with this
    # command at an EXEC prompt. An empty tuple makes the explicit
    # save-then-capture mode unsupported unless configuration_autosave is set.
    save_commands: tuple[Step, ...] = ()
    configuration_autosave: bool = False
    # A startup replay is confirmed by reading the configuration back (see verification.py).
    verifiable: bool = False

    def prompt_line(self, tail):
        if LOADER_PROMPT.fullmatch(tail):
            return False
        return (
            any(pattern.fullmatch(tail) for pattern in (self.operational, PROMPT, LOGIN_PROMPT, PASSWORD_PROMPT))
            or bool(self.configuration and self.configuration.fullmatch(tail))
            or bool(PRESS_RETURN.fullmatch(tail))
        )

    def tolerates(self, error_line):
        return self.tolerated_errors is not None and self.tolerated_errors.search(error_line) is not None

    def first_error_line(self, response):
        match = self.errors.search(response)
        if match is None:
            return ""
        return response[match.start() :].strip().replace("\r", "\n").split("\n")[0].strip()

    def console_ready(self, text):
        """Recognize an actionable prompt without answering it or changing mode."""
        tail = last_line(text)
        if self.prompt_line(tail):  # A loader prompt (IOS XE before its network OS) is not one: it ends in '>' too.
            return True
        setup_prompt = getattr(self.setup_dialog, "is_prompt", None)
        return bool(setup_prompt and not LOADER_PROMPT.fullmatch(tail) and setup_prompt(tail))

    def boot_dialog(self, session, tail):
        if not PRESS_RETURN.fullmatch(tail):
            return False
        session.send("")
        return True

    def operational_prompt(self, tail):
        return tail if self.operational.fullmatch(tail) else None

    def startup_exit(self, tail):
        """The command that leaves configuration mode when a startup apply finds the console in it."""
        return "end" if self.configuration and self.configuration.fullmatch(tail) else None

    def has_error(self, response):
        return self.errors.search(response) is not None

    @property
    def restorable(self):
        return self.restorer is not None

    def preflight(self, content):
        if self.restorer is None:
            raise CaptureFailure("configuration_apply_unsupported")
        # Validate multi-line blocks and continuations before modifying any device state.
        for _ in cli_commands(content, self.name):
            pass

    def restore(self, session, content):
        if self.restorer is None:
            raise CaptureFailure("configuration_apply_unsupported")
        self.restorer(session, content)

    def export_command(self, session, prompt, *, backup=False):
        if backup and self.backup_command:
            return self.backup_command(session, prompt) if callable(self.backup_command) else self.backup_command
        return self.capture_command

    @property
    def supports_save(self):
        return self.configuration_autosave or bool(self.save_commands)

    def save(self, session):
        """Persist running state when the platform needs an explicit save."""
        if self.configuration_autosave:
            return
        if not self.save_commands:
            raise CaptureFailure("configuration_save_unsupported")
        for step in self.save_commands:
            step.run(session)


@cache
def get_platforms() -> dict[str, ConsolePlatform]:
    """Load device recipes once, after the shared contracts are available.

    Device modules import ConsolePlatform from this module. Deferring their
    imports also allows callers to import a device module first.
    """
    from .recipes import get_recipe_modules

    platforms = {}
    for module in get_recipe_modules():
        platform = getattr(module, "PLATFORM", None)
        if platform is not None:
            if platform.name in platforms:
                raise RuntimeError(f"Duplicate console platform: {platform.name}")
            platforms[platform.name] = platform
    return platforms


def get_platform(name):
    try:
        return get_platforms()[normalize_device_type(name)]
    except (KeyError, TypeError):
        raise CaptureFailure("device_type_unsupported") from None
