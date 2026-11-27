"""What a startup preparation replaced on a node, so that it can be taken back before the launch.

The record, a small JSON file in the node folder, holds for each file the content it had before and a digest
of what the preparation left there. It counts only for the runtime generation it was written in and only while
that generation has not launched: guest saves, direct imports and later wipes are never undone.
"""

import hashlib
from contextlib import contextmanager
from pathlib import Path

from gns3server.schemas.configurations import MAX_FILE_BYTES

from .safe_io import atomic_bytes, read_json, stable_read, validate_owned_paths, write_json
from .startup_journal import journal_path, runtime, set_runtime_state

PENDING = ("clean", "prepared")


def record_path(node):
    # Named like the runtime journal.
    return journal_path(node).with_name(journal_path(node).name.replace("runtime", "preparation"))


def _digest(content):
    return None if content is None else hashlib.sha256(content).hexdigest()


def _text(content):
    """Any bytes as a JSON string, reversibly."""
    return None if content is None else content.decode("utf-8", errors="surrogateescape")


def _read(root, path):
    if not path.exists() and not path.is_symlink():
        return None
    return stable_read(str(root), path, MAX_FILE_BYTES)


def _inside(node, root, path):
    """``path`` (relative, or below the node folder as the node names it) below the resolved folder."""
    path = Path(path)
    folder = Path(node.working_dir).absolute()
    if path.is_absolute() and path.is_relative_to(folder):
        path = path.relative_to(folder)
    return root / path


def snapshot(node, paths):
    """The files as they are before a preparation writes them."""
    root = Path(node.working_dir).resolve(strict=True)
    paths = [_inside(node, root, path) for path in paths]
    return {path: _read(root, path) for path in paths}


def record(node, before, launch_files=None):
    """Remember a finished preparation; ``before`` is the ``snapshot`` taken ahead of it.

    ``launch_files`` is a ``snapshot`` of files the launch itself writes from the prepared text (NVRAM). While
    the generation has not launched, only a failed launch can have changed them, so they are put back as they were.
    """
    if not journal_path(node).exists():
        return
    root = Path(node.working_dir).resolve(strict=True)
    files = {}
    for path, previous in before.items():
        path = path.resolve() if path.exists() else path
        files[str(path.relative_to(root))] = {
            "previous": _text(previous),
            "prepared": _digest(_read(root, path)),
        }
    for path, previous in (launch_files or {}).items():
        files[str(path.relative_to(root))] = {"previous": _text(previous), "launch": True}
    write_json(record_path(node), {"generation": runtime(node)["generation"], "files": files})


@contextmanager
def keeping_ownership(node):
    """Around a server rewrite of node files (a rename): what was the preparation's before stays so."""
    if not journal_path(node).exists() or not record_path(node).exists():
        yield
        return
    value = read_json(record_path(node))
    root = Path(node.working_dir).resolve(strict=True)
    owned = [name for name, item in value["files"].items() if _digest(_read(root, root / name)) == item.get("prepared")]
    yield
    for name in owned:
        if "prepared" in value["files"][name]:
            value["files"][name]["prepared"] = _digest(_read(root, root / name))
    write_json(record_path(node), value)


def forget(node):
    record_path(node).unlink(missing_ok=True)


def withdraw(node):
    """Take back the pending preparation of a node that has not launched with it; True when there was one."""
    if not journal_path(node).exists() or not record_path(node).exists():
        return False
    value = read_json(record_path(node))
    current = runtime(node)
    pending = (
        isinstance(value, dict) and value.get("generation") == current["generation"] and current["state"] in PENDING
    )
    if pending:
        root = Path(node.working_dir).resolve(strict=True)
        paths = {root / name: item for name, item in value["files"].items()}
        validate_owned_paths(root, list(paths))
        for path, item in paths.items():
            # A file changed since the preparation is no longer the preparation's.
            if not item.get("launch") and _digest(_read(root, path)) != item["prepared"]:
                continue
            if item["previous"] is None:
                path.unlink(missing_ok=True)
            else:
                atomic_bytes(path, item["previous"].encode("utf-8", errors="surrogateescape"))
        if current["state"] == "prepared":
            set_runtime_state(node, "clean")
    forget(node)
    return pending
