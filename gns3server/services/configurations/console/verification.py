"""Compare IOS-style configuration commands in their parent scopes.

A device does not print everything it was given: it leaves out the commands that restate a default (``no shutdown``
on an interface that is up) and a text typed without indentation has no parent lines to compare. Neither is
treated as a mismatch: a ``no`` command counts only when the capture can prove or contradict it, and an
unindented text is placed under the parent lines the capture shows.
"""

import re

TOKENS = re.compile(r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s"']+|["']""")
FRAMING = re.compile(r"^(?:[!#:]|(?:end|exit(?:-address-family)?)$)", re.I)
# Devices often re-encode these values. Their equality cannot be verified from a capture.
NEGATED = re.compile(r"^no (.+)$", re.I)
REENCODED = re.compile(r"^(?:enable (?:secret|password)\b|username .*\b(?:secret|password)\b)", re.I)


def scoped_lines(content):
    parents = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        indent = len(raw[: len(raw) - len(raw.lstrip())].expandtabs(8))
        while parents and parents[-1][0] >= indent:
            parents.pop()
        if FRAMING.match(line):
            continue
        value = " ".join(TOKENS.findall(line))
        if not REENCODED.match(value):
            yield (*[parent for _, parent in parents], value)
        parents.append((indent, value))


def is_flat(content):
    """True when no comparable line is indented: the text carries no parent lines of its own."""
    return all(not raw[:1].isspace() for raw in content.splitlines() if raw.strip() and not FRAMING.match(raw.strip()))


def flat_scoped_lines(content, present):
    """The scoped lines of an unindented text, each placed under the parent line of the capture it follows."""
    parents = {path[:size] for path in present for size in range(1, len(path))}
    scope = ()
    for path in scoped_lines(content):
        value = path[-1]
        if scope and (*scope, value) in present:
            yield (*scope, value)
        elif (value,) in parents or (value,) in present:
            scope = (value,) if (value,) in parents else ()
            yield (value,)
        else:
            yield (*scope, value)


def restore_verified(uploaded, captured):
    """Return verification and scoped coverage, or None when there is nothing comparable."""
    present = set(scoped_lines(captured))
    expected = list(flat_scoped_lines(uploaded, present) if is_flat(uploaded) else scoped_lines(uploaded))
    matched = checked = 0
    for path in expected:
        if path in present:
            matched += 1
            checked += 1
            continue
        negated = NEGATED.match(path[-1])
        if negated and (*path[:-1], negated[1]) not in present:
            continue  # A default the device does not print: the capture says nothing about it.
        checked += 1
    if not checked:
        return None, None
    coverage = matched / checked
    return coverage == 1, coverage
