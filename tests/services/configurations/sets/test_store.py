"""The sets store: revisions, atomic saves, set creation, limits and the parsed-document cache."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from gns3server.schemas.configurations import ConfigurationSet, Selection, StartupDocument, StartupEntry
from gns3server.services.configurations.sets import transaction
from gns3server.services.configurations.sets.selections import SelectionStore
from gns3server.services.configurations.sets.store import StartupStore
from gns3server.services.configurations.shared.errors import ConfigurationError
from tests.support.configurations import configuration_project, run_concurrent_writes


def test_configuration_sets_persist_atomically_and_reject_stale_edits(tmp_path):
    project = configuration_project(tmp_path)
    store = StartupStore(project)
    document = store.read()
    node_id = uuid4()
    entry = StartupEntry(device_type="cisco_ios", content="hostname R1\nend\n", enabled=True)
    result = store.put_entry(document.selected, node_id, entry, revision=0)
    assert result.revision == 1
    assert StartupStore(project).read().sets[0].nodes[node_id] == entry
    assert os.stat(store.path).st_mode & 0o777 == 0o600
    with pytest.raises(ConfigurationError, match="startup_configurations_changed"):
        store.write(document, revision=0)
    assert store.read() == result
    assert not list(store.root.rglob(".startup-*"))


def test_concurrent_writers_never_lose_an_update(tmp_path):
    store = StartupStore(configuration_project(tmp_path))
    names = [f"set-{index}" for index in range(24)]
    run_concurrent_writes([lambda name=name: store.create_set(name, revision=store.read().revision) for name in names])

    document = store.read()
    assert {item.name for item in document.sets} >= set(names)
    assert document.revision == len(names)


def test_revision_poll_skips_unchanged_manifests_and_detects_replacements(tmp_path, monkeypatch):
    project = configuration_project(tmp_path)
    store, selections = StartupStore(project), SelectionStore(project)
    node_id = uuid4()
    store.write(store.read(), revision=0)
    selections.assign(node_id, Selection(), 0)
    assert (store.revision(), selections.revision()) == (1, 1)

    def unexpected_read():
        pytest.fail("the revision poll reopened an unchanged manifest")

    with monkeypatch.context() as patcher:
        patcher.setattr(store, "_read", unexpected_read)
        patcher.setattr(selections, "_selections", unexpected_read)
        assert (store.revision(), selections.revision()) == (1, 1)

    # Replace both manifests through independent store instances.
    StartupStore(project).create_set("Changed", revision=1)
    SelectionStore(project).assign(node_id, Selection(), 1)
    assert (store.revision(), selections.revision()) == (2, 2)


def test_failed_manifest_commit_preserves_saved_revision_and_cleans_temporary_files(tmp_path, monkeypatch):
    store = StartupStore(configuration_project(tmp_path))
    saved = store.write(store.read(), revision=0)
    original = store.path.read_bytes()
    replace = os.replace

    def fail_manifest_commit(source, destination):
        if Path(destination) == store.path:
            raise OSError("simulated interrupted manifest commit")
        return replace(source, destination)

    monkeypatch.setattr("gns3server.services.configurations.shared.safe_io.os.replace", fail_manifest_commit)
    with pytest.raises(OSError, match="interrupted manifest commit"):
        store.create_set("Uncommitted", revision=saved.revision)
    assert store.path.read_bytes() == original
    assert store.read() == saved
    assert not list(store.root.rglob(".startup-*"))


def test_failed_selection_write_rolls_back_set_deletion(tmp_path, monkeypatch):
    project = configuration_project(tmp_path)
    store, selections = StartupStore(project), SelectionStore(project)
    saved, selected = store.create_set("Lab", revision=0)
    node_id = uuid4()
    previous = selections.assign(node_id, Selection(kind="set", set_id=selected.id), 0)
    updated = selections.prepare_updates({node_id: Selection()}, previous["revision"])
    pending = saved.model_copy(update={"sets": (saved.sets[0],)})

    def fail(*_args):
        raise OSError("selection write failed")

    monkeypatch.setattr(transaction, "write_json", fail)
    with pytest.raises(OSError, match="selection write failed"):
        store.write(pending, revision=saved.revision, assignments=updated)
    assert store.set(selected.id)[0] == saved
    assert selections.selections() == previous
    assert not (store.root / transaction.JOURNAL).exists()


@pytest.mark.parametrize("committed", [False, True])
def test_first_read_recovers_an_interrupted_transaction(tmp_path, committed):
    project = configuration_project(tmp_path)
    store, selections = StartupStore(project), SelectionStore(project)
    saved, selected = store.create_set("Lab", revision=0)
    node_id = uuid4()
    previous = selections.assign(node_id, Selection(kind="set", set_id=selected.id), 0)
    (store.root / transaction.JOURNAL).write_bytes(b"1:2\n" + store.path.read_bytes())
    # Simulate the two possible interruption points after writing the journal.
    pending = saved.model_copy(update={"sets": (saved.sets[0],), "revision": 2})
    store.path.write_text(pending.model_dump_json())
    if committed:
        (selections.root / "selections.json").write_text(
            json.dumps({"version": 1, "revision": 2, "nodes": {str(node_id): {"kind": "none", "set_id": None}}})
        )
    assert selections.selections()["revision"] == (2 if committed else previous["revision"])
    assert store.read() == (pending if committed else saved)
    assert not (store.root / transaction.JOURNAL).exists()


def test_a_stored_entry_with_an_unknown_field_is_refused(tmp_path):
    store = StartupStore(configuration_project(tmp_path))
    raw = store.read().model_dump(mode="json")
    entry = {"device_type": "vpcs", "content": "ip 192.0.2.1/24\n", "enabled": True, "unknown_field": True}
    raw["sets"][0]["nodes"][str(uuid4())] = entry
    store.root.mkdir(parents=True)
    store.path.write_text(json.dumps(raw))
    with pytest.raises(ConfigurationError, match="invalid_startup_configurations"):
        store.read()


def test_invalid_configuration_documents_and_links_are_rejected(tmp_path):
    store = StartupStore(configuration_project(tmp_path))
    with pytest.raises(ValidationError):
        StartupDocument(selected=uuid4())
    with pytest.raises(ValidationError):
        StartupDocument(sets=(ConfigurationSet(name="same"), ConfigurationSet(name="SAME")))
    with pytest.raises(ValidationError):
        StartupEntry(device_type="cisco_ios", content="hostname R1\x03")
    store.root.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text(StartupDocument().model_dump_json())
    store.path.symlink_to(outside)
    with pytest.raises(ConfigurationError):
        store.read()


def test_set_creation_is_revisioned_and_never_overwrites(tmp_path):
    project = configuration_project(tmp_path)
    store = StartupStore(project)
    node_id = uuid4()
    entry = StartupEntry(device_type="cisco_ios", content="hostname R1\n", enabled=True)
    store.put_entry(store.read().selected, node_id, entry, revision=0)

    document, created = store.create_set("lab", revision=1)
    assert document.revision == 2 and created.name == "lab" and created.nodes == {}
    assert document.selected == document.sets[0].id

    with pytest.raises(ConfigurationError, match="duplicate_configuration_set_names"):
        store.create_set("Default", revision=2)
    with pytest.raises(ConfigurationError, match="duplicate_configuration_set_names"):
        store.create_set("LAB", revision=2)
    with pytest.raises(ConfigurationError, match="startup_configurations_changed"):
        store.create_set("other", revision=1)

    assert [item.name for item in store.read().sets] == ["Default", "lab"]


def test_set_limit_is_enforced(tmp_path):
    project = configuration_project(tmp_path)
    store = StartupStore(project)
    for index in range(31):
        _, created = store.create_set(f"set-{index}", revision=index)
    assert len(store.read().sets) == 32
    with pytest.raises(ConfigurationError, match="configuration_set_limit_reached"):
        store.create_set("too-many", revision=31)


def test_default_set_cannot_be_deleted_or_renamed(tmp_path):
    store = StartupStore(SimpleNamespace(path=str(tmp_path)))
    original = store.read()
    for replacement in ((ConfigurationSet(name="Other"),), (original.sets[0].model_copy(update={"name": "Renamed"}),)):
        with pytest.raises(ConfigurationError, match="configuration_default_set_protected"):
            store.write(original.model_copy(update={"sets": replacement, "selected": replacement[0].id}), revision=0)
    assert store.read() == original


def test_the_store_refuses_a_symlinked_startup_configurations_directory(tmp_path):
    project = configuration_project(tmp_path)
    (tmp_path / "outside").mkdir()
    (tmp_path / "project-files").mkdir()
    (tmp_path / "project-files" / "startup-configs").symlink_to(tmp_path / "outside")
    with pytest.raises(ConfigurationError, match="unsafe_configuration_path"):
        StartupStore(project).read()
