"""Well-formed XML configuration text, checked without resolving anything the text declares.

PAN-OS keeps its configuration as one ``<config>`` document. A capture and a boot media file are both that document,
so both go through the same check: a plain parse that refuses DTDs, entities and processing instructions (a
configuration never has them), and that bounds what a hostile text could cost.
"""

import re
from xml.etree import ElementTree

MAX_DEPTH = 64
MAX_ELEMENTS = 200_000
# ``<!DOCTYPE`` / ``<!ENTITY`` and processing instructions other than the XML declaration.
FORBIDDEN = re.compile(r"<!(?:DOCTYPE|ENTITY)|<\?(?!xml[ \t\r\n?])", re.I)
DECLARATION = '<?xml version="1.0"?>'


def parse_config(text, root_tag="config"):
    """The document's root element, or None for text that is not a single well-formed ``<root_tag>`` document."""
    if FORBIDDEN.search(text):
        return None
    try:
        # No DTD, entity or processing instruction can reach the parser (FORBIDDEN above).
        root = ElementTree.fromstring(text)  # noqa: S314
    except (ElementTree.ParseError, ValueError, RecursionError):
        return None
    if root.tag != root_tag:
        return None
    count = 0
    stack = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        count += 1
        if depth > MAX_DEPTH or count > MAX_ELEMENTS:
            return None
        stack.extend((child, depth + 1) for child in element)
    return root


def serialize(root):
    """The document as UTF-8 text with an XML declaration and a final newline."""
    ElementTree.indent(root, space="  ")
    return (DECLARATION + "\n" + ElementTree.tostring(root, encoding="unicode") + "\n").encode("utf-8")
