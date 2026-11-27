"""The durable startup journal of a node: which generation of its runtime it is in, and what that allows.

A small JSON file in the node's working folder. A wipe starts a new ``clean`` generation, the first start after it
consumes the generation (``initialized``), and an interrupted wipe or preparation (``resetting``, ``preparing``)
blocks the next start until it is repeated. ``legacy_existing`` marks a runtime that predates the journal or was
filled by a direct import, so its guest state is never replaced by a saved set.
"""

from pathlib import Path

from .errors import ConfigurationError
from .safe_io import read_json, write_json

VERSION = 1
STATES = frozenset({"legacy_existing", "resetting", "preparing", "clean", "prepared", "initialized"})
INTERRUPTED = ("resetting", "preparing")


def journal_path(node):
    identifier = getattr(node, "dynamips_id", None)
    if type(identifier) is int:
        return Path(node.working_dir) / f".startup-runtime-i{identifier}.json"
    return Path(node.working_dir) / ".startup-runtime.json"


def _entry(generation, state):
    return {"version": VERSION, "generation": generation, "state": state}


def _write(node, generation, state):
    write_json(journal_path(node), _entry(generation, state))


def _refuse_interrupted(value):
    if value["state"] in INTERRUPTED:
        raise ConfigurationError("configuration_outcome_unknown")


def runtime(node):
    """The node's journal; a node without one is a ``legacy_existing`` runtime of generation 0."""
    value = read_json(journal_path(node), _entry(0, "legacy_existing"))
    if (
        not isinstance(value, dict)
        or value.get("version") != VERSION
        or type(value.get("generation")) is not int
        or value["generation"] < 0
        or value.get("state") not in STATES
    ):
        raise ConfigurationError("invalid_startup_runtime")
    return value


def require_launchable(node):
    """Refuse a launch while an earlier reset or preparation was interrupted."""
    if journal_path(node).exists():
        _refuse_interrupted(runtime(node))


def mark_started(node):
    # Called immediately before emulator launch: even a failed/ambiguous launch
    # consumes preparation. Never replay a bootstrap after a lost start reply.
    # Boot media nodes call it only once the guest is running (see QemuVM.start):
    # media is safe to attach again, and losing it would boot a factory config.
    if not journal_path(node).exists():
        return
    value = runtime(node)
    _refuse_interrupted(value)
    # Keep every other key: boot media nodes record what was prepared for them (see set_runtime_state).
    write_json(journal_path(node), {**value, "state": "initialized"})


def native_runtime_owned(node):
    """An enrolled IOU runtime uses NVRAM, not the legacy text-file cache.

    A prepared set is not in NVRAM yet: the launch takes it from the startup text.
    """
    if not journal_path(node).exists():
        return False
    value = runtime(node)
    _refuse_interrupted(value)
    return value["state"] not in ("legacy_existing", "prepared")


def native_save_allowed(node):
    return not journal_path(node).exists() or runtime(node)["state"] in ("initialized", "legacy_existing")


def mark_legacy_import(node):
    if journal_path(node).exists():
        value = runtime(node)
        _refuse_interrupted(value)
        _write(node, value["generation"], "legacy_existing")


def mark_set_prepared(node):
    """A startup set was written for the next launch. A clean generation stays pending until that launch."""
    if not journal_path(node).exists():
        return
    value = runtime(node)
    _refuse_interrupted(value)
    _write(node, value["generation"], "prepared" if value["state"] in ("clean", "prepared") else "legacy_existing")


# Marks a node folder that has just been created, for nodes whose files cannot tell whether they ever ran.
NEW_MARKER = ".startup-new"


def mark_new_runtime(node):
    (Path(node.working_dir) / NEW_MARKER).touch()


def forget_new_runtime(node):
    (Path(node.working_dir) / NEW_MARKER).unlink(missing_ok=True)


def is_new_runtime(node):
    return (Path(node.working_dir) / NEW_MARKER).is_file()


def mark_wiped(node):
    # A successful first wipe is a clean generation too. Requiring a previous
    # restore journal left newly uploaded startup files outside the boot path.
    _write(node, runtime(node)["generation"] + 1, "clean")


def set_runtime_state(node, state, **details):
    """Change the lifecycle state of an existing or new journal, keeping its generation."""
    generation = runtime(node)["generation"] if journal_path(node).exists() else 0
    write_json(journal_path(node), {**_entry(generation, state), **details})
