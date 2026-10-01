<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# QEMU kernel datapath

QEMU adapters anchor on a **persistent TAP**, and links between two QEMU
nodes — or a QEMU node and a Docker container — on the same compute are wired
in the kernel (per-link Linux bridge) instead of the uBridge UDP relay. The
compute side is the same machinery Docker already uses: `KernelDatapathMixin`
(`gns3server/compute/kernel_datapath.py`) takes an *anchor interface* and does
not care whether it is a veth host end or a TAP.

## Architecture

Kernel link between two QEMU nodes on one compute:

```
 QEMU A (fd)                root namespace                 QEMU B (fd)
 ┌──────────┐   -netdev   ┌──────────────────┐  -netdev   ┌──────────┐
 │ e1000    │◄───tap──────┤  gq{idA}e0p0 ────┼──► gns3{link_id_prefix}
 └──────────┘             │  (bridge port)   │    (bridge port)  │
                          │  per-link kernel │   gq{idB}e0p0     │
                          │  bridge = "cable"│                   │
                          └──────────────────┘
```

Relay link on the same anchor (cross-compute, mixed node types, or
`enable_kernel_datapath` off):

```
 ┌──────────┐   tap    ┌────────────────────────────┐   UDP   ┌──────────┐
 │ QEMU A   │◄────────►│ uBridge relay bridge       │◄───────►│ peer     │
 │ (fd)     │ gq…e0p0  │ add_nio_ethernet ↔ add_    │ tunnel  │ (any)    │
 └──────────┘          │ nio_udp                    │         └──────────┘
                       └────────────────────────────┘
```

The relay attaches the TAP with `bridge add_nio_ethernet` (AF_PACKET, which
does not take the device over) — **never** `bridge add_nio_tap`, which would
claim the fd QEMU itself holds.

## Why a TAP works like a veth host end

| Event | Docker anchor (veth host end) | QEMU anchor (TAP) |
|---|---|---|
| Frames the node sends | arrive on the veth as `PACKET_HOST` | written to the tap fd, arrive as RX (`PACKET_HOST`) |
| Frames the peer sends | injected by uBridge, seen as `PACKET_OUTGOING` | injected by uBridge, seen as `PACKET_OUTGOING` |
| `tc` egress qdisc impairs | traffic entering the container | traffic entering the VM |
| Capture/marker anchor | the interface | the same interface |

So every filter, capture and marker primitive carries over verbatim, and
`delay 100` on both anchors still measures ≈200 ms round trip while each
direction is impaired exactly once.

## Datapath selection

`UDPLink._kernel_datapath_eligible` needs both endpoints on one compute and
both able to anchor:

* Docker always can (adapters are born as veth pairs);
* QEMU can when that compute's uBridge reports the `tap` module — asked per
  compute through `/capabilities` (`ubridge_tap`, probed by creating and
  deleting one throwaway TAP, cached by binary identity), because an old
  uBridge leaves QEMU on the legacy socket-netdev datapath and cannot anchor
  a kernel link. An unknown/failed probe keeps the link on the relay.

Because the `-netdev` type is fixed when QEMU is launched, this is
all-or-nothing per VM: on the TAP datapath *every* link can attach to (or
detach from) a running VM, including switching a link between the two
datapaths (delete + re-create, or a project reopen).

## Adapter lifecycle

* **Birth (node start, before QEMU is launched)** — `_prepare_tap_datapath`
  probes the tap module, then `_create_taps` sweeps any leftover (a persistent
  TAP outlives a crash) and creates one TAP per adapter:
  `tap create gq{node_id[:8]}e{adapter}p{port}` → `tap set_owner <uid>`
  (so the unprivileged QEMU process can open it) → `link set <tap> down`
  (carrier off until a link attaches). QEMU then opens it as
  `-netdev tap,id=gns3-{adapter},ifname=<tap>,script=no,downscript=no`.
* **Life (running)** — the TAP is never created or destroyed again. Link
  create/delete/switch, suspend, capture and markers only change *what is
  attached to it*.
* **Death (node stop)** — the QEMU process is stopped **first**, then
  `_remove_taps` un-persists the TAPs (`tap delete`) and deletes the
  per-link kernel bridges the node still holds. The order matters: uBridge's
  `tap delete` refuses a device another process holds open ("Device or
  resource busy") and that best-effort delete is suppressed, so deleting the
  TAPs while QEMU still ran leaked every persistent TAP (process side first,
  then the devices — the same lesson as IOU's reverse stop order). Deleting
  a node never runs the link-teardown path, so those bridges would otherwise
  stay behind as empty orphans; a restart rebuilds them from the NIO.

## Link operations

| Operation | Kernel-datapath action |
|---|---|
| Create / attach | `brctl create` (EEXIST tolerated via `brctl show`) + `link set <bridge> up` + `brctl addif <bridge> <tap>` + carrier up + markers + `tc netem set` (filters) |
| Delete / detach | marker teardown → `tc reset <tap>` → carrier off → `brctl delif` → `brctl delete` (last endpoint wins; EBUSY/ENOENT suppressed). The TAP survives — the adapter keeps it for the next link |
| Reset (`POST /links/{id}/reset`) | delete + create (re-evaluates eligibility) |
| Suspend (`PUT /links/{id}` `{"suspend": true}`) | tap admin-down (writing to a down TAP fd fails with EIO, so the link is genuinely dead) + QMP `set_link gns3-N off` so the guest notices; resume restores both, and the netem qdisc survives the flap |

## Capture, markers, filters

Identical to Docker's kernel links, on the TAP: `capture start_kernel <tap>`
(driven by the NIO type, not by a link flag), `marker add_kernel <tap> …`
(only the capture node's end), and one `tc netem set` per anchor so each
direction is impaired once. `frequency_drop`/`quota`/`window_drop` run as the
eBPF classifier on the anchor's clsact egress.

## Legacy fallback

A uBridge build without the `tap` module (or without `CAP_NET_ADMIN`) keeps
the previous datapath untouched: local UDP tunnels into uBridge, QEMU launched
with `-netdev socket`, and the node logs a warning that it cannot carry kernel
links. Such a node is never offered a kernel link, so nothing fails.

## Verified

End-to-end through a real server (isolated instance, two QEMU nodes with a
stub binary, the test playing the guest by holding the TAP fds and pushing
frames): **32/32 checks** on the kernel datapath and **29/29** on the relay
variant (`enable_kernel_datapath = false`). Kernel run highlights:

* anchors created persistent and owned by the server user, QEMU's netdev is
  the TAP, no local UDP tunnel left; `link_list` reports `kernel_datapath: true`
  and one per-link bridge holds both taps;
* frames cross in both directions (~0.1 ms); `delay 100` ⇒ netem on both
  anchors and a measured **100.3 ms** one-way;
* suspend ⇒ anchor DOWN, no traffic, resume ⇒ 100.3 ms again (filter kept);
* capture ⇒ a 252-byte pcap written by `capture start_kernel`;
* link delete ⇒ bridge gone, qdisc clean, anchor alive; re-create ⇒ 0.1 ms
  with no residual impairment; node stop ⇒ no taps, no bridges left.

Relay run the same script with the flag off: same lifecycle, filter measured
at 109.8 ms (applied by uBridge's bridge — no netem on the anchor, as
expected), no kernel bridge holding the tap.

## Configuration

```ini
[Server]
# Wire eligible links (both endpoints on one compute, both able to anchor)
# through kernel interfaces instead of the uBridge UDP relay.
enable_kernel_datapath = True
```

## Known caveat

Anchors are host-side netdevs, so the kernel gives them an IPv6 link-local
address and emits MLD/DAD from them; those frames flood into the emulated
segment. The hardening requirement (anchors must be pure L2, no L3 identity)
is specified for uBridge in `docs/design/ubridge-l2-anchor-spec.md` and is
**delivered**: anchors and per-link bridges come up with `addrgenmode none`,
no addresses, and an idle anchor is silent (asserted in the e2e after a 2.5 s
settle).

One residual is accepted and documented there: enslaving a port makes the
*kernel* announce the bridge's multicast memberships once — an IGMPv3 plus one
or two MLDv2 reports in the first second — which floods into the segment like
any L2 control frame. It stops; it is outside the L2-only command's reach (no
addresses involved, IPv4 has no per-device IGMP switch).

## Roadmap

IOU (its fabric terminator in uBridge needs a TAP-terminated port —
`iol_bridge add_nio_tap`, frozen in
`docs/design/ubridge-iol-tap-anchor-spec.md`; unlike QEMU, one userspace hop
on the IOU leg is irreducible, the fabric is Unix sockets), Dynamips
(hypervisor-created taps, enslavable as they are), and the Ethernet switch /
cloud paths (their anchors are ubridge-owned by design) are still on the
relay; cross-compute kernel links need VXLAN/GENEVE encapsulation, which is
a separate project (it would serve Docker links the same way).

Update: **IOU has landed** on the same mixin — see
`docs/features/iou-kernel-datapath.md` (Ethernet bays anchor on persistent
TAPs bound to the IOL fabric; serial links stay relay). **Dynamips has
landed** too — see `docs/features/dynamips-kernel-datapath.md` (the
hypervisor opens uBridge-created TAPs with `nio create_tap`: the same
external-fd-holder shape QEMU uses; serial/ATM/POS ports stay relay).
**The Ethernet switch has landed** — see
`docs/features/ethernet-switch-kernel-datapath.md` (the switch absorbs a
peer's anchor into its own kernel bridge; switch-to-switch cascades stay
relay for now).
