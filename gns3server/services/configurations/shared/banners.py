"""The ``banner <type> <delimiter>body<delimiter>`` syntax of IOS-like configurations."""

# Delimiters a rewritten banner may use: the first one its text does not contain.
DELIMITERS = "%~|@"


def banner_marker(value):
    """What closes the banner whose text starts with ``value``: one character, or a ``^C`` style pair."""
    return value[:2] if value.startswith("^") else value[:1]


def delimited_banner(value, lines):
    """``value`` and as many following ``lines`` as the banner spans, between delimiters safe to type or load.

    None when the banner never ends or every delimiter occurs in its text.
    """
    marker = banner_marker(value)
    body = value[len(marker) :]
    while marker not in body:
        line = next(lines, None)
        if line is None:
            return None
        body += "\n" + line
    body = body.split(marker, 1)[0]
    delimiter = next((char for char in DELIMITERS if char not in body), None)
    return None if delimiter is None else f"{delimiter}{body}{delimiter}"
