<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is AI-generated with reference to actual code and verified
> against real-kernel testing. AI can make mistakes — please verify against
> the source code when in doubt.

# Docker Kernel Datapath (veth + per-link Linux bridge)

## Overview

Docker node links historically flowed through a uBridge userspace relay: each
adapter was a TAP whose file descriptor uBridge pumped between the container
and UDP tunnels. This implementation replaces that model with **kernel-native
forwarding**: every adapter is born as a **veth pair**, and each link is a
**dedicated Linux kernel bridge** enslaving the two endpoints' veth host ends.
Frames never leave the kernel.

| | Old (relay) | New (kernel datapath) |
|---|---|---|
| Adapter interface | TAP moved into the container netns | veth pair (guest end in container, host end in root ns) |
| Link | uBridge bridge, TAP fd ↔ UDP, userspace copy | per-link kernel bridge `gns3{link_id[:11]}`, zero-copy |
| Relay latency | ~0.3 ms RTT | ~0.05 ms RTT (measured) |
| Link attach at runtime | yes (relay attaches the pre-existing TAP) | yes (brctl addif / add_nio_ethernet — interface untouched) |
| Packet filters | uBridge userspace filters | tc netem on the veth host end (delay / packet_loss / corrupt); bpf as cls_bpf match-drop classifiers; frequency_drop stays relay-only (eBPF classifier pending) |
| Capture / markers | relay bridge | uBridge AF_PACKET modules on the veth host end |

The work landed in six stages on branch stack `feat/docker-kernel-datapath` →
`feat/docker-kernel-capture` → `feat/docker-kernel-markers` →
`feat/docker-veth-everywhere` → `feat/docker-kernel-filters` →
`feat/docker-kernel-bpf-drop`:

1. **Kernel datapath** — NIOBridge NIO type, per-link bridges, carrier-based
   suspend, crash-safe reconciliation.
2. **Capture** — `capture start_kernel` (AF_PACKET) on the veth host end.
3. **Markers** — `marker add_kernel` (AF_PACKET + BPF) with the same signals,
   pcaps and fine-grained REST operations as the relay `mark` filter.
4. **veth-everywhere** — the TAP path deleted; every adapter is a veth and the
   datapath is a *runtime* decision (kernel or relay) that never touches a
   running container's interfaces.
5. **Filters** — impairment filters (delay, packet_loss, corrupt) become one
   tc netem qdisc per veth host end, pushed through uBridge's netlink `tc`
   module. This also removes the relay delay filter's nanosleep bottleneck
   (upstream #2827) from the kernel path.
6. **bpf match-drop** — the `bpf` filter (any line matching drops) runs as
   cls_bpf classifiers on the veth host end's clsact egress (`tc bpf_drop`:
   uBridge pcap-compiles the line to classic BPF, the kernel migrates it to
   eBPF internally — no CAP_BPF needed). Requires a uBridge reporting
   `cbpf=1` via `tc capabilities`; older builds get a clear upgrade error.

## Adapter interface types

Which interface a Docker node's adapters use is decided by the node class
(`Docker._select_node_class`, from `console_type` + `GNS3_*` environment
markers):

| Node class | Selected by | Adapter interface | Kernel links |
|---|---|---|---|
| `DockerVM` | default | veth pair | yes |
| `VendorDockerVM` (non-unix-socket) | `console_type=docker_exec`, `GNS3_SKIP_INIT`, … (XRd, SR Linux, …) | veth pair (same path via `super()`) | yes |
| `IOLDockerVM` | `GNS3_IOL_RUNNER=1` | AF_UNIX datagram socket pairs (`sNN`/`cNN`) — the container netns is unused | rejected (no host-side interface) |
| `VendorDockerVM` (unix-socket) | `GNS3_UNIX_SOCKET_NIO=1` | same socket contract, generic capability for vendor NOS images | rejected |

Unix-socket containers are detected both in the controller
(`_is_unix_socket_docker`, link eligibility) and on the compute side (NIO
rejection) — a missed detection surfaces as a clearer-late error.

## Architecture

Kernel link between two containers on the same compute:

```
 container A netns                 root namespace                  container B netns
 ┌────────────┐   veth pair   ┌───────────────────┐   veth pair   ┌────────────┐
 │ eth0 ◄─────┼───────────────┼─► gv{id}e0p0 ──────┼──►  gns3{lid} │──────────► │ eth0
 └────────────┘  gc{id}e0p0   │  (bridge port)     │  (bridge port)│            └────────────┘
                               │  per-link kernel  │   gv{id}e0p0
                               │  bridge = "cable" │
                               └───────────────────┘
```

Relay link on the same unified veth (fallback for filtered links or when
`enable_kernel_datapath` is off — e.g. to reach another compute):

```
 ┌────────────┐              ┌────────────────────────────┐              ┌────────────┐
 │ eth0       │    veth      │ uBridge relay bridge       │    UDP       │ peer node  │
 │ (gc end)   │◄────────────►│ add_nio_ethernet (AF_      │◄────────────►│ (any type, │
 └────────────┘  gv host end │ PACKET) ↔ add_nio_udp      │  tunnel     │  any host) │
                             └────────────────────────────┘              └────────────┘
```

Both datapaths anchor on the *same* veth host end; switching between them
(link delete + recreate) never touches the container-side interface.

## Datapath selection

`UDPLink._kernel_datapath_eligible` decides in the controller at NIO prepare
time; the compute side only reacts to the NIO type:

* both endpoints Docker (any class except unix-socket containers), same
  compute
* no active packet filters (filters live in the relay; kernelization via tc
  netem is planned)
* `Server.enable_kernel_datapath` enabled (default)

There is **no stopped-node requirement**. Since every adapter is a veth, links
attach to running containers: `brctl addif` (kernel) or
`bridge add_nio_ethernet` (relay) are runtime-safe operations on the host end.
On project (re)open every link re-runs `_prepare`, so relay links whose
endpoints became eligible are upgraded to the kernel datapath automatically.

## Adapter lifecycle

* **Birth (container start)** — `_create_veth`: stale sweep of any leftover
  pair (crash residue), `docker create_veth`, host end admin-down, MAC from
  the adapter base, `docker move_to_ns` of the guest end (renamed `eth{N}`, or
  the `GNS3_INTERFACE_NAMES` mapping). Names are deterministic:
  `gv|gc{node_id[:8]}e{adapter}p{port}` (≤ 15 chars). Unconnected adapters are
  born too (carrier off) so the interface is visible inside the container.
* **Life (running)** — the veth is never created/deleted/moved again. Link
  create/delete/switch, suspend, capture and markers only change *what is
  attached to the host end*.
* **Death (container stop)** — `_remove_kernel_veths` deletes the host ends
  explicitly: unlike a TAP (which died with the container netns), a veth host
  end outlives the container. Deleting either end destroys the pair.

## Link operations

| Operation | Kernel-datapath action |
|---|---|
| Create / attach | `brctl create` (EEXIST tolerated via `brctl show` verify) + `link set up` + `brctl addif` both ends (concurrent, race-tolerant) + carrier up + markers + `tc netem set` (filters) |
| Delete / detach | marker teardown → `tc reset` (netem teardown — the veth survives the link) → carrier off → `brctl delif` → `brctl delete` (last endpoint wins; EBUSY/ENOENT suppressed). The veth survives — unlike a relay bridge, whose death dropped its filters, an orphaned AF_PACKET marker would keep sniffing, hence the explicit teardown |
| Reset (`POST /links/{id}/reset`) | delete + create (re-evaluates eligibility) |
| Suspend (`PUT /links/{id}` `{"suspend": true}`) | veth host end admin-state down both ends — 100 % loss, no synthetic filter needed; resume restores (netem qdisc survives the carrier flap) |

## Capture

Kernel links capture via uBridge's AF_PACKET module bound to the veth host
end: `capture start_kernel <if> "<pcap>" [dlt]` / `capture stop_kernel`.
Single capture per uBridge process (second concurrent → EALREADY). Start/stop
key on the **NIO type**, not on veth presence — a relay NIO riding a veth
captures at its relay bridge.

## Markers

Markers ride the NIO like on the relay datapath, routed by `capture_node_id`;
the anchor is the veth host end instead of a relay bridge
(`_ubridge_apply_markers(anchor, nio)` is datapath-agnostic; DockerVM
overrides the add/delete/enable primitives to translate the commands):

```
marker add_kernel    <name> <if> "<bpf>" [tag <id>] [link <id>] [dir <tx|rx>] [linktype <name>] [pcap "<path>"]
marker delete_kernel <if> <name>                    # idempotent
marker enable_kernel <if> <name> <on|off>           # off = installed but silent
```

* Per-deployment convention: **only the capture node's end** runs
  `add_kernel` (symmetric with capture) — signals form clean send/return
  pairs (`PACKET_OUTGOING` on the host end = container receiving = `rx`).
* Same BPF compilation, MARK UDP signals, pcap files and fine-grained REST
  toggle/rebuild/delete endpoints as the relay `mark` filter.
* Node restart reinstalls markers from the NIO; link deletion tears them down.

## Packet filters

Impairment filters run **in the kernel** as tc netem qdiscs on the veth host
ends (uBridge `tc netem set`, raw netlink — no `tc` binary needed):

| GNS3 filter | kernel implementation | Notes |
|---|---|---|
| `delay [ms, jitter]` | netem `delay X jitter Y` | jitter 0 omitted |
| `packet_loss [%]` | netem `loss P` | per direction (see below) |
| `corrupt [%]` | netem `corrupt P` | |
| `bpf` (one line per expression, OR) | `tc bpf_drop add <if> <prio> "<expr>"` — cls_bpf on clsact egress + gact drop | needs uBridge `cbpf=1` (`tc capabilities`, probed once per uBridge process); a line that fails to compile on the compute is skipped with a warning, mirroring the relay |
| `frequency_drop` | — not yet (eBPF stateful classifier spec'd: [ubridge-kernel-impairment-spec](../design/ubridge-kernel-impairment-spec.md), part B pending) | 409 on kernel links; relay fallback |

Semantics:

* **Both endpoints** receive the filter dict and attach one qdisc to *their*
  veth host end. The qdisc's egress covers traffic entering that container,
  so every direction of the link is impaired exactly once — the same net
  effect as the relay, where both directions cross the single filtered
  bridge. A `delay 100` link measures ≈200 ms RTT; `packet_loss 30`
  measures ≈51 % round-trip (1 − 0.7²).
* **Reconcile = full re-apply.** `netem set` is an atomic replace (NLM_F_REPLACE),
  so every NIO update just rebuilds the qdisc from the current filters; no
  per-parameter diffing. An empty filter set detaches it (`tc reset`,
  ENOENT-tolerated).
* **Node restart** restores the qdisc from the NIO (like capture and markers);
  **link deletion** detaches it explicitly — the veth survives the link and an
  orphaned qdisc would keep impairing the next one.
* **Suspend** keeps the qdisc (carrier-driven loss); the first packet after
  resume takes one extra delay interval (known netem idle-baseline behaviour)
  and steady state is exact.
* A link carrying `frequency_drop` is wired on the **relay** (its eBPF
  stateful classifier is not delivered yet); `available_filters` hides it on
  kernel links and setting it returns 409 with a clear message. The remaining
  kernel-side roadmap is frozen in
  [docs/design/ubridge-kernel-impairment-spec.md](../design/ubridge-kernel-impairment-spec.md)
  (eBPF stateful classifier for `frequency_drop` + quota/window/flow modes,
  plus netem keyword extensions: rate, reorder, gemodel loss, jitter
  distributions — parts C and D of that spec are delivered).
* **bpf reconcile = flush + re-add** (`tc bpf_drop flush`, then one add per
  line at priorities 10, 11, …). `tc reset` (link delete / filter clear) is
  the full restore in uBridge: filters → clsact → root qdisc, idempotent.
* **Observability caveat:** clsact drops happen before the AF_PACKET tap
  points — markers/captures on the same veth do not observe cls_bpf-dropped
  frames (on the relay, filter-vs-mark ordering determined visibility
  instead).

## uBridge command surface

No uBridge changes were needed beyond the marker module's `*_kernel` commands
(the AF_PACKET capture module was pre-existing):

```
docker create_veth / delete_veth / move_to_ns / set_mac_addr
brctl create / delete / addif / delif / show
link set <if> up|down
capture start_kernel / stop_kernel
marker add_kernel / delete_kernel / enable_kernel
tc netem set <if> [delay <ms>] [jitter <ms>] [loss <%>] [dup <%>] [corrupt <%>]
tc bpf_drop add <if> <prio 10-99> "<expr>" / tc bpf_drop flush <if>
tc reset <if>                     # full restore: filters -> clsact -> root qdisc, idempotent
tc capabilities                   # "netem=<kw,...>;ebpf=0|1;cbpf=0|1", probed once per process
bridge add_nio_ethernet / add_nio_udp / start / stop / start_capture / stop_capture
```

## Configuration

```ini
[Server]
# Wire eligible Docker-to-Docker links through kernel veth/bridge interfaces
enable_kernel_datapath = True
```

Intended to grow into the global datapath switch as QEMU / IOU / Dynamips
migrate to kernel bridges (QEMU: tap enslaved per-link bridge, zero relay).

## Verification

End-to-end on a five-container FRR topology (mixed runtime-drawn and reloaded
links): 8/8 links on the kernel datapath, ping RTT ≈ 0.05 ms, FDB learning,
suspend = 100 % loss / resume restores, project reopen upgrades relay links,
runtime link creation on running containers, marker pcaps exact (tx/rx
pairs), capture freeze on stop, server restart reconciliation.

Filters (two-container kernel link, 27/27 checks): baseline 0.06 ms →
`delay 100` = 200.2 ms RTT (2× per direction) → `delay 50` = 100.2 ms
(atomic replace) → clear = baseline (qdisc detached); `packet_loss 30` =
48 % round-trip loss (expected 51 % = 1 − 0.7²); `frequency_drop` = 409;
suspend with delay active = 100 % loss, resume keeps the qdisc
(200.1 ms); node restart restores it (200.1 ms); link delete detaches it
(`/usr/sbin/tc qdisc show` — no netem left); re-created link has no residual
impairment.

bpf match-drop (same setup, 22/22 checks): `bpf "icmp"` = 100 % loss on both
ends' clsact; size-discriminating expression (`greater 150`) = small pings
pass / 300-byte pings dropped (real byte-level BPF match); two-line OR;
coexistence with netem (delay 50 → small pings 100.2 ms while big dropped);
clear removes clsact entirely; suspend/resume keeps the drops; link delete +
recreate leaves no residual filters; `frequency_drop` still 409;
`available_filters` shows `bpf` and hides `frequency_drop`. Unit tests:
`tests/compute/docker/test_docker_kernel_datapath.py`,
`tests/controller/test_kernel_datapath_link.py`.
