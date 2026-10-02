<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is AI-generated with reference to actual code and verified
> against real-kernel testing. AI can make mistakes — please verify against
> the source code when in doubt.

# IOL runner container kernel datapath

## Overview

IOL runner containers (`IOLDockerVM`, selected by the `GNS3_IOL_RUNNER`
environment marker — the Cisco CML `iol-runner` images such as
`iol-xe/iol-xe:17-18-02`) have no container-namespace networking at all:
their guest leg is the runner's per-interface AF_UNIX datagram socket pairs.
A unix socket is not a kernel interface, so until now every link of such a
container rode the uBridge userspace relay (unix ↔ UDP).

The kernel datapath gives every Ethernet bay/unit a **persistent TAP anchor**
(`gx` names, born at node start exactly like IOU's) and wires the *link
segment* through the kernel. One userspace hop on the container leg is
irreducible — the socket pair is the only physical layer the runner exposes —
but the anchor → per-link bridge → peer anchor crossing, the kernel filters,
the suspend carrier and the AF_PACKET capture/markers are all native now.

```
 container netns (iol-runner)      root namespace
 ┌────────────┐  unix datagram    ┌────────────────────────────────┐
 │ netiomux   │◄─ sNN/cNN.sock ──►│ uBridge port bridge            │
 │ (sNN/cNN)  │   (host-side dir) │   [nio_unix, nio_tap] relay    │
 └────────────┘                   │        │ holds the TAP fd      │
                                  │        ▼                       │
                                  │   gx{id}e{bay}p{unit} ─────────┼─► gns3{link_id}
                                  │   (persistent TAP anchor)      │   (per-link kernel
                                  └────────────────────────────────┘    bridge port)
```

The port bridge is the deployment shape ubridge's
`doc/gns3server-integration.md` § *bridge — generic NIO relay with a
swappable TAP leg* froze: a per-node bridge created at start, the unix NIO in
the first slot for the node's whole life, the topology leg in the second —
`add_nio_udp` (relay) or `add_nio_tap` (kernel link) — swapped as links are
attached, suspended, deleted or the project reopens, through
stop → delete → add → start. The c-socket binding never re-binds across a
swap: frames the container sends while the bridge is stopped queue on the
socket and relay after `start` (regression-tested in ubridge's bridge suite).

## Datapath selection

`UDPLink._kernel_datapath_eligible` treats an IOL runner container like any
Docker node (same compute, Ethernet port) with one gate of its own in
`_kernel_endpoint_ready`: the compute must report both

* `ubridge_tap` — the tap module (`tap create`/`tap delete`), the same
  capability QEMU and Dynamips gate on, and
* `ubridge_bridge_tap` — `bridge delete_nio_tap`, the swappable-leg command
  (probed with one command against a bridge that cannot exist: 202 = old
  build, 214 = new; no scratch objects, no capabilities, cached by binary
  identity like every other probe).

Both strict `True`; anything unreported (old uBridge, failed probe) keeps the
link on the relay, where it always works. The generic `GNS3_UNIX_SOCKET_NIO`
containers stay excluded as before — that marker's semantics are
image-specific, while `GNS3_IOL_RUNNER` selects a class whose anchors this
server owns.

## Anchor lifecycle

* **Birth (node start, before any link)** — `_start_ubridge` runs
  `_prepare_tap_datapath` right after the hypervisor connects: probe both
  capabilities, then for every (bay, unit 0-3) sweep a leftover
  (`tap delete`, suppressed), `tap create` (hardened, starts DOWN) and
  `link set down` — carrier off until a link attaches. The anchors exist
  whether or not any link ever uses them: an anchor born with its link would
  leave the Ethernet switch fast path's deferred join waiting forever.
  No `tap set_owner`: uBridge itself holds these fds.
* **Life** — the anchor is never recreated. Link create/delete/switch,
  suspend, capture and markers only change what is attached to it, and the
  ensure-then-add contract guards the one window where the device could have
  been swept (`/sys/class/net` existence check — `tap create` is strictly
  create-only, `IFF_TUN_EXCL`, and refuses an existing device with EBUSY).
* **Death (node stop)** — the port bridges hold the anchor fds
  (`bridge add_nio_tap`), so they are deleted first (`bridge delete` stops
  their relay threads and frees the NIOs), then the anchors themselves
  (`tap delete` answers EBADFD on a device another fd still holds), then the
  per-link kernel bridges — all while the control channel lives, before the
  hypervisor stops. A restart recreates everything from the NIO.

## Link operations

* **Kernel link create** (`_attach_kernel_link`): ensure the port bridge and
  its unix NIO → ensure the anchor → `bridge add_nio_tap` (uBridge opens and
  holds the fd) → the shared mixin flow (`brctl create`/`addif` the per-link
  bridge, capture, markers, tc netem/cls_bpf/eBPF filters on the anchor) →
  `bridge start` (the [unix ↔ tap] relay) → the carrier pass (which is also
  what brings a born-down anchor up; a suspended NIO sets it back down).
* **Link delete** (`_release_port_tap`): `bridge stop` (delete_nio_tap
  refuses while running — the relay threads hold the NIO pointers for their
  whole life; freeing under them is a use-after-free) →
  `bridge delete_nio_tap <bridge> "<tap>"` (matched on the kernel-resolved
  name) → the mixin teardown (markers, tc reset, `brctl delif`, per-link
  bridge deletion). The anchor survives — the node owns it, not the link.
* **Relay link** — unchanged: the port bridge's second leg is `add_nio_udp`,
  userspace filters at the port bridge. The unix NIO stays in its slot
  across every datapath switch.

## Capture, markers, filters

Inherited from `KernelDatapathMixin` unchanged — everything is keyed on the
anchor interface name, which is why a TAP and a veth host end are
interchangeable there: `capture start_kernel` / `marker add_kernel`
(AF_PACKET), one tc netem qdisc (the full netem surface plus the
extensions), `bpf` as cls_bpf match-drop, `frequency_drop`/`quota`/
`window_drop` as the eBPF stateful classifier — all capability-gated per
compute exactly like the Docker veth datapath.

Suspend semantics: anchor admin-down. The port bridge's TAP writes fail EIO
(tolerated by the delivered uBridge hardening) and its reads fall silent —
traffic stops both ways. The runner itself is unaware of the link state
(netiomux has no carrier signal), exactly as on the relay datapath where
suspend rode the synthetic frequency_drop filter instead.

## Relay fallback

Missing either capability, the node runs relay-only: links ride
unix ↔ UDP, `kernel_datapath` stays false, and anchors are simply never
created (or, with `enable_kernel_datapath` off server-wide, created but
never attached — the same semantics as QEMU's and Dynamips' anchors).

## Verified

Live on the real server (`tests/e2e/test_iol_docker_kernel_datapath.py`,
isolated instance, real `iol-xe/iol-xe:17-18-02` images, real uBridge with
`bridge delete_nio_tap`):

* kernel link reports `kernel_datapath`, anchors exist from node start, the
  per-link bridge enslaves exactly the two of them;
* real ICMP crosses the [unix ↔ tap] port-bridge relay (100 % ping);
* the L2-anchor spec §E.2 silence window with the guests shut — the
  behavioral half of the hardening on anchors created by uBridge's bridge
  TAP module (`bridge add_nio_tap`);
* `delay 100` lands as netem on both anchors, measured RTT grows ≥ 150 ms
  and returns < 50 ms when cleared;
* the classifier spot check on a TAP anchor (the Docker suite runs the full
  matrix on veth host ends): `bpf "icmp"` drops everything (clsact on the
  anchor), `frequency_drop 3` as the eBPF every-nth mode measured 56 %
  round-trip loss (theory 55.6 %), both restoring on clear;
* suspend admin-downs the anchor and kills the traffic; resume restores;
* AF_PACKET capture writes a real pcap of the ICMP exchange;
* link delete/re-create swaps the port bridge's TAP leg out and back in
  (unix binding never re-binds) with the ping returning;
* node stop tears the anchors down (no `gx` devices left), a restart
  recreates the whole wiring from the NIO;
* project delete leaves no anchors and no bridges; the relay control on a
  relay-configured instance keeps the link off the kernel and still pings.

Also caught and fixed live: `tap create` is strictly create-only
(`IFF_TUN_EXCL`) — the ensure-then-add guard must check existence first
(`/sys/class/net`), not re-create unconditionally (EBUSY on the device the
start loop just made).

## Configuration

```
[Server]
enable_kernel_datapath = True   # the global switch (link attachment)
```

The anchor lifecycle needs no configuration of its own — the capability
probes decide per compute, and an IOL runner container without them simply
never anchors.

## Roadmap

Cross-compute kernel links need VXLAN/GENEVE encapsulation — deferred until
every node type is kernelized; with the IOL runner container anchored, that
condition is one project away from met.
