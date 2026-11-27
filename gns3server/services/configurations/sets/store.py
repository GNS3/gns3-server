"""Persistence of a project's startup configurations: the named sets and the per-node assignments.

Both live under ``project-files/startup-configs`` of the project; every write goes through one
per-project lock and an optimistic revision check.
"""

import hashlib
import json
import threading
from pathlib import Path
from uuid import UUID

from gns3server.schemas.configurations import (
    DEFAULT_SET,
    ConfigurationSet,
    StartupDocument,
)
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.safe_io import stable_read

from . import transaction
from .revisions import read_revision

MAX_STORE_BYTES = 32 * 1024 * 1024
MAX_SETS = 32

_STORE_LOCKS: dict[str, threading.RLock] = {}
_STORE_LOCKS_GUARD = threading.Lock()

# The last parsed document per project file, keyed by the digest of the bytes it was parsed from: validating a
# large document costs far more than reading it, and every start and wipe resolves it.
_PARSED: dict[str, tuple[bytes, StartupDocument]] = {}
MAX_PARSED = 16


def store_lock(project):
    """Per-project lock for read-check-replace of the store documents.

    Writers run both on the event loop and in worker threads (archive import),
    so the revision check and the file replace must not interleave across
    threads. The lock is re-entrant so callers can group several writes.
    """
    key = str(Path(project.path).absolute())
    with _STORE_LOCKS_GUARD:
        return _STORE_LOCKS.setdefault(key, threading.RLock())


class StartupStore:
    def __init__(self, project):
        self.project = project
        self.root = Path(project.path) / "project-files" / "startup-configs"
        self.path = self.root / "configurations.json"

    def revision(self):
        with store_lock(self.project):
            transaction.recover(self.root)
            return read_revision(self.path, lambda: self._read().revision)

    def read(self):
        # Readers share the writers' lock so they never observe a replace in flight.
        with store_lock(self.project):
            return self._read()

    def _read(self):
        if self.root.is_symlink():
            raise ConfigurationError("unsafe_configuration_path")
        transaction.recover(self.root)
        if not self.path.exists() and not self.path.is_symlink():
            return StartupDocument()
        data = stable_read(str(self.root), self.path, MAX_STORE_BYTES)
        digest = hashlib.blake2b(data).digest()
        key = str(self.path)
        cached = _PARSED.get(key)
        if cached is not None and cached[0] == digest:
            # Callers get their own copy: the models are frozen, but their member dictionaries are not.
            return cached[1].model_copy(deep=True)
        try:
            raw = json.loads(data)
            document = StartupDocument.model_validate(raw)
        except (ValueError, TypeError, AttributeError):
            raise ConfigurationError("invalid_startup_configurations") from None
        with _STORE_LOCKS_GUARD:
            if key not in _PARSED and len(_PARSED) >= MAX_PARSED:
                _PARSED.pop(next(iter(_PARSED)))
            _PARSED[key] = (digest, document.model_copy(deep=True))
        return document

    def write(self, document: StartupDocument, *, revision: int, assignments=None):
        with store_lock(self.project):
            return self._write(document, revision=revision, assignments=assignments)

    def _write(self, document: StartupDocument, *, revision: int, assignments=None):
        # The store lock serializes this optimistic revision check and commit
        # against writers in other threads (archive import) and on the loop.
        current = self.read()
        if current.revision != revision:
            raise ConfigurationError("startup_configurations_changed")
        document = StartupDocument.model_validate(document.model_dump())
        default = next((s for s in current.sets if s.id == DEFAULT_SET), None)
        if default is not None and not any(s.id == DEFAULT_SET and s.name == default.name for s in document.sets):
            raise ConfigurationError("configuration_default_set_protected")
        document = document.model_copy(update={"revision": revision + 1})
        payload = document.model_dump_json().encode("utf-8")
        if len(payload) > MAX_STORE_BYTES:
            raise ConfigurationError("configuration_too_large")
        transaction.commit(self.root, payload, assignments)
        return document

    def set(self, set_id):
        document = self.read()
        selected = next((s for s in document.sets if s.id == UUID(str(set_id))), None)
        if selected is None:
            raise ConfigurationError("configuration_set_not_found")
        return document, selected

    def create_set(self, name, *, revision, select=False):
        """Add an empty set. Names stay unique and the Default set stays intact."""
        document = self.read()
        if len(document.sets) >= MAX_SETS:
            raise ConfigurationError("configuration_set_limit_reached")
        self._unique_set_name(document, name)
        selected = ConfigurationSet(name=name.strip())
        document = self.write(
            document.model_copy(
                update={
                    "sets": (*document.sets, selected),
                    "selected": selected.id if select else document.selected,
                }
            ),
            revision=revision,
        )
        return document, next(item for item in document.sets if item.id == selected.id)

    def _unique_set_name(self, document, name):
        name = (name or "").strip()
        if not name or any(ord(character) < 32 for character in name):
            raise ConfigurationError("invalid_configuration_request")
        if any(selected.name.casefold() == name.casefold() for selected in document.sets):
            raise ConfigurationError("duplicate_configuration_set_names")

    def put_entry(self, set_id, node_id, entry, *, revision):
        document, selected = self.set(set_id)
        nodes = {**selected.nodes, UUID(str(node_id)): entry}
        replacement = selected.model_copy(update={"nodes": nodes})
        return self.write(
            document.model_copy(
                update={"sets": tuple(replacement if s.id == selected.id else s for s in document.sets)}
            ),
            revision=revision,
        )

    @staticmethod
    def remapped(document, mapping):
        """The document with its entries moved to new node ids; entries of unknown nodes are dropped."""
        sets = tuple(
            s.model_copy(
                update={
                    "nodes": {
                        UUID(mapping[str(node_id)]): entry
                        for node_id, entry in s.nodes.items()
                        if str(node_id) in mapping
                    }
                }
            )
            for s in document.sets
        )
        return document.model_copy(update={"sets": sets})
