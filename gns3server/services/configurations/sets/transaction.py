"""Recover an interrupted commit across the set and selection files."""

from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.safe_io import (
    MAX_JSON_BYTES,
    atomic_bytes,
    fsync_directory,
    read_json,
    stable_read,
    write_json,
)

JOURNAL = ".sets-transaction"


def recover(root):
    """Finish recovery before reading either file, under the project store lock."""
    journal = root / JOURNAL
    if not journal.exists() and not journal.is_symlink():
        return
    record = stable_read(str(root), journal, MAX_JSON_BYTES)
    header, separator, previous = record.partition(b"\n")
    if not separator or not header.startswith(b"1:") or not header[2:].isdigit() or len(header) > 24:
        raise ConfigurationError("invalid_startup_configurations")
    committed_revision = int(header[2:])
    selections = read_json(root / "nodes" / "selections.json", {"revision": 0})
    revision = selections.get("revision") if isinstance(selections, dict) else None
    if committed_revision < 1 or type(revision) is not int or revision < committed_revision - 1:
        raise ConfigurationError("invalid_startup_configurations")
    if revision == committed_revision - 1:
        # Selection revision is the commit point. Restore the exact old bytes on rollback.
        path = root / "configurations.json"
        if previous:
            current = stable_read(str(root), path, MAX_JSON_BYTES) if path.exists() or path.is_symlink() else None
            if current != previous:
                atomic_bytes(path, previous)
        else:
            path.unlink(missing_ok=True)
            fsync_directory(root)
    journal.unlink()
    fsync_directory(root)


def commit(root, payload, selections):
    """Replace both manifests under the project store lock."""
    path = root / "configurations.json"
    if selections is None:
        atomic_bytes(path, payload)
        return
    previous = stable_read(str(root), path, MAX_JSON_BYTES) if path.exists() or path.is_symlink() else b""
    atomic_bytes(root / JOURNAL, f"1:{selections['revision']}\n".encode() + previous)
    try:
        atomic_bytes(path, payload)
        write_json(root / "nodes" / "selections.json", selections)
    finally:
        # Also runs after a write error. If rollback itself fails, the journal
        # stays on disk and the next reader must recover before serving data.
        recover(root)
