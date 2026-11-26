"""Portable set archives: export, import, node matching and archive integrity."""

import base64
import io
import json
import zipfile
import zlib
from uuid import UUID, uuid4

import pytest

from gns3server.schemas.configurations import (
    ArchiveImport,
    Selection,
)
from gns3server.services.configurations.sets import archive
from gns3server.services.configurations.sets.selections import SelectionStore
from gns3server.services.configurations.sets.store import StartupStore
from gns3server.services.configurations.shared.errors import ConfigurationError
from tests.support.configurations import configuration_project, run_concurrent_writes, save_startup


def import_set(project, request, manifest, *, authorize=None):
    """Follow the route's prepare, authorize, and commit order."""
    plan = archive.prepare_import(project, request, manifest)
    if authorize is not None:
        authorize(plan)
    return archive.commit_import(project, plan)


def encoded(payload):
    return base64.b64encode(payload).decode("ascii")


def archive_zip(manifest):
    entries = [(archive.MANIFEST_NAME, json.dumps(manifest).encode("utf-8"))]
    entries += [(node["file"], b"hostname R1\n") for node in manifest.get("nodes", ()) if node.get("file")]
    return zip_entries(entries, compression=zipfile.ZIP_DEFLATED)


def zip_entries(entries, *, compression=zipfile.ZIP_STORED):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression) as stream:
        for name, content in entries:
            info = zipfile.ZipInfo(name)
            info.compress_type = compression
            if name == "link":
                info.external_attr = 0o120777 << 16
            stream.writestr(info, content)
    return output.getvalue()


def text_manifest(node_id="00000000-0000-0000-0000-000000000001"):
    return {
        "version": 2,
        "kind": "gns3-startup-configuration-set",
        "created_at": "2026-10-31T20:00:00Z",
        "set_name": "Default",
        "nodes": [
            {
                "node_id": node_id,
                "node_type": "iou",
                "device_type": "cisco_ios_telnet",
                "enabled": True,
                "file": "nodes/r1.cfg",
            }
        ],
    }


def test_archive_round_trip_creates_new_set_and_preserves_assignments(tmp_path):
    node_id, other_id = str(uuid4()), str(uuid4())
    project = configuration_project(tmp_path, [(node_id, "R1", "iou"), (other_id, "R2", "iou")])
    store = StartupStore(project)
    save_startup(store, node_id, "cisco_ios_telnet", "hostname R1\n")
    save_startup(store, other_id, "cisco_ios_telnet", "hostname R2\n", enabled=False)
    filename, payload = archive.build(project, store.read().selected)
    assert filename.endswith(".gns3startup.zip")
    manifest = archive.read(payload)
    assert manifest.set_name == "Default"
    assert {str(node.node_id) for node in manifest.nodes} == {node_id, other_id}
    with zipfile.ZipFile(io.BytesIO(payload)) as stream:
        written = json.loads(stream.read(archive.MANIFEST_NAME))
        files = {name: stream.read(name) for name in stream.namelist() if name != archive.MANIFEST_NAME}
    # One readable file per node; the manifest only points at it.
    assert written["version"] == 2 and all("text" not in node for node in written["nodes"])
    assert files == {node["file"]: f"hostname {node['node_name']}\n".encode() for node in written["nodes"]}
    assert sorted(name.split("-")[0] for name in files) == ["nodes/R1", "nodes/R2"]

    target = configuration_project(tmp_path / "imported", [(node_id, "R1", "iou")])
    request = ArchiveImport(archive=encoded(payload))
    result = import_set(target, request, archive.read(request.payload()))
    # The receiving project keeps its own Default set; the archive is added.
    assert result["set"].name == "Default (2)"
    assert result["mapped"] == {node_id: node_id}
    assert result["skipped"] == [{"node_id": other_id, "node_name": "R2", "reason": "node_not_found"}]
    entry = result["set"].nodes[UUID(node_id)]
    assert entry.content == "hostname R1\n" and entry.enabled is True
    # Archival import never enrolls or assigns the receiving nodes.
    assert SelectionStore(target).selections()["nodes"] == {}


def test_import_counts_duplicate_names_and_can_select_and_assign(tmp_path):
    node_id = str(uuid4())
    project = configuration_project(tmp_path, [(node_id, "R1", "iou")])
    store = StartupStore(project)
    save_startup(store, node_id, "cisco_ios_telnet", "hostname R1\n")
    _, payload = archive.build(project, store.read().selected)
    parsed = archive.read(payload)
    request = ArchiveImport(archive=encoded(payload), select=True, assign_nodes=True)
    first = import_set(project, request, parsed)
    assert first["set"].name == "Default (2)"
    assert StartupStore(project).read().selected == first["set"].id
    assert SelectionStore(project).selections()["nodes"][node_id] == {"kind": "set", "set_id": str(first["set"].id)}
    second = import_set(project, request, parsed)
    assert second["set"].name == "Default (3)"
    assert len(StartupStore(project).read().sets) == 3


def test_import_uses_explicit_mapping_and_rejects_unknown_targets(tmp_path):
    source_id, target_id = str(uuid4()), str(uuid4())
    project = configuration_project(tmp_path, [(source_id, "R1", "iou")])
    store = StartupStore(project)
    save_startup(store, source_id, "cisco_ios_telnet", "hostname R1\n")
    _, payload = archive.build(project, store.read().selected)
    manifest = archive.read(payload)

    empty = configuration_project(tmp_path / "empty", [])
    with pytest.raises(ConfigurationError, match="configuration_node_not_found"):
        import_set(
            empty,
            ArchiveImport(archive=encoded(payload), nodes={manifest.nodes[0].node_id: uuid4()}),
            manifest,
        )

    mapped = configuration_project(tmp_path / "mapped", [(target_id, "R9", "iou")])
    result = import_set(
        mapped, ArchiveImport(archive=encoded(payload), nodes={manifest.nodes[0].node_id: target_id}), manifest
    )
    assert result["mapped"] == {source_id: target_id}
    assert result["skipped"] == []
    assert list(result["set"].nodes) == [UUID(target_id)]

    incompatible = configuration_project(tmp_path / "incompatible", [(target_id, "PC1", "vpcs")])
    result = import_set(
        incompatible,
        ArchiveImport(archive=encoded(payload), nodes={manifest.nodes[0].node_id: target_id}),
        manifest,
    )
    assert result["mapped"] == {}
    assert result["skipped"] == [{"node_id": source_id, "node_name": "R1", "reason": "configuration_apply_unsupported"}]
    assert result["set"].nodes == {}


@pytest.mark.filterwarnings("ignore:Duplicate name:UserWarning")  # The duplicate manifest is the point of the test.
def test_read_rejects_unusable_payloads(monkeypatch):
    manifest = json.dumps(text_manifest())
    for payload in (
        b"not a zip",
        b"",
        zip_entries([(archive.MANIFEST_NAME, manifest), (archive.MANIFEST_NAME, manifest)]),
    ):
        with pytest.raises(ConfigurationError):
            archive.read(payload)
    monkeypatch.setattr(archive, "MAX_ARCHIVE_BYTES", 64)
    with pytest.raises(ConfigurationError, match="configuration_archive_too_large"):
        archive.read(archive_zip(text_manifest()))


def test_archive_round_trips_a_manifest_larger_than_the_old_limit(tmp_path):
    node_ids = [uuid4() for _ in range(3)]
    project = configuration_project(
        tmp_path, [(str(node_id), f"PC{index}", "vpcs") for index, node_id in enumerate(node_ids)]
    )
    store = StartupStore(project)
    document = store.read()
    for node_id in node_ids:
        document = save_startup(store, node_id, "vpcs", "!" * 1500000, enabled=False)
    _, payload = archive.build(project, document.selected)
    assert {item.node_id: item.text for item in archive.read(payload).nodes} == {
        node_id: document.sets[0].nodes[node_id].content for node_id in node_ids
    }


@pytest.mark.parametrize("limit", ["MAX_MANIFEST_BYTES", "MAX_ARCHIVE_BYTES"])
def test_export_rejects_archives_that_exceed_the_import_limit(tmp_path, monkeypatch, limit):
    project = configuration_project(tmp_path)
    monkeypatch.setattr(archive, limit, 64)
    with pytest.raises(ConfigurationError, match="configuration_archive_too_large"):
        archive.build(project, StartupStore(project).read().selected)


def test_read_rejects_traversal_links_and_undeclared_members():
    manifest = json.dumps(text_manifest())
    content = b"hostname R1\n"
    for entries in (
        [(archive.MANIFEST_NAME, manifest), ("../escape", content)],
        [(archive.MANIFEST_NAME, manifest), ("link", content)],
        [(archive.MANIFEST_NAME, manifest), ("objects/" + "0" * 64, content)],
        [(archive.MANIFEST_NAME, "{}")],
        [("objects/" + "0" * 64, content)],
    ):
        with pytest.raises(ConfigurationError):
            archive.read(zip_entries(entries))


def test_import_rejects_two_sources_mapped_to_one_target(tmp_path):
    first, second = str(uuid4()), str(uuid4())
    project = configuration_project(tmp_path, [(first, "R1", "iou"), (second, "R2", "iou")])
    store = StartupStore(project)
    save_startup(store, first, "cisco_ios_telnet", "hostname R1\n")
    save_startup(store, second, "cisco_ios_telnet", "hostname R2\n")
    _, payload = archive.build(project, store.read().selected)
    manifest = archive.read(payload)
    request = ArchiveImport(
        archive=encoded(payload),
        nodes={manifest.nodes[0].node_id: first, manifest.nodes[1].node_id: first},
    )
    with pytest.raises(ConfigurationError, match="configuration_archive_mapping_conflict"):
        import_set(project, request, manifest)
    assert len(StartupStore(project).read().sets) == 1


def exported_archive(tmp_path, nodes):
    """An archive of a source project whose nodes have these (id, name, type) and a saved entry each."""
    source = configuration_project(tmp_path / "source", nodes)
    store = StartupStore(source)
    for index, (node_id, name, _) in enumerate(nodes):
        save_startup(store, node_id, "cisco_ios_telnet", f"hostname {name}\n")
    _, payload = archive.build(source, store.read().selected)
    return payload


def import_into(project, payload, **fields):
    request = ArchiveImport(archive=encoded(payload), **fields)
    return request, archive.read(request.payload())


def test_import_into_another_project_matches_nodes_by_name(tmp_path):
    """The usual case of a set archive: the other project has the same devices under new node ids."""
    payload = exported_archive(tmp_path, [(str(uuid4()), "R1", "iou"), (str(uuid4()), "R2", "iou")])
    r1, r2 = str(uuid4()), str(uuid4())
    target = configuration_project(
        tmp_path / "target", [(r1, "R1", "iou"), (r2, "R2", "iou"), (str(uuid4()), "R3", "iou")]
    )
    request, manifest = import_into(target, payload)
    assert archive.targets(target, request, manifest) == sorted([r1, r2])
    result = import_set(target, request, manifest)
    assert {match["node_name"]: match["target_id"] for match in result["matched_by_name"]} == {"R1": r1, "R2": r2}
    assert [match["node_name"] for match in result["matched_by_name"]] == ["R1", "R2"]
    assert result["skipped"] == []
    assert {entry.content for entry in result["set"].nodes.values()} == {"hostname R1\n", "hostname R2\n"}
    assert set(result["set"].nodes) == {UUID(r1), UUID(r2)}


def test_authorized_import_does_not_remap_to_a_replacement_node(tmp_path):
    payload = exported_archive(tmp_path, [(str(uuid4()), "R1", "iou")])
    node_id, replacement_id = str(uuid4()), str(uuid4())
    project = configuration_project(tmp_path / "target", [(node_id, "R1", "iou")])
    request, manifest = import_into(project, payload)

    def authorize(plan):
        assert set(plan.targets) == {node_id}
        project.nodes[replacement_id] = project.nodes.pop(node_id)

    with pytest.raises(ConfigurationError, match="startup_configurations_changed"):
        import_set(project, request, manifest, authorize=authorize)
    assert StartupStore(project).read().revision == 0


def test_import_prefers_the_same_node_id_over_a_name(tmp_path):
    shared, other = str(uuid4()), str(uuid4())
    payload = exported_archive(tmp_path, [(shared, "R1", "iou")])
    # The receiving project has this id under another name, and another node under the archive's name.
    target = configuration_project(tmp_path / "target", [(shared, "Edge", "iou"), (other, "R1", "iou")])
    request, manifest = import_into(target, payload)
    result = import_set(target, request, manifest)
    assert result["mapped"] == {shared: shared} and result["matched_by_name"] == []


def test_import_does_not_guess_between_nodes_with_the_same_name(tmp_path):
    source_id = str(uuid4())
    payload = exported_archive(tmp_path, [(source_id, "R1", "iou")])
    target = configuration_project(tmp_path / "target", [(str(uuid4()), "R1", "iou"), (str(uuid4()), "R1", "iou")])
    request, manifest = import_into(target, payload)
    result = import_set(target, request, manifest)
    assert result["mapped"] == {} and result["set"].nodes == {}
    assert result["skipped"] == [{"node_id": source_id, "node_name": "R1", "reason": "node_name_ambiguous"}]


def test_an_explicit_mapping_beats_a_name_match(tmp_path):
    source_id, chosen, same_name = str(uuid4()), str(uuid4()), str(uuid4())
    payload = exported_archive(tmp_path, [(source_id, "R1", "iou")])
    target = configuration_project(tmp_path / "target", [(chosen, "Other", "iou"), (same_name, "R1", "iou")])
    request, manifest = import_into(target, payload, nodes={source_id: chosen})
    assert import_set(target, request, manifest)["mapped"] == {source_id: chosen}


def test_importing_a_set_as_the_default_moves_the_choices_like_the_editor_does(tmp_path):
    with_entry, without_entry = str(uuid4()), str(uuid4())
    payload = exported_archive(tmp_path, [(with_entry, "R1", "iou")])
    target = configuration_project(tmp_path / "target", [(with_entry, "R1", "iou"), (without_entry, "R2", "iou")])
    store, selections = StartupStore(target), SelectionStore(target)
    default = store.read().selected
    for node_id in (with_entry, without_entry):
        selections.assign(node_id, Selection(kind="set", set_id=default), selections.selections()["revision"])
    request, manifest = import_into(target, payload, select=True)
    result = import_set(target, request, manifest)
    nodes = selections.selections()["nodes"]
    # The node the archive covers follows the new default; a node it does not cover is switched off.
    assert nodes[with_entry] == {"kind": "set", "set_id": str(result["set"].id)}
    assert nodes[without_entry]["kind"] == "none"


def test_importing_a_set_without_selecting_it_leaves_the_choices_alone(tmp_path):
    node_id = str(uuid4())
    payload = exported_archive(tmp_path, [(node_id, "R1", "iou")])
    target = configuration_project(tmp_path / "target", [(node_id, "R1", "iou")])
    selections = SelectionStore(target)
    default = StartupStore(target).read().selected
    selections.assign(node_id, Selection(kind="set", set_id=default), 0)
    request, manifest = import_into(target, payload)
    import_set(target, request, manifest)
    assert selections.selections()["nodes"][node_id] == {"kind": "set", "set_id": str(default)}


def test_a_save_between_preparation_and_commit_is_not_overwritten(tmp_path):
    project = configuration_project(tmp_path)
    store = StartupStore(project)
    _, payload = archive.build(project, store.read().selected)
    request, manifest = import_into(project, payload, name="Imported")

    def authorize(_plan):
        store.create_set("saved meanwhile", revision=store.read().revision)

    with pytest.raises(ConfigurationError, match="startup_configurations_changed"):
        import_set(project, request, manifest, authorize=authorize)
    assert [item.name for item in store.read().sets] == ["Default", "saved meanwhile"]


def test_archive_import_does_not_lose_a_concurrent_save(tmp_path):
    project = configuration_project(tmp_path)
    store = StartupStore(project)
    _, payload = archive.build(project, store.read().selected)
    request, manifest = import_into(project, payload, name="Imported")
    saves = [f"saved-{index}" for index in range(12)]
    import_count = 6

    def import_archive():
        import_set(project, request, manifest)

    writers = [lambda name=name: store.create_set(name, revision=store.read().revision) for name in saves]
    run_concurrent_writes(writers + [import_archive] * import_count)

    document = store.read()
    names = {item.name for item in document.sets}
    assert names >= set(saves)
    assert sum(name.startswith("Imported") for name in names) == import_count
    assert document.revision == len(saves) + import_count


def test_assigning_an_empty_archive_leaves_the_assignments_alone(tmp_path):
    project = configuration_project(tmp_path, [(str(uuid4()), "PC1", "vpcs")])
    store = StartupStore(project)
    _, payload = archive.build(project, store.read().selected)
    request, manifest = import_into(project, payload, assign_nodes=True)

    assert import_set(project, request, manifest)["mapped"] == {}
    assert SelectionStore(project).selections()["revision"] == 0


def exported(tmp_path, entries):
    """A project with one set holding ``entries`` ([(name, device_type, content)]) and its exported archive."""
    node_ids = [str(uuid4()) for _ in entries]
    project = configuration_project(
        tmp_path, [(node_id, name, "qemu") for node_id, (name, _, _) in zip(node_ids, entries, strict=True)]
    )
    store = StartupStore(project)
    document = store.read()
    for node_id, (_, device_type, content) in zip(node_ids, entries, strict=True):
        document = save_startup(store, node_id, device_type, content, enabled=bool(content))
    return node_ids, archive.build(project, document.selected)[1]


def unpacked(payload):
    with zipfile.ZipFile(io.BytesIO(payload)) as stream:
        return {name: stream.read(name) for name in stream.namelist()}


def test_node_files_have_safe_unique_names_and_the_extension_of_their_device(tmp_path):
    node_ids, payload = exported(
        tmp_path,
        [
            ("R1", "cisco_ios_telnet", "a\n"),
            ("R1", "cisco_ios_telnet", "b\n"),  # The same node name twice.
            ("../../etc/passwd rout\u00e9r", "cisco_nxos", "c\n"),
            ("fw", "paloalto_panos", "<config/>\n"),
            ("tik", "mikrotik_routeros", "d\n"),
            ("pc", "vpcs", "e\n"),
            ("empty", "cisco_ios_telnet", ""),
        ],
    )
    manifest = archive.read(payload)
    files = [node.file for node in manifest.nodes]
    assert files[-1] is None and manifest.nodes[-1].text == ""  # An empty entry has no file.
    assert len(set(files[:-1])) == 6 and all(archive.NODE_FILE.fullmatch(name) for name in files[:-1])
    assert [name.rsplit(".", 1)[1] for name in files[:-1]] == ["cfg", "cfg", "cfg", "xml", "rsc", "vpc"]
    assert [node.text for node in manifest.nodes[:3]] == ["a\n", "b\n", "c\n"]


def test_a_pack_edited_offline_and_zipped_again_imports_the_edited_text(tmp_path):
    node_ids, payload = exported(tmp_path, [("R1", "cisco_ios_telnet", "hostname R1\n")])
    members = unpacked(payload)
    node_file = next(name for name in members if name != archive.MANIFEST_NAME)
    # A Windows editor (byte order mark, CRLF), a "compress folder" tool (folder entries) and macOS leftovers.
    members[node_file] = "\ufeffhostname EDITED\r\n".encode()
    entries = [("pack/", b""), ("pack/nodes/", b"")]
    entries += [(f"pack/{name}", data) for name, data in members.items()]
    entries += [("__MACOSX/pack/nodes/._x", b"junk"), ("pack/.DS_Store", b"junk"), ("pack/nodes/Thumbs.db", b"junk")]
    manifest = archive.read(zip_entries(entries))
    assert manifest.nodes[0].text == "hostname EDITED\r\n"


def test_a_set_with_more_nodes_than_the_old_member_limit_round_trips(tmp_path):
    node_ids, payload = exported(tmp_path, [(f"PC{index}", "vpcs", "ip dhcp\n") for index in range(300)])
    assert len(archive.read(payload).nodes) == 300


def test_an_explicit_mapping_never_shares_its_target_with_an_automatic_match(tmp_path):
    kept, moved = str(uuid4()), str(uuid4())
    payload = exported_archive(tmp_path, [(kept, "R1", "iou"), (moved, "R2", "iou")])
    target = configuration_project(tmp_path / "target", [(kept, "R1", "iou")])
    request, manifest = import_into(target, payload, nodes={moved: kept})
    result = import_set(target, request, manifest)
    assert result["mapped"] == {moved: kept} and len(result["set"].nodes) == 1
    assert result["skipped"] == [{"node_id": kept, "node_name": "R1", "reason": "node_mapped_elsewhere"}]


@pytest.mark.parametrize("change", [{"version": 1}, {"nodes": None}])
def test_an_old_version_or_a_manifest_without_nodes_is_refused(change):
    value = text_manifest()
    value.update(change)
    if value["nodes"] is None:
        del value["nodes"]
    payload = zip_entries([(archive.MANIFEST_NAME, json.dumps(value).encode())])
    with pytest.raises(ConfigurationError, match="invalid_configuration_archive"):
        archive.read(payload)


def manifest_for(*nodes, version=2):
    value = text_manifest()
    value["version"] = version
    value["nodes"] = [
        {"node_id": str(uuid4()), "node_type": "iou", "device_type": "cisco_ios_telnet", "enabled": True, **node}
        for node in nodes
    ]
    return json.dumps(value).encode()


@pytest.mark.parametrize(
    ("nodes", "members"),
    [
        ([{"file": "nodes/a.cfg"}], []),  # A named file is missing.
        ([{"file": "nodes/a.cfg"}], [("nodes/a.cfg", b"x"), ("nodes/b.cfg", b"y")]),  # A file nobody names.
        ([{"file": "nodes/a.cfg"}, {"file": "nodes/a.cfg"}], [("nodes/a.cfg", b"x")]),  # Named twice.
        ([{"text": "inline"}], []),  # Version 2 keeps texts in files.
        ([{"file": "nodes/a.cfg"}], [("nodes/a.cfg", b"\xff\xfe\x00")]),  # Not UTF-8 text.
        ([{"file": "nodes/a.cfg"}], [("nodes/a.cfg", b"bad\x00byte")]),  # Control characters.
        ([{"file": "nodes/deep/a.cfg"}], [("nodes/deep/a.cfg", b"x")]),
        ([{"file": "other.cfg"}], [("other.cfg", b"x")]),
        ([], [("readme.txt", b"x")]),
    ],
)
def test_a_pack_that_does_not_add_up_is_refused(nodes, members):
    payload = zip_entries([(archive.MANIFEST_NAME, manifest_for(*nodes)), *members])
    with pytest.raises(ConfigurationError, match="invalid_configuration_archive"):
        archive.read(payload)


def test_a_node_file_over_the_entry_limit_is_refused():
    payload = zip_entries(
        [(archive.MANIFEST_NAME, manifest_for({"file": "nodes/a.cfg"})), ("nodes/a.cfg", b"x" * (2 * 1024 * 1024 + 1))]
    )
    with pytest.raises(ConfigurationError, match="configuration_archive_too_large"):
        archive.read(payload)


@pytest.mark.parametrize("error", [RecursionError(), zlib.error("bad stream"), NotImplementedError("method 99")])
def test_a_damaged_archive_is_an_invalid_archive(monkeypatch, error):
    payload = zip_entries([(archive.MANIFEST_NAME, b"{}")])

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(
        archive.json if isinstance(error, RecursionError) else archive,
        "loads" if isinstance(error, RecursionError) else "_member",
        fail,
    )
    with pytest.raises(ConfigurationError, match="invalid_configuration_archive"):
        archive.read(payload)
