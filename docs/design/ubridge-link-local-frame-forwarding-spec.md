# uBridge bridge ports must forward link-local frames (per-port `group_fwd_mask`)

> **Status: landed and verified.** uBridge branch `feature/bridge-tap-l2only`,
> commits `0284500` (feat), `03a18f1` (test suite), `cf4e494` (docs) — the
> implicit `addif` hook of §A.1 plus the `setportgroupfwd` escape hatch of
> §A.3. gns3-server carries **zero product-code changes**: the behavior
> reaches every `brctl addif` call site as specified. Verified by the uBridge
> suite (`tests/brctl/test_linklocal.py`, 28/28) and live through a real
> server by `tests/e2e/test_docker_link_local_frames.py`. The three
> `test_vlan` kernel-state failures seen alongside are pre-existing on the
> parent commit (verified by an fb72758 control run). The version bump (R8)
> is still open, pending review.

## 0. Background & scope

### The datapath this serves

GNS3's kernel datapath wires a link by enslaving each endpoint's host-side
anchor (veth host end, TAP) into a per-link Linux bridge. The same shape is
used by the Ethernet switch node (its bridge absorbs peers' anchors), by
switch-to-switch cascades (a veth pair joining two bridges) and by the Cloud
node (pnet bridges). Functionally these bridges stand in for **a cable** — a
transparent L2 segment — and that is the contract users expect from them.

### The problem: a Linux bridge is not a transparent cable

`br_handle_frame()` in `net/bridge/br_input.c` treats the IEEE 802.1D
reserved link-local range `01:80:c2:00:00:00`–`01:80:c2:00:00:0f` specially
and, by default, does **not** forward it. Measured on a stock mainline kernel
(7.2.6, no patches) with two ports in one bridge:

| Destination MAC | Protocol | Default bridge | Notes |
|---|---|---|---|
| `ff:ff:ff:ff:ff:ff`, `01:00:5e:*`, `33:33:*` | broadcast, IPv4/IPv6 multicast | forwarded | unaffected |
| `01:80:c2:00:00:00` | STP / RSTP BPDU | **forwarded** | special-cased: forwarded while the bridge runs no STP |
| `01:80:c2:00:00:01` | 802.3x PAUSE / 802.1Qbb PFC | not forwarded | kernel drops unconditionally — see §0.3 |
| `01:80:c2:00:00:02` | LACP / slow protocols | not forwarded | |
| `01:80:c2:00:00:03` | 802.1X EAPOL | not forwarded | |
| `01:80:c2:00:00:0e` | LLDP (DCBX) | not forwarded | |
| `01:80:c2:00:00:10` and up | — | forwarded | outside the reserved nibble range |

Consequence: on a kernel-datapath link, two emulated devices that run LACP,
LLDP/DCBX or 802.1X never see each other, while the same lab over the uBridge
UDP relay (a dumb store-and-forward, fully transparent) works. The two
datapaths disagree, and the failure is silent.

### Why the bridge-level knob is not enough

`IFLA_BR_GROUP_FWD_MASK` (the bridge-level attribute, already reachable via
uBridge's `brctl setgroupfwd`) is restricted by `BR_GROUPFWD_RESTRICTED`
(`BR_GROUPFWD_STP | BR_GROUPFWD_MACPAUSE | BR_GROUPFWD_LACP`): writes
containing bits 0/1/2 fail with `EINVAL`. Measured: bridge-level accepts at
most `0xfff8`, which forwards LLDP/EAPOL but **not LACP**.

The per-port attribute `IFLA_BRPORT_GROUP_FWD_MASK` (commit
`5af48b59f35cf712793badabe1a574a0d0ce3bd3`, "net: bridge: add per-port
group_fwd_mask with less restrictions", net-next 2017, Linux 4.15) exists
precisely for this: its commit message names "transparent forwarding of
most link-local frames (e.g. STP, LACP) through tunnels (vxlan, qinq)" and
restricts only MAC PAUSE. Measured: port-level accepts `0xfffd` and then
forwards STP, LACP, EAPOL, LLDP and every other reserved address.

The mask is evaluated on the **ingress** port (setting it on the egress port
only has no effect), so every port of a bridge needs it — which is exactly
what a per-addif hook gives us.

### What this change is — and what it cannot be

PAUSE / PFC is **not** in scope and cannot be delivered by any mask: the
`case 0x01:` branch in `br_handle_frame()` drops unconditionally
(`kfree_skb_reason(..., SKB_DROP_REASON_MAC_IEEE_MAC_CONTROL)`) without
consulting `fwd_mask`, and the port-level setter rejects bit 1 with `EINVAL`.
Forwarding PAUSE would require patching that branch. Emulation of PFC
semantics is out of reach anyway (no hardware pause generation/response, no
per-priority queues, no headroom/watchdog), so the GNS3 documentation will
state PFC as unsupported on kernel links rather than pretending otherwise.

### Goal

A kernel-datapath link (and every other uBridge bridge) carries link-local
frames exactly like the cable it emulates: STP, LACP, EAPOL, LLDP and the
remaining reserved addresses flow; PAUSE/PFC is documented as impossible.

---

## A. The requested change

### A.1 One step in `br_enslave_if()` (`hypervisor_brctl.c:251`)

After the port is enslaved (step 1) — and using the existing u16 port-attribute
helper — set the link-local forwarding mask:

```c
/* Step 3 – link-local transparency.  A Linux bridge stands in for a cable
 * here: LACP/LLDP/EAPOL/STP must cross it.  The kernel restricts the
 * *bridge-level* mask to bits 3..15 (BR_GROUPFWD_RESTRICTED), so LACP is
 * only reachable per port.  0xfffd = every reserved address except MAC
 * PAUSE (bit 1), which the kernel refuses and hard-drops anyway.
 * Best-effort: kernels before 4.15 have no such port attribute, and the
 * cable simply keeps today's behaviour there. */
if (br_set_port_attr_u16(bridge, port, IFLA_BRPORT_GROUP_FWD_MASK,
                         LINK_LOCAL_FWD_MASK) < 0)
    fprintf(stderr, "ubridge: %s: link-local forwarding mask not set\n", port);
```

with

```c
/* bit 0 STP (harmless: already forwarded while STP is off), bit 2 LACP,
 * bit 3 802.1X EAPOL, bit 14 LLDP; bit 1 MAC PAUSE must stay clear or the
 * kernel rejects the whole value with EINVAL. */
#define LINK_LOCAL_FWD_MASK 0xfffdu
```

`br_set_port_attr_u16()` (`hypervisor_brctl.c:811`) already does everything
needed: it checks membership via `br_check_master()`, builds the
`IFLA_PROTINFO` nested attribute on `AF_BRIDGE`/`RTM_SETLINK`, and — critically
— encodes the value as **2 bytes**, which is what the kernel's port policy
requires (`NLA_U16`); a 1-byte payload is rejected with `-ERANGE` (the same
trap documented in that helper's comment for `IFLA_BRPORT_PRIORITY`).

### A.2 Why in `br_enslave_if()` rather than in any single caller

* **Every** enslavement in uBridge funnels through this helper — per-link
  bridges, the Ethernet switch's own ports, peers absorbed into a switch
  bridge, cascades, pnet/Cloud bridges. One hook covers all of them, and
  covers future callers too.
* gns3-server **cannot** do it itself: the packaged service runs unprivileged
  (`init/gns3.service.systemd`: `User=gns3`) and `CAP_NET_ADMIN` is carried by
  the uBridge binary (`base_manager.py:_has_privileged_access()`). A
  server-side `ip link set … type bridge_slave …` is not possible in the
  supported deployment.
* Doing it at addif time also means ports that are re-attached after a node
  restart (the server re-pushes NIOs) are re-covered without extra logic.

### A.3 Alternative interface, if the project prefers explicit policy

If uBridge would rather keep this policy out of `addif`, the equivalent
explicit command is:

```
brctl setportgroupfwd <bridge> <port> <mask>      (3 args)
```

implemented as a thin wrapper over `br_set_port_attr_u16(..., (unsigned
short)mask)` and registered next to `setportprio` in the command table
(`hypervisor_brctl.c:2049`). In that case gns3-server will call it at its
five `brctl addif` sites and gate it on a probe of the running build. The
implicit form is preferred by gns3-server because it needs no server change
and cannot be forgotten at a new call site.

---

## B. Requirements (normative)

* **R1** After a successful `brctl addif <bridge> <port>`, the port carries
  `group_fwd_mask = 0xfffd` (`LINK_LOCAL_FWD_MASK`).
* **R2** The value must **exclude bit 1 (MAC PAUSE)**. `0xfffe`/`0xffff` are
  rejected by the kernel with `EINVAL` and would silently lose the whole
  mask — do not use them.
* **R3** The attribute payload must be encoded as u16 (`br_set_port_attr_u16`).
  A u8 payload fails `validate_nla` with `-ERANGE` on kernels that enforce the
  policy strictly.
* **R4** **Best-effort**: a failed mask write must never fail the `addif`
  (kernels < 4.15 have no per-port attribute; unusual deployments may lack
  `CAP_NET_ADMIN`). Reply to `addif` is unchanged; the failure is logged to
  stderr.
* **R5** Ordering: set the mask after the port is enslaved (both
  `br_check_master()` and the kernel's `IFLA_PROTINFO` handling require
  membership). The step-2 "bring the port up" may run before or after; both
  work.
* **R6** Idempotent: re-`addif` of an already-enslaved port must succeed and
  keep the mask set (gns3-server re-attaches links on node start).
* **R7** Applies uniformly to every bridge/port this helper touches — no
  per-bridge or per-caller switch (a real switch terminates link-local frames,
  but GNS3's Ethernet switch node is used as a transparent segment, so
  forwarding is the wanted behaviour there too).
* **R8** Version: bump the reported version so gns3-server can raise its
  minimum (the server already gates on `ubridge version X.Y.Z`,
  `compute/ubridge/hypervisor.py:_check_ubridge_version`, currently ≥ 1.2.3).
* **R9** Document the PAUSE/PFC exclusion in uBridge's help/docs, so the gap
  is not rediscovered as a bug.

---

## C. Implementation notes

* `IFLA_BRPORT_GROUP_FWD_MASK` is defined in `include/uapi/linux/if_link.h`
  (Linux ≥ 4.15); guard the build on its presence if uBridge must compile
  against older headers — behavior on such kernels is "no mask", which R4
  already tolerates.
* The kernel's `br_set_group_fwd_mask()` (port variant) validates against
  `BR_GROUPFWD_MACPAUSE`; there is also a follow-up fix
  (`16c42db48522`, "bridge: check for attempt to forward STP PDU's with STP
  enabled") that moves STP validation into the setter — bit 0 is harmless for
  our case because we never enable STP on these bridges.
* No interaction with existing commands: `brctl setgroupfwd` (bridge-level)
  stays as is and is unused by gns3-server; `hairpin`/`isolated`/`setportstate`
  continue to use their own attributes through the same helper family.

---

## D. Reply contract & error behavior

`addif` replies (`HSC_INFO_OK` / `HSC_ERR_*`) are unchanged. The mask write
does not produce its own reply and does not alter the addif verdict; on
failure it writes one line to stderr (§A.1). No new error codes.

---

## E. Test requirements

The uBridge test suite already drives bridge/veth setups; the following cases
pin the contract (all are cheap AF_PACKET probes — send a frame with a given
destination MAC into port A, observe whether it arrives on port B, using
`PACKET_OUTGOING` filtering so a port's own transmissions do not count):

* **T1 transparency**: with two veths in one bridge created via `brctl`:
  `01:00:5e:00:00:01` forwarded, `01:80:c2:00:00:0e` (LLDP) forwarded,
  `01:80:c2:00:00:02` (LACP) forwarded, `01:80:c2:00:00:00` (STP) forwarded,
  `01:80:c2:00:00:01` (PAUSE) **not** forwarded.
* **T2 ingress semantics**: mask on the egress port only → LACP not forwarded
  (documents why every port is set; regression guard against "set it once").
* **T3 best-effort**: force the mask write to fail (fault-injection hook or an
  invalid attribute id) and assert `addif` still replies `HSC_INFO_OK`.
* **T4 idempotency**: `addif` twice → both succeed, mask still `0xfffd`.
* **T5 value boundary** (optional, documents R2): a direct write of `0xfffe`
  through the port setter fails with `EINVAL`.

---

## gns3-server alignment (informational — not uBridge scope)

* **No server change is required** for the behavior: all five server-side
  enslavements (`compute/kernel_datapath.py:165`,
  `compute/builtin/nodes/ethernet_switch.py:399,518`,
  `compute/builtin/nodes/cloud.py:377`, and anything added later) go through
  `brctl addif`.
* If R8's version bump lands, gns3-server can raise
  `_check_ubridge_version`'s minimum so that a compute that cannot deliver
  the behavior is reported instead of silently degrading.
* GNS3 documentation will state the resulting matrix for kernel links:
  LLDP/DCBX ✅, LACP ✅, 802.1X ✅, STP ✅, **PAUSE/PFC ❌** (kernel-level,
  not fixable by mask).
* The planned VXLAN datapath inherits the same story: the vxlan device is a
  bridge port, so the same per-port mask applies; PAUSE/PFC stays out of
  reach there too. That must be decided before VXLAN ships, because today's
  cross-compute relay links *do* carry PFC and would silently regress.

## Roadmap note

If PFC emulation ever becomes a hard requirement, the only paths are a
patched kernel (`case 0x01`), a tc/eBPF ingress redirect on the anchor, or a
userspace AF_PACKET pass-through in uBridge (packet sockets see these frames
before the bridge drops them). None of these is part of this spec.

## References

* Kernel: `net/bridge/br_input.c` (`br_handle_frame`, the link-local switch),
  `net/bridge/br_private.h` (`BR_GROUPFWD_*`, `BR_GROUPFWD_RESTRICTED`).
* Per-port mask: commit
  [`5af48b59f35c`](https://github.com/Freescale/linux-fslc/commit/5af48b59f35cf712793badabe1a574a0d0ce3bd3)
  ("net: bridge: add per-port group_fwd_mask with less restrictions");
  [patchwork entry](https://patchwork.ozlabs.org/project/netdev/patch/1506517964-17479-1-git-send-email-nikolay@cumulusnetworks.com/).
* Measurements: stock mainline 7.2.6-1-default, two veth ports in one Linux
  bridge, AF_PACKET probes (2026-10).
