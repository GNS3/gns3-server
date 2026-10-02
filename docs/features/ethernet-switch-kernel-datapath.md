<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# Ethernet switch kernel datapath

The builtin Ethernet switch has been a real Linux kernel bridge since its
brctl migration: one bridge per switch node, every port a persistent TAP
enslaved to it (see `ethernet-switch-ubridge-brctl-migration` design notes
in `gns3server/compute/builtin/nodes/ethernet_switch.py`). What remained on
the userspace path was the *cable*: each port's TAP doubled as a uBridge
relay endpoint, and a link to another node crossed
`peer anchor/UDP tunnel → uBridge relay ↔ port TAP → bridge` — two extra
copies of every frame.

The kernel datapath removes the cable's userspace leg: the switch absorbs
the **peer's anchor directly into its own bridge**. The peer's veth host
end / TAP becomes the switch port; frames cross
`peer anchor → switch bridge → other switch ports` entirely in the kernel.

```
 relay (before):  peer ──UDP── ubridge[nio_udp↔nio_tap] ──tap── kernel bridge
 kernel (now):    peer anchor ──────────────────────────► kernel bridge
                  (the peer's own interface IS the switch port)
```

## Datapath selection

A link with an `ethernet_switch` endpoint rides the fast path when the
**peer** can anchor (same compute; Docker always — including IOL runner
containers, per their own capability gate — QEMU/IOU/Dynamips per
their capabilities) — the switch side needs no anchoring capability of its
own, its bridge and brctl exist by construction. Exclusions, all staying
on the relay:

* **switch ↔ switch** cascades ride the kernel too — through a veth pair
  joining the two bridges (one end per switch, each side applying its own
  port mode to its own end); see the wire format below;
* anchor-less peers (VPCS, cloud, the Dynamips-hosted hub, generic
  `GNS3_UNIX_SOCKET_NIO` containers);
* cross-compute links, non-Ethernet ports: the common rules.

**Relay port TAPs.** The switch's own relay-path port TAPs (the
`gns3{id}-N` devices) are created *implicitly* by uBridge's
`bridge add_nio_tap` — a name that is free is minted as a transient TAP,
and uBridge hardens it L2-only at creation (the fifth creator of
`docs/design/ubridge-l2-anchor-spec.md` §B, uBridge `fb72758`). The server
issues nothing extra: without that hardening the device would take a
kernel-default IPv6 identity whose DAD/MLD noise floods the segment, which
is exactly what the e2e's relay-control §E.1 assertion guards against.

## The wire format: one NIO names the other end's interface

```
 controller ──► switch compute:  nio_anchor   { anchor: "gv00010203e0p0", filters, markers }
 controller ──► peer compute:    nio_bridge   { bridge: null,             filters: {}, markers }
```

* `nio_anchor` (new, `NIOAnchor`) is the mirror of `nio_bridge`: "enslave
  *this* interface into *my own* bridge". The switch joins the anchor and
  applies the port's VLAN mode to it (`brctl addif` + the access/dot1q/
  qinq composition), exactly as it programs its own port TAPs.
* `nio_bridge` with `bridge: null` on the peer end means "externally
  bridged": the peer keeps everything its node type does around the anchor
  (Dynamips opens the TAP in the hypervisor, IOU binds the fabric to it,
  QEMU's netdev, Docker's carrier) and applies markers/impairments, but
  never touches bridge membership — including on detach, where deleting a
  bridge it does not own would take the switch down.

The anchor's **name** is the shared naming contract
(`gns3server/utils/kernel_anchor.py`): `g<type>{node_id[:8]}e{adapter}p{port}`,
the same function the four node types create their anchors with. It is a
pure function of (node type, node id, adapter, port) — valid whether or
not the peer is running, which is what makes links to stopped nodes
wireable at all.

**Ownership.** The switch owns everything about the anchor's bridge state
(membership, VLANs). The link's *link state* — capture, markers, tc
impairments, suspend — is attached to the same interface by exactly one
end: filters and capture go to the switch (the controller assigns them
single-sided; both ends would hit one interface twice), suspend rides both
(same admin state either way), markers follow the usual capture-node
routing and work from either end.

## Stopped peers: deferred join and the re-push

The peer's anchor exists only while the peer runs. A link created against
a stopped peer cannot be joined immediately, so the switch **defers**: it
remembers the anchor and touches nothing (the link must not fail — this is
the normal case when a project reopens while nodes are still starting).

The controller completes the wiring: after any node of a link reaches the
started state (`Node.start` → `UDPLink.node_started`), a switch link's NIO
is re-pushed to the switch, which joins the anchor now. The same re-join
runs when a peer restart *replaced* its interface under the same name
(QEMU recreates its TAPs at every start): the membership is checked against
the kernel (`/sys/class/net/<bridge>/brif/<anchor>`), not assumed.

Port setting changes (`ports_mapping` update) edit VLAN membership **in
place**: only the ports whose mode/VLAN actually changed are touched, and
each change deletes the previous mode's entries the new mode does not want
and adds the new mode's (the dot1q admits-all entry is one range operation
in both directions). A port never leaves the bridge to change its VLANs —
no traffic gap, no FDB flush, and nothing that detaches an interface this
switch does not own.

This replaced an earlier "reset by re-enslaving" shortcut (`delif` +
`addif`, so the kernel would hand the port a fresh default membership —
used because a mode change must drop stale entries, e.g. dot1q's all-VIDs
range). On the switch's own relay TAPs it merely cost a brief traffic gap;
on **absorbed anchors** re-enslaving an interface owned by another node
proved to be where links died: live testing showed an anchor occasionally
losing its bridge membership right after a `ports_mapping` update (later
updates then failed `delif` with EINVAL), reproducibly with qemu, IOU and
Dynamips peers, never with Docker's veths. Replaying the exact command
sequence by hand against uBridge (held TAPs, no server involved) did not
reproduce it, and the in-place reconcile removes the operation entirely —
the failure mode no longer exists by construction.

## Link-local frames (LACP, LLDP, 802.1X, STP)

The bridge stands in for a cable, but the kernel's `br_handle_frame()` does
not forward the IEEE 802.1D reserved range (`01:80:c2:00:00:00`-`0f`) by
default — LACP, LLDP/DCBX and 802.1X would never cross a kernel link while
the UDP relay carries them fine. uBridge therefore opens every port's
per-port `group_fwd_mask` (`IFLA_BRPORT_GROUP_FWD_MASK`) to `0xfffd` at
`brctl addif` time (Linux 4.15+, best-effort on older kernels). The
bridge-level knob cannot do this: `BR_GROUPFWD_RESTRICTED` rejects bits 0-2,
so LACP is reachable per port only.

Result on kernel links: ordinary multicast, STP/RSTP, LACP, 802.1X and
LLDP/DCBX all cross; **802.3x PAUSE / PFC does not** — `case 0x01` in
`br_handle_frame()` drops it unconditionally and no mask can enable it.
That is a documented limit, not a regression (PFC's hardware semantics are
out of emulation's reach anyway); a lab that needs PAUSE frames on the wire
must use a relay link. Verified live by
`tests/e2e/test_docker_link_local_frames.py` (per-MAC guest-to-guest
matrix); the contract and kernel references live in
`docs/design/ubridge-link-local-frame-forwarding-spec.md`.

The switch node's own bridge ports carry the same mask: the builtin
Ethernet switch is a transparent L2 segment in GNS3, not a protocol
endpoint, so LACP/LLDP between two peers crosses it (a physical switch
would terminate them itself).

## Verified

Unit level (all under `tests/`): the switch's kernel-port lifecycle (join
with VLAN composition, deferred join, re-join, detach with marker/tc/
carrier teardown, capture on the anchor, batch acceptance for project
open); the in-place VLAN reconcile (every mode transition, untouched ports
emit nothing, relay TAPs and absorbed anchors alike); the shared naming
contract; the mixin's externally-bridged branch (no bridge membership work
in attach/remove, the bridge sweep never deletes a bridge the node does not
own); the controller's eligibility table, wire format (anchor name,
single-sided filters, endpoint-order alignment), `kernel_datapath`
reporting and the node-start re-push.

Live end-to-end on a real server (`tests/e2e/test_ethernet_switch_kernel_datapath.py`
plus scripted reproduction rounds over the REST API):

* two qemu peers (the previously 2-out-of-2 failing scenario): deferred
  links → start → both anchors joined; four `ports_mapping` cycles
  (10/20 ↔ 10/10) with both anchors in the bridge throughout, no failed
  update, kernel VLAN state correct at every step;
* a mixed switch (2 × IOU + 2 × Dynamips on one bridge, four kernel
  ports): four anchors stable across updates that changed all ports and
  across updates that changed only two;
* Docker peers with real ICMP: isolating VLANs cuts the ping with **both
  anchors still enslaved** (the filter does the cutting, not a broken
  link); restoring the VLAN restores the ping;
* VPCS peers (the relay path, same switch-side mechanics as cloud): the
  relay TAPs likewise stay enslaved across VLAN changes, with a real ping
  proving isolation and recovery.

The cascade has its own in-repo e2e
(`tests/e2e/test_ethernet_switch_cascade.py`): two switches joined by the
link-owned veth pair, two c7200 routers per switch, real ICMP crossing both
bridges — the pair is born UP with exactly one end per bridge, a dot1q
trunk cascade carries two VLANs at once, the §E.2 idle-silence window with
all four router interfaces shut (the absorbed anchors, both cascade ends
and both switch bridges), the symmetric access/trunk mode flip on the
cascade ends isolates and revives a VLAN in place, a `delay` filter lands
as netem on both ends (one per direction, RTT ≈ 2×delay), suspend
admin-downs both ends, and a link delete/re-create retires the whole pair
and mints a new one under the new link id — with zero host residue after
the project goes.

The host-side checks throughout are the kernel's own view: bridge
membership under `/sys/class/net/<bridge>/brif/`, the `master` link
attribute, `bridge vlan show`, and live pings where the peer allows it.

## Configuration

Same switch as every node type:

```ini
[Server]
enable_kernel_datapath = True
```

## Roadmap

Switch-to-switch links (a veth pair joining the two kernel bridges, with
each side's port mode applied at its own end) have landed (see above), and
so has the IOL runner container (`iol-docker-kernel-datapath.md` — its
`iol_docker` anchors absorb like any peer's). Cross-compute kernel links
need VXLAN/GENEVE encapsulation, deferred until every node type is
kernelized.
