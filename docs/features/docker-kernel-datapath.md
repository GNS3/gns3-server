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
| Packet filters | uBridge userspace filters | tc netem on the veth host end (delay / packet_loss / corrupt / duplicate + the netem extensions rate, reorder, gemodel, seed, limit, jitter distributions, loss correlation); bpf as cls_bpf match-drop classifiers; frequency_drop and quota as the eBPF stateful classifier — every filter type has a kernel equivalent |
| Capture / markers | relay bridge | uBridge AF_PACKET modules on the veth host end |

The work landed in eight stages on branch stack `feat/docker-kernel-datapath` →
`feat/docker-kernel-capture` → `feat/docker-kernel-markers` →
`feat/docker-veth-everywhere` → `feat/docker-kernel-filters` →
`feat/docker-kernel-bpf-drop` → `feat/docker-kernel-netem-ext` →
`feat/docker-kernel-ebpf-drops`:

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
7. **netem extensions** — the netem-extension surface delivered in uBridge
   `feature/tc-netem-ext` is exposed as GNS3 filter types: `rate`,
   `reorder`, `gemodel`, `duplicate`, `seed`, `limit`, plus the delay
   `distribution` and loss/dup `correlation` parameters. Kernel-datapath
   links only (the relay has no equivalent); capability-gated per uBridge
   process. Reconcile became reset-before-set: the kernel's netem replace
   merges optional attributes, so removing a parameter needs the explicit
   reset.
8. **eBPF stateful drops** — `frequency_drop` becomes the eBPF classifier's
   exact every-Nth mode (`tc nth_drop`, uBridge `feature/tc-precision`;
   -1 = drop everything → every 1st) and the new kernel-only `quota` type
   the byte-cap mode (`tc quota_drop`). Needs a uBridge reporting `ebpf=1`
   (setcap cap_bpf,cap_net_admin,cap_net_raw=ep — verified working for a
   non-root server process, the production credential shape). With this,
   no filter type forces the relay anymore: kernel/relay is a purely
   topological choice.

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

Relay link on the same unified veth (fallback for mixed node types, cross-
compute wiring or when `enable_kernel_datapath` is off):

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
* `Server.enable_kernel_datapath` enabled (default)

Filters never disqualify the kernel path anymore — every type has a kernel
equivalent (netem / cls_bpf / eBPF classifier).

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
| `delay [ms, jitter, dist]` | netem `delay X jitter Y [distribution D]` | jitter 0 omitted; dist ∈ uniform/normal/pareto/paretonormal (kernel-only parameter) |
| `packet_loss [%, correl]` | netem `loss P [correl C]` | per direction (see below); correlation is a kernel-only parameter |
| `corrupt [%]` | netem `corrupt P` | |
| `duplicate [%, correl]` | netem `dup P [correl C]` | kernel-only type |
| `rate ["512kbit"]` | netem `rate B` | tc-style integer+unit (bit/kbit/mbit/gbit/bps/kbps/mbps, ≤100gbit); kernel-only type |
| `reorder [%, correl, gap]` | netem `reorder P [correl C] [gap G]` | requires `delay`; kernel-only type |
| `gemodel [p, r, 1-h]` | netem `loss gemodel P R H` | Gilbert-Elliot bursty loss; mutually exclusive with `packet_loss`; kernel-only type |
| `seed [u32]` | netem `seed N` | reproducible random draws; kernel-only type |
| `limit [pkts]` | netem `limit N` | queue depth above the 1000 default (rate+delay BDP); kernel-only type |
| `bpf` (one line per expression, OR) | `tc bpf_drop add <if> <prio> "<expr>"` — cls_bpf on clsact egress + gact drop | needs uBridge `cbpf=1` (`tc capabilities`, probed once per uBridge process); a line that fails to compile on the compute is skipped with a warning, mirroring the relay |
| `frequency_drop [N]` | `tc nth_drop <if> N` — the eBPF stateful classifier's exact every-Nth mode (clsact egress prio 1) | needs uBridge `ebpf=1`; -1 = drop everything → every 1st; per-direction counters (see below) |
| `quota [bytes, %]` | `tc quota_drop <if> <bytes> <pct>` — after the byte quota is consumed, each further packet drops with the given chance (100 = hard cutoff) | kernel-only type; needs `ebpf=1`; per-direction byte counters |

Semantics:

* **Both endpoints** receive the filter dict and attach one qdisc to *their*
  veth host end. The qdisc's egress covers traffic entering that container,
  so every direction of the link is impaired exactly once — the same net
  effect as the relay, where both directions cross the single filtered
  bridge. A `delay 100` link measures ≈200 ms RTT; `packet_loss 30`
  measures ≈51 % round-trip (1 − 0.7²); `rate 512kbit` adds ≈2× the
  per-packet serialization time to the RTT.
* **Reconcile = reset + full re-apply.** The kernel's netem replace MERGES
  optional attributes (rate, correlation, reorder, corrupt, gemodel,
  distribution: an absent attr keeps its previous value), so re-applying a
  filter set with a parameter *removed* would silently keep the old value.
  Every apply therefore starts with `tc reset` (also drops clsact and its
  bpf_drop filters — re-added right after in the same flow) followed by one
  `netem set` built from the current filters; no per-parameter diffing. An
  empty filter set is the reset alone (ENOENT-tolerated).
* **Extension gating.** The netem-extension keywords (rate, reorder,
  gemodel, dist, seed, limit, and the correl suffixes) probe
  `tc capabilities` once per uBridge process and require the tokens;
  a plain delay/loss/corrupt/dup filter never probes — an old uBridge
  serves the original surface untouched.
* **kernel-only vs relay-available.** The extension types and `quota` have
  no uBridge relay equivalent: `available_filters` hides them on relay
  links, setting one on a created relay link returns 409, and a project
  loaded with such filters on a link that cannot be kernel-wired drops them
  with a warning (invalid filters are dropped the same way at load).
  `frequency_drop` runs on both datapaths (relay userspace filter / eBPF
  every-Nth).
* **frequency_drop counting semantics differ per datapath.** The relay's
  single filtered bridge counts packets of BOTH directions through one
  counter; the kernel attaches one classifier per veth end, so each
  direction drops every Nth independently. For a round-trip measurement
  with every-Nth N: relay ≈ 1/N of frames (phase-locked), kernel = 1 −
  ((N−1)/N)² (e.g. N=3 → 55.6 % round-trip loss, measured 57 %). The
  kernel count is exact (atomic counter), unlike netem's stochastic loss.
* **Classifier order** on clsact egress: the eBPF stateful filter runs at
  prio 1, `bpf_drop` expressions at 10–99 — a packet dropped by the
  stateful modes never reaches the expression drops, and dropped packets
  never reach netem.
* **Validation** mirrors the tc grammar: `reorder` requires `delay`,
  `gemodel` and `packet_loss` are mutually exclusive (both map to the netem
  loss keyword), `distribution` requires jitter > 0, rate must be integer +
  unit ≤ 100gbit.
* **Node restart** restores the qdisc from the NIO (like capture and markers);
  **link deletion** detaches it explicitly — the veth survives the link and an
  orphaned qdisc would keep impairing the next one.
* **Suspend** keeps the qdisc (carrier-driven loss); the first packet after
  resume takes one extra delay interval (known netem idle-baseline behaviour)
  and steady state is exact.
* **bpf reconcile = flush + re-add** (`tc bpf_drop flush`, then one add per
  line at priorities 10, 11, …). `tc reset` (link delete / filter clear) is
  the full restore in uBridge: filters → clsact → root qdisc, idempotent.
* **Observability caveat:** clsact drops happen before the AF_PACKET tap
  points — markers/captures on the same veth do not observe cls_bpf-dropped
  frames (on the relay, filter-vs-mark ordering determined visibility
  instead). Also note `tc qdisc show` cannot print a distribution's name
  (the kernel stores only the sampled table).

## uBridge command surface

No uBridge changes were needed beyond the marker module's `*_kernel` commands
(the AF_PACKET capture module was pre-existing):

```
docker create_veth / delete_veth / move_to_ns / set_mac_addr
brctl create / delete / addif / delif / show
link set <if> up|down
capture start_kernel / stop_kernel
marker add_kernel / delete_kernel / enable_kernel
tc netem set <if> [delay <ms>] [jitter <ms>] [loss <%> [correl <%>] | loss gemodel <p> <r> <1-h>]
                                  [dup <%> [correl <%>]] [corrupt <%>] [reorder <%> [correl <%>] [gap <n>]]
                                  [rate <bw>] [limit <pkts>] [distribution uniform|normal|pareto|paretonormal] [seed <u32>]
tc bpf_drop add <if> <prio 10-99> "<expr>" / tc bpf_drop flush <if>
tc nth_drop <if> <n | off>        # eBPF exact every-Nth (frequency_drop)
tc quota_drop <if> <bytes> <pct> | off   # eBPF byte cap (quota)
tc reset <if>                     # full restore: eBPF filter -> bpf_drops -> clsact -> root qdisc, idempotent
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
48 % round-trip loss (expected 51 % = 1 − 0.7²); `frequency_drop` = 409 (at that
stage — superseded by the eBPF stage below);
suspend with delay active = 100 % loss, resume keeps the qdisc
(200.1 ms); node restart restores it (200.1 ms); link delete detaches it
(`/usr/sbin/tc qdisc show` — no netem left); re-created link has no residual
impairment.

bpf match-drop (same setup, 22/22 checks): `bpf "icmp"` = 100 % loss on both
ends' clsact; size-discriminating expression (`greater 150`) = small pings
pass / 300-byte pings dropped (real byte-level BPF match); two-line OR;
coexistence with netem (delay 50 → small pings 100.2 ms while big dropped);
clear removes clsact entirely; suspend/resume keeps the drops; link delete +
recreate leaves no residual filters; `frequency_drop` still 409 and hidden
(at that stage — superseded by the eBPF stage below); `available_filters` shows
`bpf`. Unit tests:
`tests/compute/docker/test_docker_kernel_datapath.py`,
`tests/controller/test_kernel_datapath_link.py`.

netem extensions (same setup, 24/24 checks): `rate 512kbit` on both veths,
1400-byte pings measure 45.5 ms RTT = baseline + 2× the 22.2 ms
serialization (exact); `delay 100 20 paretonormal` applies delay+jitter and
clears the previous rate (leak detector for the kernel's merge-on-replace);
`reorder 25 gap 5` visible in the qdisc dump and traffic passes;
`gemodel 100/0/30` = 50 % bursty round-trip loss with the previous reorder
cleared; `duplicate 50` link alive; `packet_loss 30 correl 50` shows
`loss 30% 50%`; `seed 42` + `limit 5000` both visible in the dump, RTT
exactly 2×50 ms; suspend/resume and node restart keep the filters; a
docker↔ethernet-switch relay link rejects `rate` with 409 and its
`available_filters` hides the kernel-only types while the kernel link shows
them all (frequency_drop included since the eBPF stage); `reorder` without `delay` and
`gemodel`+`packet_loss` are 409s; teardown leaves no netem on either veth.
Also verified live: a relay attach (`bridge add_nio_ethernet`) on the
admin-down veth host end fails in libpcap — the relay path now brings the
interface up before attaching.

eBPF stateful drops (same setup, 13/13 checks): `frequency_drop 3` installs
the tc_impair classifier on both veths (clsact egress pref 1, visible in
`tc filter show`); round-trip loss 57 % against the per-direction theory 1 −
(2/3)² = 55.6 % (each direction drops every 3rd independently — the relay's
single shared counter would give ≈ 1/3); `frequency_drop -1` = exactly
100 % loss; `quota 3000B/100 %` = pings pass until the byte cap then hard
cutoff; coexistence with `delay 50` (RTT 100.3 ms with every-4th drops);
clearing filters leaves no residual bpf filter; suspend = 100 % while down
with drops persisting after resume; node restart restores every-Nth on the
fresh veth; `available_filters` shows frequency_drop + quota on kernel
links and hides quota on relay links; a two-leg relay path through an
Ethernet switch still serves frequency_drop from the userspace filter
(56 % round-trip for N=3). The e2e also exposed and fixed a pre-existing
restart bug: the relay bridge-name registry was not cleared on stop, so a
node restart with a relay link skipped `bridge create` and failed. Unit tests:
`tests/utils/test_packet_filter_validation.py` (P6a class),
`tests/compute/docker/test_docker_kernel_datapath.py`,
`tests/controller/test_kernel_datapath_link.py`.
