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
| Packet filters | uBridge userspace filters | not supported yet (tc netem roadmap) → relay fallback |
| Capture / markers | relay bridge | uBridge AF_PACKET modules on the veth host end |

The work landed in four stages on branch stack `feat/docker-kernel-datapath` →
`feat/docker-kernel-capture` → `feat/docker-kernel-markers` →
`feat/docker-veth-everywhere`:

1. **Kernel datapath** — NIOBridge NIO type, per-link bridges, carrier-based
   suspend, crash-safe reconciliation.
2. **Capture** — `capture start_kernel` (AF_PACKET) on the veth host end.
3. **Markers** — `marker add_kernel` (AF_PACKET + BPF) with the same signals,
   pcaps and fine-grained REST operations as the relay `mark` filter.
4. **veth-everywhere** — the TAP path deleted; every adapter is a veth and the
   datapath is a *runtime* decision (kernel or relay) that never touches a
   running container's interfaces.

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
| Create / attach | `brctl create` (EEXIST tolerated via `brctl show` verify) + `link set up` + `brctl addif` both ends (concurrent, race-tolerant) + carrier up |
| Delete / detach | marker teardown → carrier off → `brctl delif` → `brctl delete` (last endpoint wins; EBUSY/ENOENT suppressed). The veth survives — unlike a relay bridge, whose death dropped its filters, an orphaned AF_PACKET marker would keep sniffing, hence the explicit teardown |
| Reset (`POST /links/{id}/reset`) | delete + create (re-evaluates eligibility) |
| Suspend (`PUT /links/{id}` `{"suspend": true}`) | veth host end admin-state down both ends — 100 % loss, no synthetic filter needed; resume restores |

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

Not supported on the kernel datapath yet: a link with active filters is wired
on the relay (where uBridge's userspace filters apply), and adding filters to
an existing kernel link returns 409. Kernelization via `tc netem` on the veth
is the planned next stage — it also removes the relay's `delay` filter
nanosleep bottleneck under high packet rates.

## uBridge command surface

No uBridge changes were needed beyond the marker module's `*_kernel` commands
(the AF_PACKET capture module was pre-existing):

```
docker create_veth / delete_veth / move_to_ns / set_mac_addr
brctl create / delete / addif / delif / show
link set <if> up|down
capture start_kernel / stop_kernel
marker add_kernel / delete_kernel / enable_kernel
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
pairs), capture freeze on stop, server restart reconciliation. Unit tests:
`tests/compute/docker/test_docker_kernel_datapath.py`,
`tests/controller/test_kernel_datapath_link.py`.
