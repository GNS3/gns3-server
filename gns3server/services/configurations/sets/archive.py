"""Portable configuration-set archives.

An archive is a ZIP holding one set: ``manifest.json`` (the set name and its node membership) and one readable text
file per node under ``nodes/`` so the configurations can be compared and edited offline (manifest version 2).
Content is text only: archives never describe host paths,
symlinks or executable hooks, and an imported set never changes a runtime or a per-node assignment unless the caller
asks for it explicitly.
"""

import io
import json
import re
import zipfile
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from gns3server.schemas.configurations import (
    MAX_ARCHIVE_BYTES,
    MAX_FILE_BYTES,
    ArchiveImport,
    ArchiveManifest,
    ArchiveNode,
    ConfigurationSet,
    Selection,
    StartupDocument,
    StartupEntry,
    compatible_device_type,
)
from gns3server.services.configurations.sets.selections import SelectionStore, default_selection_changes
from gns3server.services.configurations.sets.store import MAX_SETS, StartupStore, store_lock
from gns3server.services.configurations.shared.errors import ConfigurationError

MANIFEST_NAME = "manifest.json"
MAX_UNCOMPRESSED_BYTES = 2 * MAX_ARCHIVE_BYTES
# A set holds up to 1000 nodes; re-zipping tools add folder entries and macOS adds a shadow copy of every file.
MAX_MEMBERS = 4096
MAX_MANIFEST_BYTES = MAX_UNCOMPRESSED_BYTES
NODE_FILE = re.compile(r"nodes/[^/\\]+")
EXTENSIONS = {"paloalto_panos": "xml", "mikrotik_routeros": "rsc", "vpcs": "vpc", "frr": "conf"}
# Files that archiving tools add on their own; they carry nothing of the set.
TOOL_FILES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


def _filename(set_name):
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", set_name).strip("-.")[:60] or "configuration-set"
    return f"{stem}.gns3startup.zip"


def _node_file(node_name, node_id, device_type, used):
    """``nodes/<node name>-<id>.<extension>``: readable, and unique within the archive."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", node_name).strip("-.")[:60] or "node"
    extension = EXTENSIONS.get(device_type, "cfg")
    name = f"nodes/{stem}-{node_id.hex[:8]}.{extension}"
    return name if name not in used else f"nodes/{stem}-{node_id.hex}.{extension}"


def build(project, set_id, revision=None) -> tuple[str, bytes]:
    """Serialize one saved set without reading or changing runtime state.

    ``revision`` is the document revision the user confirmed; a later edit refuses the export.
    """
    document, selected = StartupStore(project).set(set_id)
    if revision is not None and document.revision != revision:
        raise ConfigurationError("startup_configurations_changed")
    nodes, files = [], {}
    for node_id, entry in selected.nodes.items():
        node = project.nodes.get(str(node_id))
        node_name = getattr(node, "name", "") if node is not None else ""
        member = None
        if entry.content:
            member = _node_file(node_name, node_id, entry.device_type, files)
            files[member] = entry.content.encode("utf-8")
        nodes.append(
            ArchiveNode(
                node_id=node_id,
                node_name=node_name,
                node_type=getattr(node, "node_type", "") if node is not None else "",
                device_type=entry.device_type,
                enabled=entry.enabled,
                file=member,
            )
        )
    manifest = ArchiveManifest(
        created_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        source_project_id=UUID(str(project.id)),
        source_set_id=selected.id,
        set_name=selected.name,
        nodes=tuple(nodes),
    )
    encoded = manifest.model_dump_json(indent=2, exclude={"nodes": {"__all__": {"text"}}}).encode("utf-8")
    if len(encoded) > MAX_MANIFEST_BYTES or len(encoded) + sum(map(len, files.values())) > MAX_UNCOMPRESSED_BYTES:
        raise ConfigurationError("configuration_archive_too_large")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_NAME, encoded)
        for member, data in files.items():
            archive.writestr(member, data)
    if output.tell() > MAX_ARCHIVE_BYTES:
        raise ConfigurationError("configuration_archive_too_large")
    return _filename(selected.name), output.getvalue()


def read(payload: bytes) -> ArchiveManifest:
    """Validate an archive fully before any project state is written; every node comes back with its text."""
    if not 0 < len(payload) <= MAX_ARCHIVE_BYTES:
        raise ConfigurationError("configuration_archive_too_large")
    members = _members(payload)
    try:
        data = json.loads(members.pop(MANIFEST_NAME))
        if not isinstance(data, dict) or data.get("version") != 2:
            raise ValueError("Unsupported archive version")
        _attach_files(data, members)
        manifest = ArchiveManifest.model_validate(data)
        for node in manifest.nodes:
            StartupEntry(device_type="vpcs", content=node.text)  # The text rules of a saved entry (any device).
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise ConfigurationError("invalid_configuration_archive") from None
    return manifest


def _attach_files(data, members):
    """Put the text of each node file into its manifest node; every file has to be named by exactly one node."""
    used = set()
    for node in data["nodes"]:
        if "text" in node:
            raise ValueError("A version 2 archive keeps its texts in files")
        name = node.get("file")
        if name is None:
            continue
        if name in used or name not in members:
            raise ValueError("A node names a missing file, or one that another node names")
        used.add(name)
        node["text"] = members[name].decode("utf-8-sig")  # Windows editors may add a byte order mark.
    if set(members) - used:
        # A file the manifest does not name would be dropped without a word.
        raise ValueError("The archive holds a file that no node names")


def _is_tool_file(member):
    parts = member.filename.split("/")
    return member.is_dir() or parts[0] == "__MACOSX" or parts[-1] in TOOL_FILES


def _members(payload):
    """The manifest and node files of the archive as {name: bytes}; any other content is refused."""
    contents = {}
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_MEMBERS or sum(member.file_size for member in entries) > MAX_UNCOMPRESSED_BYTES:
                raise ConfigurationError("configuration_archive_too_large")
            members = [member for member in entries if not _is_tool_file(member)]
            prefix = _wrapping_folder([member.filename for member in members])
            for member in members:
                name = member.filename.removeprefix(prefix)
                if _unsafe(member) or name in contents or not (name == MANIFEST_NAME or NODE_FILE.fullmatch(name)):
                    raise ConfigurationError("invalid_configuration_archive")
                limit = MAX_MANIFEST_BYTES if name == MANIFEST_NAME else MAX_FILE_BYTES
                contents[name] = _member(archive, member, limit)
    except ConfigurationError:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, zlib.error, NotImplementedError):
        raise ConfigurationError("invalid_configuration_archive") from None
    if MANIFEST_NAME not in contents:
        raise ConfigurationError("invalid_configuration_archive")
    return contents


def _wrapping_folder(names):
    """``folder/`` when the whole archive sits in one folder (a compressed folder), else an empty string."""
    if MANIFEST_NAME in names:
        return ""
    folder = names[0].split("/")[0] + "/" if names else ""
    wrapped = folder + MANIFEST_NAME in names and all(name.startswith(folder) for name in names)
    return folder if wrapped else ""


def _unsafe(member):
    """Reject links and encrypted members."""
    if member.flag_bits & 0x1:
        return True
    return (member.external_attr >> 16) & 0o170000 == 0o120000


def _member(archive, member, limit=MAX_FILE_BYTES):
    if member.file_size > limit:
        raise ConfigurationError("configuration_archive_too_large")
    with archive.open(member) as stream:
        content = stream.read(limit + 1)
    if len(content) != member.file_size:
        raise ConfigurationError("invalid_configuration_archive")
    return content


def _unique_name(document, requested):
    names = {selected.name.casefold() for selected in document.sets}
    base = requested.strip()[:80]
    if base.casefold() not in names:
        return base
    for index in range(2, MAX_SETS + 1):
        suffix = f" ({index})"
        candidate = base[: 80 - len(suffix)] + suffix
        if candidate.casefold() not in names:
            return candidate
    raise ConfigurationError("configuration_set_limit_reached")


def resolve_targets(nodes_backend, request: ArchiveImport, manifest: ArchiveManifest):
    """Decide which node of this project receives each node of the archive.

    An explicit mapping of the request wins, then the same node ID, then the one node of this project that
    has the archive node's name (an archive from another project, or from this one after a copy). A name
    shared by several nodes is not guessed. A node that an explicit mapping gives to another source is not
    matched a second time, so two sources never share a target. Returns ``(targets, by_name, skipped)``: the receiving node id per
    archive node id, the matches that were made by name, and the nodes that stay out.
    """
    claimed = {str(target) for target in request.nodes.values()}
    claimed |= {str(node.node_id) for node in manifest.nodes if str(node.node_id) in nodes_backend}
    names = {}
    for node_id, node in nodes_backend.items():
        names.setdefault(getattr(node, "name", ""), []).append(node_id)
    mapped_away = {str(request.nodes[node.node_id]) for node in manifest.nodes if node.node_id in request.nodes}
    targets, by_name, skipped = {}, [], []
    for node in manifest.nodes:
        source = str(node.node_id)
        if node.node_id in request.nodes:
            target = str(request.nodes[node.node_id])
            if target not in nodes_backend:
                raise ConfigurationError("configuration_node_not_found")
        elif source in nodes_backend:
            if source in mapped_away:
                skipped.append({"node_id": source, "node_name": node.node_name, "reason": "node_mapped_elsewhere"})
                continue
            target = source
        else:
            candidates = [c for c in names.get(node.node_name, []) if c not in claimed] if node.node_name else []
            if len(candidates) != 1:
                reason = "node_name_ambiguous" if candidates else "node_not_found"
                skipped.append({"node_id": source, "node_name": node.node_name, "reason": reason})
                continue
            target = candidates[0]
            claimed.add(target)
            by_name.append({"node_id": source, "node_name": node.node_name, "target_id": target})
        targets[source] = target
    return targets, by_name, skipped


def targets(project, request: ArchiveImport, manifest: ArchiveManifest):
    """The nodes the import writes to, resolved up front so authorization happens before any write."""
    try:
        resolved, _, _ = resolve_targets(project.nodes.copy(), request, manifest)
    except ConfigurationError:
        # An unknown mapping target is reported by the import itself, after authorization: node ids must not
        # be probeable without access.
        resolved = {}
    return sorted({*resolved.values(), *(str(target) for target in request.nodes.values())})


@dataclass(frozen=True)
class ImportPlan:
    document: StartupDocument
    selection_revision: int
    changes: dict[str, Selection]
    affected_nodes: frozenset[str]
    targets: dict
    result: dict


def prepare_import(project, request, manifest):
    with store_lock(project):
        return _prepare_import(project, request, manifest)


def _prepare_import(project, request, manifest):
    document = StartupStore(project).read()
    assignments = SelectionStore(project).selections()
    if len(document.sets) >= MAX_SETS:
        raise ConfigurationError("configuration_set_limit_reached")
    nodes_backend = project.nodes.copy()
    if len({str(target) for target in request.nodes.values()}) != len(request.nodes):
        raise ConfigurationError("configuration_archive_mapping_conflict")
    resolved, by_name, skipped = resolve_targets(nodes_backend, request, manifest)
    entries = {}
    mapped = {}
    for node in manifest.nodes:
        target = resolved.get(str(node.node_id))
        if target is None:
            continue
        if not compatible_device_type(nodes_backend[target].node_type, node.device_type):
            skipped.append(
                {"node_id": str(node.node_id), "node_name": node.node_name, "reason": "configuration_apply_unsupported"}
            )
            continue
        entries[UUID(target)] = StartupEntry(device_type=node.device_type, content=node.text, enabled=node.enabled)
        mapped[str(node.node_id)] = target
    by_name = [match for match in by_name if match["node_id"] in mapped]
    selected = ConfigurationSet(name=_unique_name(document, request.name or manifest.set_name), nodes=entries)
    sets = (*tuple(document.sets), selected)
    pending = document.model_copy(
        update={"sets": sets, "selected": selected.id if request.select else document.selected}
    )
    changes = {}
    affected = set()
    if request.select:
        changes = default_selection_changes(document, pending, assignments)
        old_default = next(item for item in document.sets if item.id == document.selected)
        affected.update(
            str(node_id)
            for set_entries in (old_default.nodes, entries)
            for node_id, entry in set_entries.items()
            if entry.enabled and str(node_id) not in assignments["nodes"]
        )
    if request.assign_nodes:
        changes.update({target: Selection(kind="set", set_id=selected.id) for target in mapped.values()})
    affected.update(
        identifier
        for identifier, choice in changes.items()
        if choice.model_dump(mode="json") != assignments["nodes"].get(identifier)
    )
    result = {
        "set": selected,
        "mapped": mapped,
        "matched_by_name": by_name,
        "skipped": skipped,
    }
    affected.intersection_update(nodes_backend)
    authorized_targets = {*mapped.values(), *affected}
    return ImportPlan(
        pending,
        assignments["revision"],
        changes,
        frozenset(affected),
        {identifier: nodes_backend[identifier] for identifier in authorized_targets},
        result,
    )


def commit_import(project, plan):
    with store_lock(project):
        selections = SelectionStore(project)
        if selections.selections()["revision"] != plan.selection_revision or any(
            project.nodes.get(identifier) is not node for identifier, node in plan.targets.items()
        ):
            raise ConfigurationError("startup_configurations_changed")
        updated = selections.prepare_updates(plan.changes, plan.selection_revision) if plan.changes else None
        StartupStore(project).write(plan.document, revision=plan.document.revision, assignments=updated)
        return plan.result
