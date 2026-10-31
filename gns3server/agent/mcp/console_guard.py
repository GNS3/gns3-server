#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: Yue Guobin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
TUI guard for the MCP console tools — data separated from logic so the
rule tables can be updated on their own cadence.

Two rule sources, merged at load time (same pattern as the copilot's
command_filter):

  1. Builtin tables below (always present; the fallback).
  2. The GNS3-Skills repository file `config/console_guard.txt`, which
     OVERRIDES matching builtin entries and can remove them with
     '!family: head'. Update path: edit the skills repo, git pull,
     restart (or hot-reload once wired) — no server release needed.

The file lives in the skills repo (not forbidden_commands.txt, which
serves the copilot batch tools with different semantics: long-running
command bans vs. screen-interactive commands here).

Matching is deliberately lexical — first word's basename, one flag
presence check, no shell parsing — to keep false positives near zero.
Every rejection carries the non-interactive alternative; nothing is
rewritten silently.
"""

import logging
import threading
from typing import Any

log = logging.getLogger(__name__)

VALID_FAMILIES = ("shell", "netos")

# Builtin rules: family -> {head word: suggestion}. "{cmd}" expands to the
# word after the command (used by man). Keep this table SMALL and
# high-confidence: a false reject blocks a legitimate command.
DEFAULT_GUARD_TABLES: dict[str, dict[str, str]] = {
    "shell": {
        "top": "top -b -n 1",
        "htop": "htop has no batch mode — use 'ps aux'",
        "vim": "edit files with node_file_write instead",
        "vi": "edit files with node_file_write instead",
        "nano": "edit files with node_file_write instead",
        "emacs": "edit files with node_file_write instead",
        "less": "cat <file>",
        "more": "cat <file>",
        "man": "{cmd} --help",
        "watch": "run the command directly once",
        "python": "python -c '<code>'",
        "python3": "python3 -c '<code>'",
        "node": "node -e '<code>'",
        "mysql": "mysql -e '<sql>'",
        "psql": "psql -c '<sql>'",
        "sqlite3": "sqlite3 <db> '<sql>'",
        "passwd": "not supported over the MCP console",
        "su": "not supported over the MCP console",
        "ssh": "not supported over the MCP console",
        "telnet": "not supported over the MCP console",
    },
    "netos": {
        "setup": "configure with config commands instead",
    },
}

# Commands whose suggested form is the SAME command with a flag: once the
# flag is present, the command IS the non-interactive form and must pass.
# (Not expressible in the rules file — this is logic, not data.)
BATCH_FLAG_OK = {
    "top": "-b",  # top -b -n 1 is exactly what the guard suggests
}

# ── Rules file parsing (pure, unit-tested) ────────────────────────────────


def parse_guard_file(text: str) -> tuple[dict[str, dict[str, str]], list[tuple[str, str]]]:
    """Parse console_guard.txt content.

    Line format:
        family: head -> suggestion      add/override a rule
        family: head                    add/override, block without suggestion
        !family: head                   remove the builtin rule

    Returns (overrides, removals); invalid lines are skipped with a log.
    """
    overrides: dict[str, dict[str, str]] = {}
    removals: list[tuple[str, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        remove = line.startswith("!")
        if remove:
            line = line[1:].strip()
        if ":" not in line:
            log.warning("console_guard: skipping malformed line %d: %r", lineno, raw)
            continue
        family, _, rest = line.partition(":")
        family = family.strip().lower()
        if family not in VALID_FAMILIES:
            log.warning("console_guard: unknown family on line %d: %r", lineno, raw)
            continue
        if remove:
            removals.append((family, rest.strip().lower()))
            continue
        parts = rest.split("->", 1)
        head = parts[0].strip().lower()
        suggestion = parts[1].strip() if len(parts) == 2 else ""
        if not head or " " in head:
            log.warning("console_guard: bad head word on line %d: %r", lineno, raw)
            continue
        overrides.setdefault(family, {})[head] = suggestion
    return overrides, removals


# ── Merged table loading ──────────────────────────────────────────────────

_lock = threading.Lock()
_tables: dict[str, dict[str, str]] | None = None

GUARD_FILE_RELATIVE_PATH = "config/console_guard.txt"


def _read_skills_guard_file() -> str | None:
    """Read console_guard.txt from the skills repository, if present."""
    try:
        from gns3server.agent.gns3_copilot.skills.registry import get_skills_manager

        manager = get_skills_manager()
        if manager is None:
            return None
        guard_file = manager.skills_dir / GUARD_FILE_RELATIVE_PATH
        if not guard_file.exists():
            return None
        return guard_file.read_text(encoding="utf-8")
    except Exception as e:
        log.debug("console_guard: skills repository unavailable: %s", e)
        return None


def _build_tables() -> dict[str, dict[str, str]]:
    tables = {family: dict(rules) for family, rules in DEFAULT_GUARD_TABLES.items()}
    text = _read_skills_guard_file()
    if text is None:
        return tables
    overrides, removals = parse_guard_file(text)
    for family, head in removals:
        tables.get(family, {}).pop(head, None)
    for family, rules in overrides.items():
        tables.setdefault(family, {}).update(rules)
    log.info(
        "console_guard: %d override(s), %d removal(s) from skills repository",
        sum(len(r) for r in overrides.values()),
        len(removals),
    )
    return tables


def get_guard_tables() -> dict[str, dict[str, str]]:
    """Merged guard tables (builtin + skills-repo overrides), cached."""
    global _tables
    with _lock:
        if _tables is None:
            _tables = _build_tables()
        return _tables


def reload_console_guard() -> None:
    """Drop the cache so the next check re-reads the skills repository."""
    global _tables
    with _lock:
        _tables = None


# ── The check itself ──────────────────────────────────────────────────────


def _has_control_keys(command: str) -> bool:
    """Keystroke-style input (Ctrl-C etc.) — guard does not apply."""
    return any(ord(c) < 32 and c not in "\n\r\t" for c in command)


def guard_command(command: str, family: str) -> dict[str, Any] | None:
    """Screen one command against the family's interactive-TUI table.

    Returns a rejection dict (with a suggestion) or None to allow.
    Never rewrites silently — the caller must see what was blocked and why.
    """
    if _has_control_keys(command):
        return None
    tokens = command.strip().split()
    if not tokens:
        return None
    head = tokens[0].rsplit("/", 1)[-1]  # /usr/bin/top -> top
    # Already in its batch form (top -b ...) — rejecting it would block the
    # very suggestion this guard returns.
    batch_flag = BATCH_FLAG_OK.get(head)
    if batch_flag is not None and any(t.startswith(batch_flag) for t in tokens[1:]):
        return None
    table = get_guard_tables().get(family, {})
    if head in table:
        suggestion = table[head]
        if suggestion and head == "man" and len(tokens) > 1:
            suggestion = suggestion.replace("{cmd}", tokens[1])
        if suggestion:
            return {
                "status": "rejected",
                "error": f"'{head}' is screen-interactive and would hang this console; the non-interactive form is required",
                "suggestion": suggestion,
            }
        # Rule exists with an empty suggestion: block without advice.
        return {
            "status": "rejected",
            "error": f"'{head}' is screen-interactive and would hang this console",
            "suggestion": None,
        }
    if head == "tail" and "-f" in tokens:
        return {
            "status": "rejected",
            "error": "'tail -f' is screen-interactive and would hang this console; the non-interactive form is required",
            "suggestion": "tail -n 50 <file>",
        }
    return None
