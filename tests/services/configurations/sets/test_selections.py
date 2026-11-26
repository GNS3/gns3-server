"""Per-node set assignments: revisions, remapping and unambiguous references."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from gns3server.controller.configurations import selected_entry
from gns3server.schemas.configurations import ConfigurationSet, Selection, StartupEntry
from gns3server.services.configurations.sets import transaction
from gns3server.services.configurations.sets.selections import (
    SelectionStore,
    default_selection_changes,
    remap_nodes,
)
from gns3server.services.configurations.sets.store import StartupStore
from gns3server.services.configurations.shared.errors import ConfigurationError
from tests.support.configurations import save_startup


def test_assignments_are_revisioned_and_remap_with_the_nodes(tmp_path):
    store = SelectionStore(SimpleNamespace(path=str(tmp_path)))
    original, replacement = str(uuid4()), str(uuid4())
    selection = Selection(kind="set", set_id=uuid4())
    store.assign(original, selection, 0)
    with pytest.raises(ConfigurationError, match="startup_configurations_changed"):
        store.assign(original, Selection(), 0)
    remap_nodes(SimpleNamespace(path=str(tmp_path)), {original: replacement})
    assert store.selections()["nodes"] == {replacement: selection.model_dump(mode="json")}


def test_an_interrupted_remap_leaves_sets_and_choices_on_the_same_ids(tmp_path, monkeypatch):
    project = SimpleNamespace(path=str(tmp_path))
    original, replacement = str(uuid4()), str(uuid4())
    sets = StartupStore(project)
    document = save_startup(sets, original, "vpcs", "set pcname A\n", enabled=False)
    choices = SelectionStore(project)
    choices.assign(original, Selection(kind="set", set_id=document.selected), 0)

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(transaction, "write_json", fail)
    with pytest.raises(OSError):
        remap_nodes(project, {original: replacement})
    monkeypatch.undo()
    assert list(sets.read().sets[0].nodes) == [UUID(original)]
    assert list(choices.selections()["nodes"]) == [original]


@pytest.mark.parametrize("kwargs", [dict(kind="set"), dict(kind="none", set_id=uuid4()), dict(kind="other")])
def test_selection_reference_is_unambiguous(kwargs):
    with pytest.raises(ValidationError):
        Selection(**kwargs)


def test_editing_the_default_set_updates_node_choices_but_editing_another_set_does_not(tmp_path):
    project = SimpleNamespace(path=str(tmp_path))
    node = SimpleNamespace(id=str(uuid4()), project=project, node_type="vpcs", properties={})
    store = StartupStore(project)
    before = store.read()
    assignments = SelectionStore(project)
    assignments.assign(node.id, Selection(), 0)
    entry = StartupEntry(device_type="vpcs", content="set pcname Saved\n", enabled=True)

    def follow_default(previous, current):
        value = assignments.selections()
        changes = default_selection_changes(previous, current, value)
        if changes:
            assignments.assign_many(changes, value["revision"])

    after = store.put_entry(before.selected, node.id, entry, revision=before.revision)
    follow_default(before, after)
    assert selected_entry(node) == (after.selected, entry)
    selection = assignments.selections()
    inactive = ConfigurationSet(name="Other", nodes={UUID(node.id): entry})
    edited = after.model_copy(update={"sets": (*after.sets, inactive)})
    follow_default(after, edited)
    assert assignments.selections() == selection
    disabled = store.put_entry(
        after.selected, node.id, entry.model_copy(update={"enabled": False}), revision=after.revision
    )
    follow_default(after, disabled)
    assert selected_entry(node) is None
