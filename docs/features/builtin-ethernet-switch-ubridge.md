<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is AI-generated with reference to actual code and verified
> against real-kernel testing (Linux 7.1.2-1-default). AI can make mistakes —
> please verify against the source code when in doubt.

# Builtin Ethernet Switch — uBridge brctl Backend

## Overview

The historical GNS3 Ethernet Switch was an emulated L2 device inside Dynamips
(`ethsw`). This implementation replaces it with a **real Linux kernel bridge**
driven through uBridge's `brctl` module — one bridge per switch node.  The
migration makes the switch a first-class builtin node (no Dynamips dependency)
and enables native-kernel-speed L2 switching with VLAN filtering and QinQ.

| | Old (Dynamips ethsw) | New (uBridge brctl) |
|---|---|---|
| Switching engine | Dynamips user-space emulation | Linux kernel bridge (netlink) |
| VLAN model | ethsw ACL per port | Kernel VLAN filtering + PVID/untagged |
| QinQ | 0x8100/0x88A8/0x9100/0x9200 | 0x8100 (802.1Q) / 0x88A8 (802.1ad) |
| Data path | Node NIO ↔ ethsw NIO (Dynamips) | Node NIO ↔ uBridge relay ↔ TAP ↔ kernel bridge |
| Console | Inactive (reserved TCP port) | None (console_type=none) |
| Node type | `dynamips`-routed | `builtin` (always-on) |

## Architecture

```
  ┌───────────┐     ┌──────────────┐     ┌───────────────┐     ┌───────────┐
  │  Peer A   │     │   uBridge    │     │  Kernel       │     │  Peer B   │
  │ (Dynamips │◄───►│  per-port    │◄───►│  Bridge       │◄───►│ (IOU /    │
  │  / IOU /  │ UDP │  relay       │ TAP │  gns3{id[:6]}│ TAP │ QEMU / …) │
  │  QEMU)   │     │  nio_tap↔udp │     │  vlan_filter  │     │           │
  └───────────┘     └──────────────┘     └──────┬────────┘     └───────────┘
                                                │
                                          ┌─────┴─────┐
                                          │ ... more   │
                                          │ ports      │
                                          └───────────┘
```

Each switch port is a **dual-role TAP** — uBridge holds the file descriptor as a
`nio_tap` relay endpoint, and the same TAP is enslaved to the kernel bridge via
`brctl addif`.  This is the same pattern the Cloud node already uses for host
bridges (`cloud.py:_add_linux_ethernet`).  uBridge is **only** the per-port UDP
transport; the kernel bridge performs the actual MAC learning, forwarding, and
VLAN filtering.

### Component map

| File | Role |
|------|------|
| `compute/builtin/nodes/ethernet_switch.py` | Node implementation |
| `api/routes/compute/ethernet_switch_nodes.py` | REST endpoints (repointed to Builtin) |
| `schemas/compute/ethernet_switch_nodes.py` | Request/response models (unchanged) |
| `controller/udp_link.py` | Link creation — pushes NIO to switch via standard adapter endpoint |

## Lifecycle

### `create()` → `start()`

1. `_start_ubridge(require_privileged_access=True)` — launch uBridge instance
2. `_ensure_bridge()`:
   - Derive deterministic bridge name: `gns3` + first 6 hex chars of `self.id`
   - `brctl delete` (best-effort — crash recovery, cleans stale interfaces)
   - `brctl create`
   - `link set … up` (bridge is DOWN after create)
   - `brctl vlanfiltering … on`

### `add_nio(nio, port_number)`

Per port, one uBridge relay bridge `{node_id}-{port}` is wired:

```
bridge create {node_id}-{port}
bridge add_nio_tap {node_id}-{port} "{tap}"          ← uBridge holds TAP fd
brctl addif "{bridge}" "{tap}"                       ← enslave to kernel bridge
brctl vlan_del/vlan_add …                            ← apply port VLAN mode
bridge add_nio_udp {node_id}-{port} lport rhost rport
bridge reset_packet_filters {node_id}-{port}          ← from _ubridge_apply_filters
bridge start {node_id}-{port}
```

Captures and marker signals are applied via the existing `_ubridge_apply_filters`
and `_ubridge_apply_markers` helpers from `BaseNode`. The controller therefore allows
packet filters and traffic-insight markers on switch links (including switch-to-switch):
`ethernet_switch` is a marker/filter-capable node type, and the compute API exposes the
matching NIO-update and per-marker endpoints. The `ethernet_hub` — still Dynamips-hosted,
no uBridge — remains excluded.

### `remove_nio(port_number)`

```
brctl delif "{bridge}" "{tap}"
bridge delete {node_id}-{port}
release_udp_port(nio.lport)
```

### `close()`

```
for each port: release UDP port
brctl delete "{self._bridge_name}"     ← kernel bridge teardown
_stop_ubridge()                        ← destroys remaining TAPs
```

**Cleanup paths:**

| Scenario | Bridge cleanup | TAP cleanup |
|----------|---------------|-------------|
| Normal project close | `close()` → `brctl delete` | uBridge stops → TAP fd closed → kernel destroys |
| gns3server crash / kill | Next `_ensure_bridge()` → `brctl delete` before `create` | uBridge dies → TAP fd closed by kernel |
| Manual project-file deletion after crash | Leaked (no GNS3 record of `gns3{id[:6]}`) | Leaked (same — but uBridge probably dead, TAPs gone with it) |

## Port mode → VLAN translation

All VLAN operations ride on the `brctl` hypervisor module (`../ubridge/doc/brctl.md`).
The kernel bridge must have `vlan_filtering on` before any `vlan_*` call.

### access VLAN N

```
brctl vlan_del {br} {tap} 1          ← remove default PVID 1
brctl vlan_add {br} {tap} N pvid untagged
```

### dot1q trunk (native VLAN V)

A dot1q trunk in ESW is "admit all VLANs tagged, native VLAN PVID + untagged":
```
brctl vlan_del {br} {tap} 1
brctl vlan_add {br} {tap} 1 vid 4094     ← admit all VIDs tagged
brctl vlan_add {br} {tap} V pvid untagged ← override native
```

### qinq (outer VLAN O, ethertype 0x88A8)

Bridge-level (once):
```
brctl setvlanproto {br} 0x88a8          ← switch to 802.1ad (outer S-tag)
```

Port-level:
```
brctl vlan_del {br} {tap} 1
brctl vlan_add {br} {tap} O pvid untagged  ← S-tag push for untagged ingress
```

Ethertype 0x8100 qinq ports are treated as plain access ports (the bridge
defaults to 0x8100; no `setvlanproto` needed).  Ethertype 0x9100/0x9200 are
not supported by the kernel bridge — see § Limitations.

### Runtime reconfiguration (`update_port_settings`)

On `ports_mapping` update, existing port VLANs are reset before re-apply:
```
brctl delif {br} {tap}                  ← release from bridge (clears VLAN state)
brctl addif {br} {tap}                  ← re-enslave (resets to default PVID 1)
brctl vlan_del/vlan_add …               ← apply new mode
```

This prevents stale VLAN membership from a previous mode leaking into the new
configuration (e.g., access→trunk transition leaving old access VLAN behind).

## Bridge naming

Deterministic from the switch's UUID: `gns3` + first 6 hex chars (no dashes).

```
gns3a1b2c3          ← bridge (10 chars, ≤ 15 IFNAMSIZ limit)
gns3a1b2c3-0        ← tap for port 0 (12 chars)
gns3a1b2c3-1        ← tap for port 1 (12 chars)
```

- 6 hex = 48 bits of entropy — collision risk is astronomically low even with
  thousands of switches on the same host.
- **Crash recovery**: `brctl delete` (best-effort, ignore if not found) then
  `brctl create` — stale interfaces from a previous abnormal shutdown are
  reclaimed automatically when the switch is re-created.

## Controller integration

No controller or API contract changes are required. The migration is entirely
compute-internal:

- `node_types.BUILTIN_NODE_TYPES` already classified `ethernet_switch` as a
  builtin, always-running node.
- `udp_link.create()` pushes the NIO to the switch via the standard
  `POST /adapters/0/ports/{p}/nio` endpoint (same as Dynamips).
- The REST API paths, request/response schemas, and port model
  (`EthernetSwitchPort`: type/vlan/ethertype) are unchanged.
- `/start`, `/stop`, `/suspend`, `/reload` return 405 (switch is always-on).

The sole observable difference: the `console` field in the response is now
`null` (the switch has no console; `console_type="none"` makes `BaseNode`
skip TCP port reservation).  The old Dynamips ethsw returned an unused TCP
port number.  Both are valid under `Optional[int]`.

## Known limitations

### Default PVID 1 must be deleted explicitly

A port freshly enslaved to a `vlan_filtering` bridge inherits default PVID 1
(PVID + Egress Untagged).  Access/trunk mode application must issue
`vlan_del … 1` first — `vlan_add … pvid` moves the PVID but does not remove
the old PVID's membership.  This matches iproute2 semantics and is documented
in `../ubridge/doc/brctl.md#limitations`.

### QinQ is outer-tag (S-VLAN) only

With `setvlanproto 0x88a8` the bridge filters on the outer S-tag; the inner
C-tag passes through transparently.  Selective QinQ (inner-VLAN classification
or remapping) requires `IFLA_BRIDGE_VLAN_TUNNEL_INFO` which is not implemented.
Documented in `../ubridge/doc/brctl.md#limitations`.

### Ethertype 0x9100 / 0x9200

The GNS3 schema allows legacy QinQ ethertypes `0x9100` and `0x9200`, but the
Linux kernel bridge only supports `0x8100` (802.1Q) and `0x88a8` (802.1ad).
Configuring these on a qinq port produces a `NodeError` at creation/update
time.  Handling policy (map to 0x88A8 + warn vs. reject with error) is
pending per design discussion.

### No FDB read/write

The `brctl` module exposes no `fdb_show`/`fdb_flush`.  The kernel bridge
learns and ages MAC entries autonomously; uBridge has never exposed MAC-table
access and gns3-server does not consume it.  Consumers that need the FDB
(e.g., a WebUI switch view) should read `/sys/class/net/<br>/brforward` or
`bridge fdb show dev <br>` directly, without uBridge involvement.

## Troubleshooting

### Docker iptables: FORWARD chain DROP

Docker sets the iptables `FORWARD` chain default policy to `DROP` when the
Docker daemon starts.  This blocks **all** forwarded traffic through kernel
bridges on the host, including `gns3*` bridges.

**Symptoms**: nodes can send frames into the bridge (visible in `tcpdump -i
gns3*`) but never receive unicast replies.  ARP and multicast may work
because they flood, but unicast forwarding silently fails.

**Fix**:
```bash
sudo iptables -P FORWARD ACCEPT
```

### Bridge left DOWN after creation

`brctl create` creates the bridge but leaves it administratively DOWN.
The node now sends `link set … up` after `brctl create`.  If forwarding
is not working, verify:
```bash
ip -d link show gns3* | grep -E "state|vlan_filtering"
```

### Kernel version differences

This implementation has been tested on Linux 7.1.2-1-default (x86_64) with
uBridge installed via `make install` (cap_net_admin,cap_net_raw=ep).  The
ubridge `brctl` module has a 168-test suite covering kernel-side VLAN
behaviour on this kernel.
