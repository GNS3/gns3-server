<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> Frozen requirements spec for the **uBridge** project. Status: **delivered
> and verified from the server side** — implemented on the
> `feature/iol-tap-anchor` branch of the ubridge fork (both commands, the §B
> hardening, and one fix beyond the spec: `iol_bridge delete` now releases
> every port NIO even when the bridge was not running, so a stopped node's
> anchor fds never leak). The server side landed on
> `feat/iou-kernel-datapath` and passed a live e2e (64/64 kernel, 62/62
> relay; see `docs/features/iou-kernel-datapath.md`).
>
> Notes from the implementation: the two new commands answer `208` for a
> missing bridge where the older `add_nio_udp` answered `214` (no client
> branches on the code), and a write to an admin-DOWN anchor logs one
> `perror` line per dropped frame.
>
> Scope guard: no wire format change, no change to existing commands or
> replies. This adds one NIO type to the existing `iol_bridge` module (two
> commands) plus one error-tolerance fix in the two listener threads. The
> `tap`, `brctl`, `link`, `tc`, `marker` and `capture` modules are reused
> as-is.

# IOL bridge TAP anchor ports (`iol_bridge add_nio_tap`)

## 0. Background & scope

### What IOU's physical layer is

An IOU instance has no host netdev. Its only wire is the Unix-datagram
fabric in `/tmp/netio<uid>/`: frames carry an 8-byte IOL header (dst id,
src id, dst port, src port, message type, channel), and the NETMAP file
maps every `bay/unit` of the instance to a second, fake instance — which
today is uBridge itself (`iol_bridge create <name> <app_id + 512>`,
binding `/tmp/netio<uid>/<app_id + 512>`). Each port of that fake
instance terminates on a **destination NIO**, and the only destination
NIO type is UDP (`iol_bridge add_nio_udp`): one listener thread per port
relays fabric → NIO, and one bridge listener relays fabric-side reads →
NIO sends.

### The problem

With UDP as the only termination, every IOU link is a uBridge userspace
relay leg:

- an IOU port cannot join a per-link kernel bridge, so IOU ↔ Docker/QEMU
  traffic always crosses through a UDP relay even when both ends sit on
  the same compute;
- kernel-class impairments (`tc netem`, the clsact eBPF classifiers) and
  the `*_kernel` capture/marker commands cannot anchor on an IOU port —
  only the userspace packet filters apply, whose delay implementation is
  the known blocking-nanosleep defect that inflates RTT under load;
- suspend of a single link has no clean mapping.

### What this change is — and what it cannot be

Give the port a second destination NIO type: a **persistent TAP,
created by gns3-server with the existing `tap create` command and opened
(held) by uBridge**. uBridge's iol_bridge then plays, on that TAP, the
same role the QEMU process plays on its TAP: it is the device's
userspace endpoint. Everything the anchor model already delivers —
`brctl addif` enslavement, `tc` on the anchor, `capture start_kernel`,
`marker add_kernel`, `link set up/down` for carrier/suspend — is keyed
on the interface name and does not care who holds the fd.

One userspace hop on the IOU leg is irreducible: the Unix fabric is
IOU's only physical layer, so frames always pass
fabric ↔ listener thread ↔ TAP fd. What kernelization buys is that the
**link segment itself** is the kernel: anchor → per-link bridge → peer
anchor, with kernel filters, markers and capture on the anchors, and
suspend mapped to anchor admin-down. That is the accepted design, not a
deficiency of this spec.

### Goal

`iol_bridge` ports can terminate on a pre-existing persistent TAP
anchor, with the same lifecycle semantics as `add_nio_udp` (attach
before or after `iol_bridge start`, replace a previous NIO, delete and
re-add), and the relay survives — without exiting — the anchor being
administratively DOWN, which is a steady state of this design (port
anchored but no link attached; link suspended).

Explicitly **not** in scope:

- creating or deleting the TAP device itself — the server owns the
  anchor lifecycle through the existing `tap` module (`tap create`,
  `tap delete`; the device is created hardened per the L2-only spec);
- serial bays — a TAP carries Ethernet frames; serial links stay on
  `add_nio_udp`;
- an MTU command (`link set <if> mtu <n>`) — does not exist today and is
  not required by default-MTU IOU traffic; noted as future work if
  jumbo frames ever matter;
- any change to the NETMAP, the IOL header encoding, or the L1
  keepalive protocol.

## A. New commands

Belong to the existing `iol_bridge` module, next to their UDP
counterparts. `bay`/`unit` and the IOL header handling are identical to
`add_nio_udp`.

### `iol_bridge add_nio_tap <bridge> <iol_id> <bay> <unit> <tap_name>` (6 args)

| Arg | Description |
|-----|-------------|
| `<bridge>` | An existing IOL bridge (`208` if not) |
| `<iol_id>` | The real instance's application id, encoded into the IOL header as with `add_nio_udp`; the existing "`iol_id` == bridge id" refusal in `create_iol_port_entry` applies unchanged |
| `<bay>`, `<unit>` | Port coordinates, same encoding and MAX_PORTS check as `add_nio_udp` |
| `<tap_name>` | A **pre-existing** network device (`208` if not, see below); ≤ IFNAMSIZ−1 chars (`204` otherwise) |

Semantics:

1. **Require an existing device.** Resolve `<tap_name>` with
   `if_nametoindex` first and refuse with `208` when absent. This is the
   same reasoning as the `tap` module's `tap_require_existing`: without
   the check, `TUNSETIFF` silently *creates a transient* TAP that dies
   with the fd — an anchor that vanishes on detach is worse than a
   clear error.
2. Open the device with the existing `create_nio_tap()` (by-name
   `TUNSETIFF`, `IFF_TAP | IFF_NO_PI`, default carrier). No owner or
   persistence ioctl — the device is persistent and owned already.
3. Install it through the existing `create_iol_port_entry()`, which is
   generic over `nio_t *`: it frees whatever NIO the port held before
   (listener stop guarded on `tid`, delay lines torn down under
   `iol_delay_lock`, capture/filters freed), pre-computes the IOL
   header, and starts the port listener if the bridge is running. A
   port may therefore swap `add_nio_udp` ↔ `add_nio_tap` repeatedly —
   that is the datapath-switch path and must keep working.
4. If the fd cannot be opened (`create_nio_tap` fails), reply `206` and
   free the nio as the UDP handler does.

No `carrier` argument: administrative state is the server's lever, via
the existing `link set <tap> up|down`.

### `iol_bridge delete_nio_tap <bridge> <bay> <unit>` (3 args)

Same body as `cmd_delete_nio_udp`, including its thread-safety guards:
stop the port listener (cancel guarded on `tid != 0`, join), destroy
both delay lines under `iol_delay_lock`, free capture, filters and the
NIO (which closes the TAP fd). **The persistent device itself survives**
— the server deletes it with `tap delete` when the node stops, exactly
as it does for QEMU anchors. Deleting a port that holds no NIO is a
no-op `100` (mirrors `delete_nio_udp`).

Replies:

```
iol_bridge add_nio_tap IOL-BRIDGE-513 1 0 0 gi0badfe9e0p0
100-NIO TAP added to IOL bridge 'IOL-BRIDGE-513'
iol_bridge delete_nio_tap IOL-BRIDGE-513 0 0
100-NIO TAP deleted from IOL bridge 'IOL-BRIDGE-513'
```

## B. Required hardening: the anchor can be administratively DOWN

A TAP anchor is expected to sit admin-DOWN for long periods (port
anchored, no link attached yet; or the link suspended). The listeners
must treat that as normal:

1. **`iol_bridge_listener`, NIO send path** (IOL → TAP, `nio->send` = a
   `write` on the fd): a write to an admin-DOWN TAP fails with **EIO**.
   The current tolerated set is `ECONNREFUSED | ENETDOWN | EINVAL`,
   anything else is `exit(EXIT_FAILURE)` — which would take the whole
   uBridge down the first time a suspended link carries traffic. Add
   `EIO` to the tolerated set: drop the frame (optionally a debug log)
   and continue.
2. **`iol_nio_listener`, NIO receive path** (TAP → IOL, `nio_recv` = a
   `read` on the fd): while the device is DOWN the read blocks (no
   carrier), which is fine — but a return of `0` must not be counted or
   forwarded (it would fabricate header-only packets for the instance).
   Treat `recv <= 0` as continue; treat `-1` with `EIO` as continue
   alongside the existing `ECONNREFUSED | ENETDOWN`.

No other listener behavior changes: the fabric-side `sendto` already
tolerates `ENOENT`/`ECONNREFUSED` for the window where the IOU process
has not created its endpoint yet, and that stays.

## C. Implementation notes

- The command handlers are thin: existence check + `create_nio_tap` +
  `create_iol_port_entry` (add), and the `cmd_delete_nio_udp` body
  (delete). The three copies of that teardown block in the module are a
  pre-existing pattern — a shared helper is welcome but not required by
  this spec.
- Do **not** route the TAP through `nio_tap_open`'s `/dev/net/tun`
  path-name variant; the anchor is addressed by interface name.
- Statistics (`iol_bridge get_stats`) work unchanged: the counters hang
  off the generic nio and both listeners already update them.
- Port filters, delay lines, capture (`iol_bridge add_packet_filter`,
  `start_capture`, …) keep working on a TAP-terminated port; gns3-server
  simply will not combine userspace filters with `tc` on the same port
  (see the alignment section).

## D. Reply contract & error codes

| Code | Meaning |
|------|---------|
| `100` | OK — NIO added/deleted (delete of an empty port is also `100`) |
| `203` | Bad number of parameters |
| `204` | Invalid parameter (tap name longer than IFNAMSIZ−1) |
| `206` | Unable to create (bridge exists but the TAP fd cannot be opened) |
| `208` | Unknown object — bridge or **tap device** does not exist |

Old builds answer `202-Unknown command` for both commands; gns3-server
uses that to fall back to the UDP datapath, mirroring the `tap`-probe
degradation.

## E. Test requirements

1. **Both-direction relay.** On a running IOL bridge with one
   TAP-terminated port: a frame sent on the fabric for that bay/unit
   appears on the TAP netdev (stripped of the IOL header); a frame
   injected on the netdev reaches the fabric with the port's correct
   8-byte header. (A scratch Unix-datagram endpoint can play the
   instance; no IOU binary is needed.)
2. **No transient device.** `add_nio_tap … nosuchtap0` → `208`, and no
   interface is created (`ip -o link` unchanged).
3. **Unknowns.** Unknown bridge → `208`; name ≥ IFNAMSIZ → `204`; a
   bridge-id == iol_id → the existing refusal.
4. **Delete keeps the device.** After `delete_nio_tap`, the port has no
   NIO (stats/list reflect that), the TAP netdev still exists, and the
   port accepts `add_nio_udp` (and re-`add_nio_tap`) afterwards.
5. **Swap semantics.** A port holding a UDP NIO that gets `add_nio_tap`
   releases the UDP socket (old listener joined, port usable), and vice
   versa — no fd or thread leak after several swaps.
6. **DOWN-anchor resilience.** With the TAP admin-DOWN, drive traffic
   from the fabric side for ≥ 100 frames: uBridge stays alive, frames
   are dropped, nothing is written to the netdev. After `link set up`,
   traffic flows again. This is the regression test for §B.1.
7. **Idle DOWN port is quiet.** A DOWN anchored port produces no
   header-only or zero-length fabric sends (§B.2).
8. **Kernel-bridge interop.** Enslave the anchor into a kernel bridge
   (`brctl create` + `addif`) while the port relays: frames cross
   bridge ↔ fabric through the port, and a peer port on the same bridge
   receives them. This is the actual deployment shape.

## gns3-server alignment (informational — not uBridge scope)

- **Anchors**: one TAP per Ethernet bay/unit, `gi{node_id[:8]}e{bay}p{unit}`,
  created persistent (hardened by `tap create` per the L2-only spec) at
  node start, swept for stale leftovers first, `tap delete`d at node
  stop — the exact lifecycle QEMU anchors use. All Ethernet ports are
  anchored at start ("tap-everywhere"); serial bays never are.
- **Links**: kernel links enslave the anchor via the shared
  `KernelDatapathMixin` (`brctl create`/`addif`, `tc`, markers,
  `capture start_kernel`, suspend = anchor admin-down). Relay links keep
  `add_nio_udp` and never touch the anchor. A port switching datapaths
  is just an NIO swap (§A.3).
- **Filters are never double-applied**: on a kernel link only the anchor
  `tc` path is used; the port's userspace filters carry relay links
  only.
- **Capability gating**: the eligibility check needs to know the command
  exists before creating a link. Probe by attempting the operation on a
  scratch bridge + scratch TAP (create, `add_nio_tap`, delete, clean
  up), cached by binary identity like `probe_tap_support`, reported
  through `/capabilities`; an old build answering `202` keeps IOU on
  the relay datapath.
- **L1 keepalives**: unchanged — an anchored-but-unconnected port holds
  no NIO from the server's perspective, so the responder keeps ignoring
  it and IOU sees the port down, which matches the anchor being DOWN.

## Roadmap note

`link set <if> mtu <n>` does not exist today. Default-MTU IOU traffic
does not need it; if jumbo IOU frames ever matter it becomes a small,
separate requirement on the `link` module.
