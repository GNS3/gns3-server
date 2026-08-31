<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.

# Docker Link UDP Self-Loop Bug (One-Way Link)

## Bug Report

**Date**: 2026-08-14
**Severity**: Medium (one-way connectivity, CPU burn from packet duplication; intermittent)
**Status**: **Fixed** — root cause found and unit-tested (same day)
**Component**: UDP port allocation — `gns3server/compute/port_manager.py`
(`get_free_udp_port` find-then-add race); secondary: `gns3server/controller/udp_link.py`
(`_prepare` accumulated stale `_link_data` on reset)

## Symptoms

Two Docker nodes (observed with Cisco XRd; node-type agnostic) linked on the
same compute cannot ping each other. Packet capture on the link shows only **one**
side sending ARP. The other side's traffic never appears on the link at all.

## Evidence (from the live occurrence)

Captured simultaneously on both nodes' uBridge `bridge1` (see diagnostics below):

| Direction | Result |
|---|---|
| A → B | works — A's ARP requests arrive at B's bridge, B replies |
| B → A | dead — B's replies/ICMP appear only on **B's own bridge** (duplicated ×2–×3), nothing arrives at A |
| B's `ethN` counters | RX ≈ TX ≈ 5000+ — B receives its own transmissions back |
| A's `ethN` counters | TX > 0, RX = 0 — never receives anything |

## Root Cause (confirmed)

**`PortManager.get_free_udp_port` had an unguarded find-then-add sequence.**
A link allocates the UDP port for **both ends concurrently**
(`asyncio.gather` in `UDPLink._prepare` → two `POST /ports/udp`). The route
handler is a sync `def`, so FastAPI executes the two requests **in parallel
threads**. Both threads ran `find_unused_port` (socket-probing, GIL-releasing)
before either reached `_used_udp_ports.add(port)` — the set add is idempotent,
so no error was raised and **both ends were handed the same port number**:
`lport == rport` on both NIOs, a literal self-loop.

Why it was *silent* and *asymmetric*:

- uBridge sets `SO_REUSEADDR` on UDP NIO sockets (`ubridge/src/nio_udp.c`), so
  the second bind of the same port **succeeds** instead of failing with
  `EADDRINUSE` — link creation returned success.
- With two sockets bound to the same port, the kernel delivers to one of them
  (last bound wins). The node that started later — in the live case B,
  restarted ~77 s after A — received **everything**: A's packets *and* its own
  transmissions echoed back. The 77 s restart did not cause the corruption; it
  only decided which end starves.
- The same-compute condition is part of the trigger: both allocations hit the
  same `PortManager` instance (a cross-compute link races two processes and
  cannot self-collide).

A second, smaller defect was found while auditing: `UDPLink._prepare()`
**appended** to `self._link_data` but the committed NIOs are always taken from
indices 0/1 — after `reset()` (delete + create on the same object) the stale,
already-released port pair was re-committed and the freshly allocated ports
were leaked.

## Fix

| Change | Where |
|---|---|
| `threading.RLock` making find-then-add (and reserve/release) atomic for TCP and UDP | `gns3server/compute/port_manager.py` |
| `_prepare()` rebuilds `_link_data` from scratch instead of appending | `gns3server/controller/udp_link.py` |
| Regression tests: threaded allocation never returns duplicates (red on the old code); `reset()` commits the fresh mirrored pair with `lport != rport` | `tests/compute/test_port_manager.py`, `tests/controller/test_udp_link.py` |

## Diagnostics (uBridge console is the fast path)

1. **uBridge console** — each node's uBridge listens on a Unix socket
   `/run/user/1000/gns3/ubridge-<node_id>.sock`; connect and send:
   `bridge list` (NIO count per bridge), and
   `bridge start_capture bridge<N> "/tmp/ub-<node>.pcap"` /
   `bridge stop_capture bridge<N>` to capture what the bridge actually forwards.
   Comparing the two ends' pcaps localizes the break immediately.
2. **Container counters** — `docker exec <cid> ip -s link show ethN`:
   TX>0/RX=0 → peer never returns; RX≈TX huge with µs-scale duplicates → self-loop.
3. **UDP sockets** — `ss -uln` (no `-p`; uBridge runs setuid-root so process names
   are hidden, ports are visible): a two-node link owns exactly two "orphan" UDP
   ports. **One port instead of two = this bug.**
4. **Recovery** — delete and re-create the link (or stop/start both nodes);
   with the fix, the corruption no longer occurs in the first place.

Note: a Docker node's in-container `ethN` is a **TAP device** whose file descriptor
lives inside uBridge (the interface is created host-side, then moved into the
container namespace and renamed). There is no veth host end to look for — do not
waste time hunting for one in the host namespace.

## Related

- `docs/features/vendor-nos-xrd.md` — troubleshooting table entry pointing here.
- Link-create batch optimization (`controller/udp_link.py`, project-open bulk path)
  was exonerated: the pool path allocates sequentially in one handler and cannot
  self-collide.
