"""Console recipe for MikroTik RouterOS."""

import re

from ...shared.errors import CaptureFailure
from ..capture_format import ConfigurationFormat, complete_quotes
from ..platforms import ERROR, ConsolePlatform
from ..prompts import LOGIN_PROMPT, last_line
from ..replay import ReplayPolicy, restore_cli

ROUTEROS_PROMPT = re.compile(r"\[[^\r\n\]]{1,160}\]\s*(?:/[^\r\n>]*)?>")


def routeros_backup(session, prompt):
    version = session.execute("/system resource print", prompt=prompt, preparation=True)
    match = re.search(r"(?m)^\s*version:\s*(\d+)\.", version)
    if match is None:
        raise CaptureFailure("device_version_unsupported")
    # RouterOS 7 hides secrets unless asked; RouterOS 6 prints them and rejects both flags
    # ("expected end of command"), so the plain export is already the complete one.
    return "/export terse show-sensitive" if int(match[1]) >= 7 else "/export terse"


def routeros_export_complete(content):
    return complete_quotes(content) and not re.search(r"(?im)^\s*#\s*error exporting\b", content)


EXPORT_HEADER = re.compile(r"\s*# (?:.* by RouterOS|.*RouterOS \d)")
RESET_CONFIRMATION = re.compile(r".*\[y/N\]:\s*", re.I)


def is_login_prompt(tail):
    return LOGIN_PROMPT.fullmatch(tail.strip()) is not None


def restore_routeros(session, content):
    """Replay; a startup apply of a full export first resets the router to an empty configuration.

    An export lists everything that differs from nothing, so replaying it on the factory defaults leaves
    the defaults the text does not mention (a DHCP client, for example) and fails on the ones it repeats.
    A short hand-written text, and an apply to a running node, only merge into the configuration.
    """
    if session.payload.get("startup") is True and EXPORT_HEADER.match(content):
        session.mark("prepare", "/system reset-configuration", 1, 1)
        session.send("/system reset-configuration no-defaults=yes skip-backup=yes")
        answer = session.wait(
            lambda text, tail: RESET_CONFIRMATION.fullmatch(tail) is not None or is_login_prompt(tail)
        )
        if RESET_CONFIRMATION.fullmatch(last_line(answer)):
            session.send("y")
            # The router reboots with an empty configuration: wait for its login prompt.
            session.wait(lambda text, tail: is_login_prompt(tail), check_errors=False)
        session.setup_dialog = session.platform.setup_dialog()
        session.mark("login")
        session.login()
    restore_cli(session, content)


class RouterOSLoginDialog:
    """Skip optional first-login screens without changing account credentials."""

    license_prompt = re.compile(r"Do you want to see the software license\?\s*\[Y/n\]:?", re.I)
    password_prompt = re.compile(r"new password>", re.I)

    def __init__(self):
        self.skippable = False
        self.skipped = False

    @classmethod
    def is_prompt(cls, tail):
        return bool(cls.license_prompt.fullmatch(tail) or cls.password_prompt.fullmatch(tail))

    def respond(self, text):
        tail = last_line(text)
        if self.license_prompt.fullmatch(tail):
            # This declines viewing the license text; it does not accept terms.
            return True, "n"
        if "Change your password (Ctrl-C to skip)" in text:
            self.skippable = True
        if not self.skipped and "Change your password" in text and not self.password_prompt.fullmatch(tail):
            return True, None
        if self.skippable and not self.skipped:
            if self.password_prompt.fullmatch(tail):
                self.skipped = True
                return True, "\x03"
            return True, None
        return False, None


PLATFORM = ConsolePlatform(
    "mikrotik_routeros",
    (),
    ConfigurationFormat(
        r"^# (?:.* by RouterOS|.*RouterOS \d)", required=(r"^/\S",), validator=routeros_export_complete
    ),
    capture_command="/export terse",
    filename="configuration.rsc",
    replay=ReplayPolicy(continuations=True),
    operational=ROUTEROS_PROMPT,
    command_prompt=ROUTEROS_PROMPT,
    strict_prompt=True,
    errors=re.compile(
        ERROR.pattern
        + r"|^\s*(?:expected end of command|expected command name|input does not match any value|no such item)\b"
    ),
    # A text exported from a router also lists the factory defaults, which a wiped router already has
    # ("failure: Server name ... already used", "failure: already have such address").
    tolerated_errors=re.compile(r"(?i)\balready (?:used|exist|have)"),
    # An `add` without a mandatory value (an export of an entry whose interface is gone) makes the CLI ask for it
    # ("interface:") and swallow the next command.
    input_prompt=re.compile(r"[a-z][a-z0-9-]*:"),
    empty_password=True,
    configuration_autosave=True,
    setup_dialog=RouterOSLoginDialog,
    restorer=restore_routeros,
    username_suffix="+ct511w4098h",
    default_username="admin",
    configuration=None,
    enter=(),
    finish=(),
    backup_command=routeros_backup,
)
