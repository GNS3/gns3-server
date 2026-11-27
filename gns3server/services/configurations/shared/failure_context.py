"""The safe, masked context of a failed console step: stage, command index, masked command and device error."""

import re

MASK = "<masked>"
FAILURE_PHASES = frozenset(
    {
        # Generic CLI replay and capture.
        "login",
        "ready",
        "console-wait",
        "prepare",
        "enter",
        "replay",
        "save",
    }
)
COMMAND_LIMIT = 160
DEVICE_ERROR_LIMIT = 250
_QUOTED = re.compile(r"\"[^\"]*(?:\"|$)|'[^']*(?:'|$)")
_HASHED = re.compile(r"\$\d\w?\$")
_SENSITIVE = re.compile(
    r"(?i)(?:[\w-]*[-_])?(?:password|passwd|secret|key|key-string|community|hash|passphrase|token|psk|credentials?)s?"
)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def mask_text(value, limit):
    """Reduce one device/configuration line to a keyword path that is safe to show.

    Quoted strings, hashed values and everything after a credential-like keyword
    (password, secret, key, community, hash, ...) or an SNMP ``host`` is replaced;
    long opaque tokens are replaced too. The result is truncated to ``limit`` characters.
    """
    if not isinstance(value, str):
        return ""
    value = _CONTROL.sub(" ", _QUOTED.sub(MASK, value[:4096]))
    tokens = []
    words = value.split()
    for position, word in enumerate(words):
        if _HASHED.search(word) or len(word) > 48:
            tokens.append(MASK)
            continue
        name, assigned, argument = word.partition("=")
        if assigned and argument and _SENSITIVE.fullmatch(name.strip(":,;()[]")):
            # RouterOS and similar write ``keyword=value``.
            tokens.append(f"{name}={MASK}")
            continue
        tokens.append(word)
        keyword = word.strip(":,;=()[]")
        lowered = keyword.lower()
        previous = words[position - 1].lower() if position else ""
        if (
            _SENSITIVE.fullmatch(keyword)
            or (lowered == "text" and previous == "authentication")
            # SNMP trap receivers: the community is a positional argument somewhere after ``host``.
            or (lowered == "host" and any("snmp" in earlier.lower() for earlier in words[:position]))
            # SNMPv3: ``auth <algorithm> <password> priv <algorithm> <password>``.
            or (lowered in ("auth", "priv") and words[0].lower().startswith("snmp"))
        ):
            if position + 1 < len(words):
                tokens.append(MASK)
            break
    result = " ".join(tokens)
    return result if len(result) <= limit else result[: limit - 3] + "..."


def failure_context(value):
    """Accept only bounded, masked stage/index/command metadata, never raw config or output."""
    if not isinstance(value, dict) or not isinstance(value.get("phase"), str) or value["phase"] not in FAILURE_PHASES:
        return {}
    result = {"phase": value["phase"]}
    for source in ("command_index", "command_total"):
        number = value.get(source)
        if type(number) is int and 1 <= number <= 1_000_000:
            result[source] = number
    for source, limit in (("command", COMMAND_LIMIT), ("device_error", DEVICE_ERROR_LIMIT)):
        text = mask_text(value.get(source), limit)
        if text:
            result[source] = text
    return result


def describe_failure(context):
    """One log/notification line from a sanitized context (never config content)."""
    context = failure_context(context)
    if not context:
        return ""
    parts = [f"phase={context['phase']}"]
    if "command_index" in context:
        parts.append(f"command={context['command_index']}/{context.get('command_total', '?')}")
    if "command" in context:
        parts.append(f"sent='{context['command']}'")
    if "device_error" in context:
        parts.append(f"device='{context['device_error']}'")
    return " ".join(parts)
