<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.

# Marker (Traffic Insight)

## Overview

A **marker** is a passive traffic-insight tap attached to a link. It runs a libpcap BPF
expression inside uBridge; on every match uBridge emits a real-time `MARK` signal and
appends the matching packet to a per-marker pcap file. Markers exist at two layers that
coexist on the same link: **per-link private markers** and **project-level definitions**
that are inherited by every capable link.

## Architecture

```mermaid
graph TB
    UI["Web UI"]

    subgraph Controller["Controller"]
        DEF["Project definitions<br/>(inheritance templates)"]
        LNK["Per-link markers"]
    end

    Compute["Compute Node"]
    UB["uBridge<br/>mark filter"]
    PCAP[("pcap file")]
    LSTN["Marker listener<br/>(UDP, per compute)"]

    UI -->|"REST + notifications ws"| Controller
    DEF -.->|"fan-out: global-{name}"| LNK
    LNK -->|"node.post /markers"| Compute
    Compute --> UB
    UB -->|"BPF match"| PCAP
    UB -->|"UDP MARK signal"| LSTN
    LSTN -->|"marker.match"| UI
```

Inheritance is a controller-only fan-out: a definition CRUD loops over links and reuses the
existing per-link marker operations, so the compute side sees an ordinary marker and is
unchanged. Each compute process runs one UDP listener serving every uBridge on that host; the
`node` and `link` fields in each signal together identify the source link (see
[Per-link attribution](#per-link-attribution)).

## Business Process

```mermaid
sequenceDiagram
    participant UI as Web UI
    participant C as Controller
    participant L as Capable Link
    participant N as Compute / uBridge

    UI->>C: POST /marker-definitions {name, bpf, ...}
    C->>C: store definition
    loop every capable link
        C->>L: start_marker("global-{name}")
        L->>N: install mark filter (BPF + pcap)
    end
    C-->>UI: 201 + link_ids

    Note over N: later: a packet matches the BPF
    N->>N: emit MARK signal + append pcap
    N-->>UI: marker.match notification (per-project ws)
```

Updating a definition syncs `bpf / tag / color / highlight_duration` to every inherited
copy; deleting a definition removes every inherited copy. A newly created link inherits all
existing definitions automatically.

## Per-link attribution

A uBridge `MARK` signal carries `node`, `filter`, `link`, `tag`, and `len` — but no bridge
name. When one node is the capture side for several links — the common case for a project-level
`global-{name}` marker on a multi-interface router — `node` + `filter` alone are identical
across those links, so they cannot tell the signals (or pcap files) apart. The `link` field
resolves this:

1. At install time the controller stamps each filter with its link id
   (`mark <bpf> [tag <id>] link <link_id> [pcap <path>]`).
2. uBridge treats `link` as opaque and echoes it verbatim in the signal (`link=<link_id>`).
3. The listener takes the signal's `link=` as the **authoritative** `link_id` of the
   `marker.match` event, falling back to its registry only for legacy signals that carry no
   `link=`.

This is also why the pcap path is keyed on link —
`<project>/markers/<node_id>_<link_id>_<filter>.pcap`, not on `bridge`+`filter`: a single
uBridge bridge can serve several links, and only the link id keeps their captures distinct.

### IOU: one bridge, many interfaces

IOU runs a single `IOL-BRIDGE` per node shared by every interface, so `bridge`+`filter` are
identical across that node's links. uBridge keeps a separate filter list **per port
(bay/unit)** within the bridge, so each interface gets its own `global-{name}` filter, its own
pcap file, and its own `link=`. The shared bridge name is irrelevant to attribution. Other
capable node types (`qemu`, `docker`, `vpcs`, `cloud`, `ethernet_switch`) already use one
bridge per link (the switch's per-port relay); `link` applies uniformly to all of them.

## Direction

A `MARK` signal optionally carries `dir=<tx|rx>` — the matched packet's travel direction
**relative to the capture node** (the `node=<id>` in the same signal, i.e. the node whose
uBridge hosts the marker):

| `dir` | Ingress NIO | Meaning |
|-------|-------------|---------|
| `tx`  | device side (`source_nio` on a generic bridge; the IOL instance on an IOU `IOL-BRIDGE`) | capture node is **sending** |
| `rx`  | link side (`destination_nio` on a generic bridge; the NIO side on an IOU `IOL-BRIDGE`) | capture node is **receiving** |

A marker is single-sided: only the chosen capture node's uBridge installs the `mark` filter,
yet both directions of the link transit that one bridge (it carries exactly two NIOs — the
device side and the link side), so that single uBridge observes and classifies both
directions. The `marker.match` event forwards `dir` through unchanged; the Web UI combines it
with the link's two endpoints and the capture `node_id` to draw an arrow:

- `dir=tx` → `capture_node → far_node`
- `dir=rx` → `far_node → capture_node`
- `dir` absent (older uBridge) → undirected highlight (current behaviour)

Because the listener ignores unknown keys, `dir` is **additive**: an older server silently
drops it and an older uBridge simply omits it — either way the system falls back to
undirected rendering with no error.

### Choosing the capture node

Since `dir` is relative to the capture node, *which* endpoint is the observer decides what
`tx`/`rx` mean. By default the server auto-picks (first started marker-capable endpoint, in
link-endpoint order). To pin it — e.g. so `dir=tx` unambiguously means "vpcs1 is sending" —
pass `capture_node_id` on marker **create**:

```json
{ "bpf": "icmp", "direction": "tx", "capture_node_id": "<vpcs1 node uuid>" }
```

The value must be one of the link's two endpoints and a marker-capable type (`vpcs`, `qemu`,
`docker`, `iou`, `dynamips`, `cloud`, `ethernet_switch`); any other id is rejected with `409`. Omit it to keep
the auto-pick. The chosen id is echoed back as `capture_node_id` in the marker entry and in
each `MARK` signal's `node=<id>`, so the Web UI always knows the observer regardless of who
picked it.

`capture_node_id` is **create-only**: it is fixed once the marker exists (changing the
observer would silently flip the meaning of stored `direction`, so recreate the marker
instead). It is not accepted on project-level definitions — a definition is link-agnostic and
has no endpoints to choose from, so inherited markers always auto-pick per link.

For the same reason, a definition **rejects `direction: tx|rx`** (HTTP 409): each inherited
copy auto-picks its capture node, so a fixed tx/rx would denote different session directions
on different links. A definition is `both` only; encode the direction you want in the BPF
instead — e.g. `icmp and icmp[icmptype]==8` for echo requests, a packet-intrinsic property
that is consistent on every link regardless of capture node. tx/rx remains available on
per-link markers, where the capture node is fixed.

## Pause & resume

Two levels of silencing, both instant (no NIO rebuild, no pcap flush):

- **Per-marker (private)** — `PUT /v3/projects/{pid}/links/{lid}/markers/{name}`
  with `{"enabled": false}` flips that one filter off in place (uBridge
  `enable_packet_filter … off`): no signal, no pcap, but traffic still relays —
  a paused `mark` is a no-op tap, not a drop. `{"enabled": true}` flips it back.
  A change to `enabled` alone is a single command (the pcap identity and emitted
  counter are preserved). Changing `bpf`, `tag`, or `direction` rebuilds just that
  one filter (`delete_packet_filter` + add) — only that marker's own pcap reopens
  (a new capture session for the new BPF); changing `color`/`highlight_duration`
  is UI-only, nothing is pushed to uBridge.
- **Per-definition (inherited)** — `POST /v3/projects/{pid}/marker-definitions/{name}/pause`
  and `/resume` toggle **every** inherited `global-{name}` copy across all links
  at once (same `enable_packet_filter on|off`, fanned out per copy). Use to
  pause or resume a whole rule independently of the others. The definition's
  `paused` flag is persisted to the `.gns3` and echoed on the definition object,
  so links created later inherit it already paused, and the Web UI renders the
  per-rule button from server truth.

| Action | signal | pcap | sink |
|--------|--------|------|------|
| per-marker `enabled: false` | stop | stop | n/a |
| per-def `pause` (all `global-{name}` copies) | stop | stop | n/a |
| per-def `resume` | resume | resume | n/a |

## Capture files

Each marker appends matches to `<project>/project-files/markers/<node_id>_<link_id>_<filter>.pcap`.
Removing a marker — per-link `DELETE .../markers/{name}` or deleting a definition (which
removes every inherited copy) — deletes that marker's pcap too, even with the capture node
stopped (the filter is removed with `delete_packet_filter`, the file is unlinked). uBridge's
`reset_packet_filters` (run on NIO/filter changes) preserves mark filters, so unrelated
changes no longer close/reopen any marker's pcap.

## API Endpoints

All endpoints require a JWT bearer token (`POST /v3/access/users/authenticate`). The
`Auth` column lists the required privilege.

### Per-link markers

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v3/projects/{pid}/links/{lid}/markers` | List markers on a link | Link.Audit |
| POST | `/v3/projects/{pid}/links/{lid}/markers` | Attach a marker | Link.Modify |
| PUT | `/v3/projects/{pid}/links/{lid}/markers/{name}` | Update a marker | Link.Modify |
| DELETE | `/v3/projects/{pid}/links/{lid}/markers/{name}` | Remove a marker | Link.Modify |

### Project-level definitions

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v3/projects/{pid}/marker-definitions` | List definitions + bound `link_ids` | Project.Audit |
| POST | `/v3/projects/{pid}/marker-definitions` | Create definition (fans out to every link) | Project.Modify |
| PUT | `/v3/projects/{pid}/marker-definitions/{name}` | Update definition (syncs all copies) | Project.Modify |
| DELETE | `/v3/projects/{pid}/marker-definitions/{name}` | Delete definition (clears all copies) | Project.Modify |
| POST | `/v3/projects/{pid}/marker-definitions/{name}/pause` | Pause every inherited copy (instant, persisted) | Project.Modify |
| POST | `/v3/projects/{pid}/marker-definitions/{name}/resume` | Resume every inherited copy | Project.Modify |

### Aggregation

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/v3/projects/{pid}/markers` | All markers across links, flat | Project.Audit |

The link object returned by `GET /v3/projects/{pid}/links[/{lid}]` also carries a `markers`
field (including inherited markers), so the Web UI can render a link's markers without an
extra request.

## Request / Response

**Marker create body** (`MarkerCreate`, shared by per-link POST and PUT):

```json
{
  "name": "icmp",
  "bpf": "icmp",
  "tag": 1,
  "direction": "tx",
  "capture_node_id": "a37e2235-e21f-46c9-a2ab-ba0f8c5465e6",
  "color": "#ff5722",
  "highlight_duration": 800,
  "enabled": true
}
```

`direction` and `capture_node_id` are both optional and create-only (see
[Direction](#direction)).

**Definition create body** (`MarkerDefinitionCreate`, shared by POST and PUT):

```json
{
  "name": "arp",
  "bpf": "arp",
  "tag": 5,
  "color": "#ff5722",
  "highlight_duration": 1200
}
```

**Marker entry** (returned by GET/POST/PUT, and the value of each link's `markers[name]`):

```json
{
  "bpf": "icmp",
  "tag": 1,
  "enabled": true,
  "color": "#ff5722",
  "highlight_duration": 800,
  "capture_node_id": "a37e2235-e21f-46c9-a2ab-ba0f8c5465e6",
  "inherited_from": null
}
```

**Definition GET response** (adds `link_ids`):

```json
{
  "arp": {
    "bpf": "arp",
    "tag": 5,
    "color": null,
    "highlight_duration": 1200,
    "direction": null,
    "paused": false,
    "link_ids": ["656ed826-...", "6bd9d156-..."]
  }
}
```

## Field Reference

### Marker entry

| Field | Type | Description |
|-------|------|-------------|
| `bpf` | string | libpcap BPF expression (required) |
| `tag` | int \| null | Correlation id echoed in `MARK` signals |
| `enabled` | bool | Whether the marker is active. Toggle is instant: `false` flips the uBridge filter off in place (no signal/pcap), `true` back on — no NIO rebuild (see [Pause & resume](#pause--resume)) |
| `color` | string \| null | Hex color render hint, e.g. `#ff5722` |
| `highlight_duration` | int \| null | UI highlight duration in ms after a match; `null` = UI default |
| `direction` | string \| null | `tx` / `rx` filter relative to the capture node; `null` = both |
| `capture_node_id` | string | Node whose uBridge hosts the marker — caller-set on create, else auto-picked |
| `inherited_from` | string | Source definition name — present on inherited markers only |

### Definition

| Field | Type | Description |
|-------|------|-------------|
| `bpf` | string | libpcap BPF expression (required) |
| `tag` | int \| null | Correlation id |
| `color` | string \| null | Hex color render hint |
| `highlight_duration` | int \| null | UI highlight duration in ms; `null` = UI default |
| `direction` | string \| null | `tx` / `rx` filter relative to the capture node; `null` = both |
| `paused` | bool | Per-definition mute flag — `true` mutes every inherited copy (persisted) |
| `link_ids` | string[] | Links currently carrying an inherited copy (GET only) |

### Notifications

| Event | Payload | Delivered to |
|-------|---------|--------------|
| `link.updated` | Link object (its `markers` field is the source of truth) | Project notification ws |
| `marker.match` | `project_id`, `node_id`, `link_id`, `filter`, `tag`, `ts`, `len`, `dir` | Project notification ws only |

The `marker.match` `link_id` is taken from the signal's `link=` field (authoritative); see
[Per-link attribution](#per-link-attribution). The `dir` field is the matched packet's travel
direction relative to the capture node; see [Direction](#direction).

## Error Responses

| Status | Description |
|--------|-------------|
| 401 | Not authenticated |
| 404 | Link / marker / definition not found |
| 409 | Per-link edit or delete of an inherited marker; reserved (`global`) name or duplicate name on create |
| 422 | Validation failure (name format, `highlight_duration < 1`, missing `bpf`) |

## Notes

- **Marker name is immutable.** It is the identifier across the controller, the uBridge
  filter, the pcap filename, and `MARK` signal routing — so rename is a delete + recreate,
  not a field update. PUT ignores the body `name`; the `{name}` path parameter identifies
  the target, and only `bpf / tag / color / enabled / highlight_duration` are changeable.
  Names are 1–32 chars (`[A-Za-z0-9][A-Za-z0-9_.-]*`); inherited copies carry a `global-`
  prefix, so their filter names reach ~39.
- **`global` prefix reserved.** User-chosen names may not start with `global`; inherited
  markers are stored as `global-{definition_name}` so the two namespaces cannot collide.
  Omitting `name` on create yields an auto-generated, prefix-free name.
- **Inherited markers are read-only per-link.** PUT/DELETE on an inherited marker returns
  409 — edit them through the definitions API.
- **Render hints are not enforced.** `color` and `highlight_duration` (milliseconds, `>= 1`)
  are stored on the link and never sent to uBridge; `null` lets the UI apply its own
  default. A partial PUT (e.g. changing only `bpf`) leaves them untouched.
- **BPF is validated once per source.** A private per-link marker validates its BPF inline
  on create/update. A definition validates its BPF once at create/update (and once per
  definition on project load, dropping any whose BPF has gone invalid); the inherited
  fan-out to every link then skips re-validation, so creating a definition over *N* links
  runs one `tcpdump -d` rather than *N*. (uBridge still runs `pcap_compile` itself at
  install time, so an invalid expression can never slip through.)
- **Supported node types.** A marker needs a uBridge bridge: `vpcs`, `qemu`, `docker`,
  `iou`, `dynamips`, `cloud`, `ethernet_switch` (one capable endpoint suffices). The
  `ethernet_switch` hosts markers on its per-port uBridge relays (brctl backend); the
  `ethernet_hub` is still Dynamips-hosted and has no uBridge. Types without a uBridge are
  silently skipped by the inheritance fan-out. IOU uses one shared `IOL-BRIDGE` per node but
  keeps filters, pcap files, and `link=` ids per port, so multi-interface nodes are handled
  (see [Per-link attribution](#per-link-attribution)).
- **Shared capture-side node.** When one node hosts markers for several links (typical for
  `global-*` definitions on a router), each filter is stamped with its `link_id` so signals
  and pcap files stay link-distinct; the controller never collapses them to a single link.
- **Persistence.** Definitions and private markers persist in the topology; inherited
  markers are re-created from definitions on project load, so reopening a project restores
  the same configuration and stale inherited copies cannot survive on disk.
- **Log interpretation across node types.** Each node type logs its startup and link
  operations differently — do not mistake sparse logs from one type for inactivity.
  QEMU prints `set_link gns3-<N> on` via its QEMU monitor, which is the most visible
  startup log among all types. VPCS, Docker, IOU, Dynamips, and Cloud each have their own
  startup paths (fork + ubridge, container veth, iouyap, Dynamips hypervisor, and TAP
  device respectively) and none of them emit QEMU-monitor-style logs. To verify marker
  operations (toggle, pause, resume) on non-QEMU types, either inspect uBridge's
  own log for `enable_packet_filter` / `marker pause` / `marker resume` commands, or
  watch the gns3server log for the corresponding compute-route calls at INFO level.
