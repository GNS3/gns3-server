"""Console application of explicitly enabled project configurations.

CLI families replay the configuration into running state and save/commit it.
This is a merge on CLI platforms, not a factory reset. No disk image edits.
"""

import re
from dataclasses import dataclass

from ..shared.banners import delimited_banner
from ..shared.errors import CaptureFailure
from .prompts import last_line


@dataclass(frozen=True)
class ReplayPolicy:
    skip_prefixes: tuple[str, ...] = ()
    skip_lines: tuple[str, ...] = ()
    banners: bool = True
    continuations: bool = False
    certificates: bool = False


# Time allowed for one console restore that is not a boot-time startup apply.
BASE_RESTORE_SECONDS = 115
MAX_RESTORE_SECONDS = 600
SECONDS_PER_COMMAND = 4


def restore_seconds(content):
    """Time allowed for a whole console replay: a base bound, longer for long configurations.

    Appliances take seconds per command on some steps (key and certificate work), so a fixed bound
    that suits a short configuration expires halfway through a full running-config.
    """
    lines = sum(1 for line in (content or "").splitlines() if line.strip() and not line.lstrip().startswith("!"))
    return min(MAX_RESTORE_SECONDS, max(BASE_RESTORE_SECONDS, 30 + SECONDS_PER_COMMAND * lines))


def cli_commands(content, driver):
    """Remove display framing, keeping multiline banners as a single exchange."""
    from .platforms import get_platform

    policy = get_platform(driver).replay
    lines = iter(content.replace("\r\n", "\n").replace("\r", "\n").splitlines())
    certificate_chain = False
    for line in lines:
        stripped = line.strip()
        if policy.certificates:
            if stripped.startswith("crypto pki certificate chain "):
                certificate_chain = True
            elif stripped.startswith("!"):
                certificate_chain = False
            elif certificate_chain and re.fullmatch(r"certificate(?: (?:ca|self-signed))? [0-9a-fA-F]+", stripped):
                yield ios_certificate_block(stripped, lines)
                continue
        if policy.continuations:
            line = continued_line(line, lines)
            stripped = line.strip()
        if not stripped or stripped.startswith(("!", "#", ":")) or stripped in ("end",):
            continue
        if stripped.startswith(policy.skip_prefixes) or stripped in policy.skip_lines:
            continue
        banner = re.match(r"^banner (\S+) (.+)$", stripped)
        if banner and policy.banners:
            text = delimited_banner(banner.group(2), lines)
            if text is None:
                raise CaptureFailure("configuration_invalid_content")
            yield f"banner {banner.group(1)} {text}"
        else:
            yield line


def continued_line(line, lines):
    while line.endswith("\\"):
        try:
            line = line[:-1] + next(lines).lstrip()
        except StopIteration:
            raise CaptureFailure("configuration_invalid_content") from None
    return line


def ios_certificate_block(header, lines):
    values = [header]
    for line in lines:
        value = line.strip()
        if value == "quit":
            if len(values) < 2:
                break
            return "\n".join([*values, "quit"])
        if not re.fullmatch(r"[0-9a-fA-F ]+", value):
            break
        values.append(value)
    raise CaptureFailure("configuration_invalid_content")


HEX_MODE = re.compile(r"hexadecimal|\(config-pki-hexmode\)#", re.I)


def restore_ios_certificate(session, value):
    """Import one certificate: the node enters hex mode (the prompt or the banner says so), then takes the data."""
    lines = value.splitlines()
    session.send(lines[0])
    # A node that already holds this certificate may return to the plain prompt: nothing to import then.
    answer = session.wait(
        lambda text, tail: HEX_MODE.search(text) or session.platform.command_prompt.fullmatch(tail),
        echo=lines[0],
    )
    if not HEX_MODE.search(answer):
        return
    for line in lines[1:-1]:
        session.send(line)
        session.wait(lambda text, _: "\n" in text)
    session.execute("quit")


def apply_line(session, line):
    if session.platform.replay.certificates and line.startswith("certificate ") and "\n" in line:
        restore_ios_certificate(session, line)
    else:
        session.execute(line)


def restore_cli(session, content, *, enter=None, finish=None):
    """Replay; failures carry the sanitized stage, index and masked command."""
    result = ""
    session.mark("enter")
    for step in session.platform.enter if enter is None else enter:
        step.run(session)
    commands = list(cli_commands(content, session.driver))
    for index, line in enumerate(commands, 1):
        session.mark("replay", line.split("\n", 1)[0], index, len(commands))
        apply_line(session, line)
    session.mark("save")
    for step in session.platform.finish if finish is None else finish:
        result = step.run(session)
    return result


def restore_ios(session, content):
    """Use the running IOS XE mode's configuration/persistence workflow."""
    from .platforms import Step

    configuration_prompt = r"[A-Za-z0-9_./:-]{1,192}\(config\)#"

    session.mark("prepare")
    mode = session.execute("show version | include operating mode")
    if not re.search(r"(?im)^\s*Router operating mode:\s*Controller-Managed\s*$", mode):
        restore_cli(session, content, enter=(Step("configure terminal", prompt=configuration_prompt),))
        return
    finished = restore_cli(
        session,
        content,
        enter=(Step("config-transaction", prompt=configuration_prompt),),
        finish=(Step("commit", r"(?im)^\s*Commit complete\.[ \t]*\r?$"), Step("end")),
    )
    if not session.platform.operational.fullmatch(last_line(finished)):
        session.mark("save")
        raise session.failure("configuration_apply_failed")
