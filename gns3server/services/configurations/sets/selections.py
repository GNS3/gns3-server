"""Which set each node starts from: the per-node assignments and the markers of the nodes this feature manages.

Stored under ``project-files/startup-configs/nodes``; every write shares the project lock of the sets store and
carries its own optimistic revision.
"""

from pathlib import Path
from uuid import UUID

from gns3server.schemas.configurations import Selection
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.safe_io import read_json, write_json

from . import transaction
from .revisions import read_revision
from .store import StartupStore, store_lock


class SelectionStore:
    """Per-node set assignments (``selections.json``) and the markers of the nodes whose startup this feature manages."""

    def __init__(self, project):
        self.project = project
        self.root = Path(project.path).absolute() / "project-files/startup-configs/nodes"

    def revision(self):
        with store_lock(self.project):
            transaction.recover(self.root.parent)
            return read_revision(self.root / "selections.json", lambda: self._selections()["revision"])

    def selections(self):
        with store_lock(self.project):
            return self._selections()

    def _selections(self):
        transaction.recover(self.root.parent)
        value = read_json(self.root / "selections.json", {"version": 1, "revision": 0, "nodes": {}})
        try:
            if value["version"] != 1 or type(value["revision"]) is not int or value["revision"] < 0:
                raise ValueError("invalid revision")
            for node_id, selection in value["nodes"].items():
                UUID(node_id)
                Selection.model_validate(selection)
            return value
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ConfigurationError("invalid_startup_configurations") from None

    def assign(self, node_id, selection, revision):
        with store_lock(self.project):
            return self._assign(node_id, selection, revision)

    def _assign(self, node_id, selection, revision):
        value = self.selections()
        if revision != value["revision"]:
            raise ConfigurationError("startup_configurations_changed")
        value["nodes"][str(UUID(str(node_id)))] = selection.model_dump(mode="json")
        value["revision"] += 1
        write_json(self.root / "selections.json", value)
        return value

    def assign_many(self, selections, revision):
        """Assign several nodes under one revision guard and one manifest write."""
        with store_lock(self.project):
            return self._assign_many(selections, revision)

    def _assign_many(self, selections, revision):
        value = self.prepare_updates(selections, revision)
        write_json(self.root / "selections.json", value)
        return value

    def prepare_updates(self, selections, revision):
        """Prepare the next selection manifest under the caller's project lock."""
        value = self.selections()
        if revision != value["revision"]:
            raise ConfigurationError("startup_configurations_changed")
        for node_id, selection in selections.items():
            value["nodes"][str(UUID(str(node_id)))] = Selection.model_validate(selection).model_dump(mode="json")
        value["revision"] += 1
        return value

    def remapped(self, mapping):
        """The next selection manifest after the nodes got new ids; None when there is none to move."""
        if not (self.root / "selections.json").exists():
            return None
        value = self.selections()
        value["nodes"] = {mapping[node_id]: source for node_id, source in value["nodes"].items() if node_id in mapping}
        value["revision"] += 1
        return value

    def remap_managed(self, mapping):
        """Move the per-node markers (managed startup, pending preparation) to the new node ids."""
        markers = [*(self.root / "managed").glob("*.json"), *(self.root.parent / "prepared").glob("*.json")]
        for file in markers:
            value = read_json(file)
            if file.stem in mapping:
                replacement = file.parent / f"{UUID(mapping[file.stem])}.json"
                if replacement == file:
                    continue
                write_json(replacement, value)
            file.unlink()


def remap_nodes(project, mapping):
    """Move saved sets and node choices to new node ids; the two manifests change in one transaction."""
    sets, choices = StartupStore(project), SelectionStore(project)
    with store_lock(project):
        document = sets.read()
        value = choices.remapped(mapping)
        if sets.path.exists():
            sets.write(sets.remapped(document, mapping), revision=document.revision, assignments=value)
        elif value is not None:
            write_json(choices.root / "selections.json", value)
        choices.remap_managed(mapping)


def default_selection_changes(previous, current, assignments):
    """The node choices that move when the project default set changes or is edited.

    Used when a document is saved without explicit selections (API clients) and when an imported set becomes
    the default. The web UI sends its own selections instead. Choices that point at another set stay as they are.
    """
    old = next(s for s in previous.sets if s.id == previous.selected)
    active = next(s for s in current.sets if s.id == current.selected)
    changes = {}
    set_ids = {s.id for s in current.sets}
    for identifier in assignments["nodes"]:
        source = Selection.model_validate(assignments["nodes"][identifier])
        if source.kind == "set" and source.set_id not in set_ids:
            changes[identifier] = Selection()
            continue
        if current.selected == previous.selected and source.kind == "set" and source.set_id != current.selected:
            continue
        node_id = UUID(identifier)
        entry = active.nodes.get(node_id)
        before = old.nodes.get(node_id)
        if current.selected == previous.selected and entry == before:
            continue
        if current.selected != previous.selected or entry is not None or before is not None:
            changes[identifier] = (
                Selection(kind="set", set_id=active.id) if entry is not None and entry.enabled else Selection()
            )
    return changes
