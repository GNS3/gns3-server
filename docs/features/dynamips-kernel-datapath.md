<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# Dynamips kernel datapath

Dynamips routers emulate every port inside the Dynamips process; today a link
reaches a router through a UDP tunnel (a Dynamips `nio create_udp`, a
loopback port pair, the node's uBridge relay, and the link's UDP NIOs). The
kernel datapath replaces that segment with the same anchor model Docker,
QEMU and IOU use: every **Ethernet slot/port** owns a persistent TAP
(`gd{node_id[:8]}e{slot}p{port}`), created by the server through uBridge's
tap module, and links attach to the anchor — a per-link Linux bridge
enslaves it, tc impairments run on it, capture and markers anchor on it.
The Dynamips **hypervisor** opens the TAP with `nio create_tap` (QEMU's
move: an external process holds the fd), unprivileged because the server
handed the device's ownership to its own user.

```
 Dynamips hypervisor               root namespace
 ┌──────────────┐  nio create_tap  ┌────────────────────────────────┐
 │ IOS router   │◄────────────────►│ gd{id}e{slot}p{port}  (TAP)    │
 │ (emulated    │  holds the fd    │        │ per-link kernel bridge│
 │  ports)      │                  │        ▼   gns3{link_id}       │
 └──────────────┘                  └────────────────────────────────┘
```

The legacy relay is untouched: a port without a kernel link keeps its
Dynamips UDP NIO and the node's uBridge relay tunnel exactly as before, and
a kernel link binds the same port to its anchor instead — per port, no
node-wide switch.

## Datapath selection

`UDPLink._kernel_datapath_eligible` extends the common rules with:

* the compute must report **`ubridge_tap`** — the anchors are uBridge-created
  TAPs the hypervisor merely opens, the same capability QEMU gates on;
  there is no Dynamips-specific one;
* **both ports must be Ethernet**. The controller's port matrix decides
  per port; serial, ATM and POS ports keep the relay whatever the
  capabilities (the adapter registry in
  `compute/dynamips/adapters/adapter.py` names the Ethernet models —
  `ETHERNET_ADAPTERS` / `ETHERNET_WICS`, WIC-1ENET included, at its
  Dynamips port number `16 * (wic_slot + 1)`).

## Anchor lifecycle

* **Birth (node start)** — `_prepare_tap_datapath` probes the tap module
  (one create/delete cycle) and creates one persistent TAP per Ethernet
  slot/port, ownership handed to the server user, born DOWN. A stale
  leftover from a previous run is swept first; an anchor that already
  exists (restart) is kept — an anchor is never recreated under a live
  link. Serial/ATM/POS ports simply have no anchor.
* **Life** — a kernel link opens the anchor in the hypervisor
  (`nio create_tap`), binds it to the slot/port and enslaves it into the
  per-link bridge; removing the link unbinds the port, deletes the
  hypervisor's TAP NIO (releasing the fd) and tears the anchor out of the
  bridge. A link bound while the router is **stopped** is stored and wired
  by the next start (deferred wiring — the NIO simply waits in the slot
  adapter).
* **Death (node close)** — `_stop_ubridge` runs in **QEMU's order**, not
  IOU's: here the Dynamips hypervisor holds the anchor fds, so its TAP
  NIOs go first (`nio delete` closes the fd), then `tap delete` per anchor,
  then the per-link kernel bridges, then uBridge itself.

**A stop is not a close.** `stop` only halts the emulated router: the
hypervisor process — and with it the TAP fds, the port bindings and the
per-link bridges — survives `vm stop` (the same reason a relay link's
tunnel always survived a stop). Links therefore keep working through a
stop/start with no re-wiring at all; the restart's attach pass skips every
port that still has its TAP NIO. If the hypervisor died mid-flight (crash
or kill), the persistent TAPs remain and the next start re-attaches from
the stored NIOs.

## Link operations

| Operation | Kernel-datapath action |
|---|---|
| Create / attach | `nio create_tap` (hypervisor holds the fd) + `vm slot_add_nio_binding` + `brctl create` + `brctl addif` + carrier up + markers + `tc netem set` |
| Delete / detach | marker teardown → `tc reset` → carrier off → `brctl delif`/`brctl delete` → unbind + `nio delete` (release the fd) |
| Update (filters/markers/suspend changed) | reconcile on the anchor only — no re-binding, no re-enslaving |
| Suspend | anchor admin-down (traffic dead both ways) + resume restores |
| Adapter hot-add (OIR) | anchors for the new adapter's Ethernet ports created at once, so a kernel link can attach immediately |

## Capture, markers, filters

Capture on a kernel link is `capture start_kernel <anchor>`; markers ride
the base reconcile with the anchor as the location (`marker add_kernel` —
the shared KernelDatapathMixin machinery, no Dynamips-specific code);
filters are one tc netem qdisc per anchor plus cls_bpf/eBPF drops. A relay
port keeps its Dynamips NIO and the node's uBridge relay bridge
(`DYNAMIPS-*`) with userspace filters, exactly as before.

## Relay fallback

A uBridge without the tap module keeps the node relay-only: `_prepare_tap_datapath`
warns, no anchors are created, the warning says the node cannot carry
kernel links, and every link keeps its `nio create_udp` tunnel. The
controller never offers such a node a kernel link (capability unreported).

## Verified

Unit level (`tests/compute/dynamips/test_dynamips_kernel_datapath.py`):
anchor topology (Ethernet models and WIC-1ENET port numbering only), the
lifecycle (create/sweep/skip-existing), deferred wiring of NIOs bound
while stopped, attach/update/remove command shapes on both datapaths, the
stop order (hypervisor NIO delete before tap delete before brctl delete),
capture and marker shapes, hot-added adapters, and the manager's
`nio_bridge` construction. Plus the controller-eligibility cases (mixable
with docker/qemu/iou, tap capability required, serial excluded) in
`tests/controller/test_kernel_datapath_link.py`.

End-to-end (`tests/e2e/test_dynamips_kernel_datapath.py`, pytest marker
`e2e`) on a live server with **two real c7200 routers on a real IOS image**,
driven through the REST API and the IOS consoles with real ICMP:

* a link created while both routers are stopped selects the kernel
  datapath and is wired by node start (deferred wiring);
* the per-link kernel bridge on the host has exactly the two anchor TAPs
  enslaved; `show ip int brief` is up/up and ping R1→R2 succeeds;
* `delay 100` ⇒ netem qdisc visible on both anchors and the ping RTT
  grows by ~200 ms (one-way 100 per direction, each anchor impairing its
  own ingress side); clearing resets the qdiscs and the RTT;
* suspend ⇒ anchor administratively down, ping 0%; resume restores both;
* capture writes a pcap full of ICMP-over-Ethernet records;
* a **serial** link between the same two routers stays on the relay
  (per-port exclusion) and pings over it — the relay regression net;
* link delete/re-create: the bridge goes and comes back, the anchors
  survive, traffic resumes;
* router stop/start keeps the wiring intact (bridge membership unchanged,
  no duplicate NIOs) and traffic resumes after the reboot;
* deleting the project removes every anchor and bridge.

`test_dynamips_relay_control` is the negative control: the same topology on
an isolated relay-configured instance (`enable_kernel_datapath = false`)
has no per-link bridge and nothing enslaved, and still pings — so the
kernel objects above can only come from the kernel datapath.

## Configuration

```ini
[Server]
# Wire eligible links (same compute, both endpoints Ethernet and able to
# anchor) through kernel interfaces instead of the uBridge UDP relay.
enable_kernel_datapath = True
```

## Roadmap

The Ethernet switch is next (its ports are already uBridge-owned TAPs; the
kernel link should attach the peer's anchor straight into the switch's
per-node bridge), then the IOL Docker node. Cross-compute kernel links need
VXLAN/GENEVE encapsulation — deferred until every node type is kernelized.
