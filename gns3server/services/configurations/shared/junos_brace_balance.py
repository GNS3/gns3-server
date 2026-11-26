"""Brace-balance check for hierarchical configuration text (Junos ``show configuration`` format)."""


def has_balanced_braces(config: str) -> bool:
    """True when every ``{`` of the configuration is closed.

    Braces inside quoted strings and comments do not count: ``#`` (and ``##``) to the end of the line, and
    ``/* ... */`` blocks, as the Junos configuration loader reads them.
    """
    depth = 0
    quoted = escaped = block = False
    for line in config.splitlines():
        index = 0
        while index < len(line):
            char = line[index]
            if block:
                if line.startswith("*/", index):
                    block = False
                    index += 1
            elif quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == "#":
                break
            elif line.startswith("/*", index):
                block = True
                index += 1
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth < 0:
                    return False
            index += 1
        escaped = False
    return depth == 0 and not quoted and not block
