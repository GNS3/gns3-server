"""Per-node set assignments: revisions, remapping and unambiguous references."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from gns3server.schemas.configurations import Selection
from gns3server.services.configurations.sets import transaction
from gns3server.services.configurations.sets.selections import SelectionStore, remap_nodes
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
