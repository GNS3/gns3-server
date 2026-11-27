"""Recognising a complete configuration in a captured transcript: header, required lines, framing and banners."""

import re
from collections.abc import Callable
from dataclasses import dataclass

from ..shared.banners import banner_marker
from .prompts import last_line


def _configuration_lines(transcript, prompt):
    text = transcript.replace("\r\n", "\n").replace("\r", "\n")
    # A complete prompt may be followed by CR/LF in the same transport read.
    # Ignore only trailing empty lines; retain all configuration framing checks.
    lines = text.rstrip("\n").split("\n")
    if not lines or last_line(lines[-1]) != prompt:
        return None
    return lines[:-1]


def _complete_banners(config, *, end_marker=None):
    delimiter = None
    end = False
    for index, line in enumerate(config):
        if delimiter is not None:
            if delimiter in line:
                delimiter = None
            continue
        banner = re.match(r"^banner \S+ (.+)$", line)
        if banner:
            value = banner.group(1)
            marker = banner_marker(value)
            if marker not in value[len(marker) :]:
                delimiter = marker
            continue
        if line == end_marker:
            end = index == len(config) - 1
    return delimiter is None and (end_marker is None or end)


def _trim_config(lines):
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _config_bytes(lines):
    return ("\n".join(lines) + "\n").encode("utf-8")


@dataclass(frozen=True)
class ConfigurationFormat:
    header: str
    required: tuple[str, ...] = ()
    end: str | None = None
    banners: bool = False
    skip_header: bool = False
    validator: Callable[[str], bool] | None = None

    def __call__(self, transcript, prompt):
        lines = _configuration_lines(transcript, prompt)
        if lines is None:
            return None
        text = "\n".join(lines)
        header = re.search(self.header, text, re.M)
        if header is None:
            return None
        lines = _trim_config(text[header.end() if self.skip_header else header.start() :].splitlines())
        if not lines:
            return None
        config = "\n".join(lines)
        if any(not re.search(pattern, config, re.M) for pattern in self.required):
            return None
        if self.end and lines[-1].strip() != self.end:
            return None
        if self.banners and not _complete_banners(lines, end_marker=self.end):
            return None
        if self.validator and not self.validator(config):
            return None
        return _config_bytes(lines)


def complete_quotes(content):
    quoted = False
    escaped = False
    for char in content:
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
    return not quoted and not escaped
