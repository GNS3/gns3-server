<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> Frozen requirements spec for the **uBridge** project. Status: **delivered**
> (uBridge `e2e3155` — `link l2only` plus the creators that apply it;
> `fb72758` — the fifth creator: the TAP `bridge add_nio_tap` creates for a
> free name) and verified from the server side: anchors and per-link bridges
> report `addrgenmode none`, `ip -4/-6 addr` are empty, and an idle anchor is
> silent once the one-shot membership burst of §0 has settled.
>
> **Residual, accepted (measured after delivery):** enslaving a port still
> makes the *bridge device* announce its multicast memberships — one IGMPv3
> plus one or two MLDv2 reports in the first second — which floods into the
> emulated segment. It is outside this command's reach by design (no addresses
> are involved, and IPv4 has no per-device IGMP off switch); see §0.
>
> Scope guard: no wire format, no command grammar change to existing
> commands — this adds one command and one internal step in four creators.

# L2-only host anchor devices (`link l2only`)

## 0. Background & scope

### What an anchor is

The host-side device that carries a node's adapter in the root namespace:
the veth host end of a Docker adapter (`gv…`, created by `docker create_veth`),
the persistent TAP of a QEMU adapter (`gq…`, created by `tap create`), and the
per-link kernel bridge those anchors are enslaved to (`brctl create`). Links
attach *to* these devices (kernel bridge port or uBridge relay endpoint); the
devices themselves are the only thing uBridge creates on the host's behalf.

### The problem (measured)

A host-side anchor that is UP gets an IPv6 link-local address from the kernel
automatically — no user-space actor involved — and with it the kernel emits its
own traffic on that device:

- a freshly created persistent TAP, brought UP: **6 frames in 2 s** of MLD
  reports (`33:33:00:00:00:16`, `33:33:00:00:00:fb`) and DAD neighbor
  solicitations (`33:33:ff:…`, ICMPv6 next-header 0/17/58), all sourced from the
  device's own link-local address;
- production: the Docker veth host end `gv6ee8d537e1p0` carries
  `fe80::5c30:e8ff:fe00:5d8d/64` (`disable_ipv6=0`), and the per-link bridge
  `gns30dbb78c5718` carries `fe80::f0d9:94ff:feac:e42b/64`.

Consequences inside an emulated topology:

- on a **kernel-datapath** link the bridge floods those frames into the emulated
  segment; on a **relay** link uBridge relays them to the peer compute;
- they land in captures and marker pcaps, so "idle link" is not quiet;
- the host **answers** neighbor solicitations for its own link-local address, so
  an emulated IPv6 router can form a real adjacency with the host — a phantom
  neighbour inside the emulated network.

IPv4 needs no equivalent knob: nothing self-provisions an IPv4 address, and the
invariant we keep is *no addresses at all* (measured: `ip -4 addr` is empty on
every anchor and per-link bridge on the deployment above, with NetworkManager
reporting them `unmanaged`). IPv6 is the only protocol that lights itself up.

### The residual this command does not remove (measured after delivery)

With `l2only` in place (anchors and bridges report `addrgenmode none`, no
addresses), **enslaving a port still makes the bridge device speak once** —
the kernel announces the multicast memberships the enslavement brings to the
bridge:

```
+0.00 s   90 B   IPv6   MLDv2 report   dst 33:33:00:00:00:16  (ICMPv6 143)
+0.09 s   54 B   IPv4   IGMPv3 report  dst 01:00:5e:00:00:16  0.0.0.0 → 224.0.0.22
+0.73 s   90 B   IPv6   MLDv2 report   dst 33:33:00:00:00:16
```

(Scratch tap pair + per-link bridge on the test host, unprivileged; source MAC
= the bridge's. A 10 s window contains exactly those three frames, then silence.
The same burst appears through the server: one 90 B IPv6 frame inside a 2 s
window right after a link is created.)

It is outside `l2only`'s reach by design: no addresses are involved (the report
sources are `::` and `0.0.0.0`), and IPv4 has no per-device "no IGMP" knob to
set. **Decision: accepted and documented, not suppressed** — it is standard L2
control traffic, one-shot per link creation or port change, and it stops. The
acceptance test in §E.2 therefore measures after a settle window. Suppressing
it (e.g. `disable_ipv6` on the bridge before enslaving, for the MLD half) would
be a new, separate requirement and has not been asked for.

### NetworkManager releases managed TAPs from bridges (measured)

On hosts where NetworkManager manages the data-plane TAPs — it claims uBridge-created tun/tap devices on many desktops (`nmcli device` shows them as `disconnected` before NM's state machine has assumed them, `connected (externally)` after) — NM can **release a tap from its bridge** some 60-70 ms after enslavement, while the port is in that not-yet-assumed state. Measured with a minimal harness (one uBridge, one fresh tap, one bridge, an `addif`/`delif` loop, no server): ~50 % of re-enslavements lose the port, the freed device stays administratively **up** with the bridge's promiscuity/allmulti cleared, and no GNS3 process sends anything — gns3-server and uBridge log nothing, and the server's attachment bookkeeping stays intact. The *first* enslavement of a newly created tap was stable in every run; the hazard is a **re-enslavement** (link delete + recreate, a port re-join after a peer restart) before NM assumes the device — on the same tap, `nmcli device set <tap> managed no` flips the failure rate from 20/40 to 0/40, and re-managing it restores 20/40.

Consequence for an affected link: the port silently leaves the bridge (frames drop) while the API stays green — the next NIO update re-heals it, because the switch's `_kernel_update` re-checks `brif` membership, but nothing forces one. Docker's veth host ends are not NM-managed and never showed the failure; every TAP anchor family is exposed (Dynamips `gd`, QEMU `gq`, IOU `gi`, IOL `gx`, and switch-absorbed anchors). Host-side remedy: `nmcli device set <tap> managed no` (runtime, per device), or NM's `unmanaged-devices` configuration keyed on the anchor name prefixes; the e2e harness takes the anchors it re-enslaves out of NM's hands (`harness.unmanage_from_networkmanager`).

### Goal

Every host-side device uBridge creates for the data plane is **pure L2**: no
IPv4 address, no IPv6 address, and no IPv6 stack activity on that device.

Explicitly **not** in scope:

- the guest/container side (the peer veth end inside a container netns keeps its
  normal IPv6 behaviour);
- global sysctls and any change outside the named interface;
- `brctl addip`-style L3 use of a bridge (cloud / Ethernet-switch paths) — those
  devices are meant to have addresses and are not data-plane anchors.

## A. New command: `link l2only <iface> [on|off]`

Belongs to the `link` module (per-interface operations: `link set`, `link veth`,
`link addr`, `link delete`).

| Arg | Description |
|-----|-------------|
| `<iface>` | An **existing** device. A missing name must fail (`208/ENODEV`), never create a transient device — mirror the `tap` module's `tap_require_existing` reasoning. |
| `on` / `off` | Default `on`. `on` = suppress IPv6 address generation and stack activity on the device; `off` = restore the kernel default. |

Semantics of `on`: after the call the kernel has assigned **no** IPv6
link-local address to the device, and the device's `addrgenmode` reports `none`
(`IFLA_INET6_ADDR_GEN_MODE = IN6_ADDR_GEN_MODE_NONE`), so no DAD, MLD or RS is
generated from it. If an address already exists it is removed as part of the
call (an anchor that was created and brought up before this command must end up
clean, not just "no new addresses from now on").

Replies:

```
link l2only gq1234abcd e0
100-L2-only set on gq1234abcd e0
link l2only gq1234abcd e0 on
100-L2-only set on gq1234abcd e0          # idempotent, same reply
link l2only gq1234abcd e0 off
100-L2-only cleared on gq1234abcd e0
```

The success reply is emitted only after a read-back (`RTM_GETLINK` +
`IFLA_AF_SPEC` → `IFLA_INET6_ADDR_GEN_MODE`) confirms the device state, so a
caller may treat `100` as verified rather than requested.

## B. Where it must be applied

The creators apply it themselves — gns3-server never issues `link l2only`
directly, and a caller cannot forget it:

| Creator | Device hardened | Notes |
|---|---|---|
| `tap create <name>` | the persistent TAP | before the success reply; the device already exists (TUNSETPERSIST) |
| `docker create_veth <host> <guest>` | the **host** end only | the guest end moves into a container netns and is deliberately untouched |
| `link veth <name> <peer>` | both ends | both ends are host-side |
| `brctl create <bridge>` | the bridge device itself | the fabric the anchors are enslaved to; the bridge's own link-local floods to every port |
| `bridge add_nio_tap <br> <name>` | the TAP it **creates** (name free) | by-name `TUNSETIFF` creates a transient device when the name is free — cloud's bridge interfaces, and the relay swap's create-if-missing path. Hardened at creation; an attach to an existing device is left untouched (the caller may name a user-owned TAP that has addresses). |

Rule for future creators: any command that creates a host-side device for the
data plane hardens it, and the acceptance checks in §E apply to it.

An **attach** is not a creation: `bridge add_nio_tap` (and every other open
of a TAP that already exists) must leave that device's addresses alone. The
transient TAP `bridge add_nio_tap` creates for a free name is a creation and
is hardened like the rest — best-effort, before the NIO is handed back.

## C. Implementation notes (netlink, not `/proc`)

- Use `RTM_SETLINK` with `IFLA_AF_SPEC{ AF_INET6, IFLA_INET6_ADDR_GEN_MODE =
  IN6_ADDR_GEN_MODE_NONE }` — this is what `ip link set dev X addrgenmode none`
  does. Removing an already-assigned link-local is `RTM_DELADDR` on that
  address (or letting the kernel drop it once generation is off; verify the end
  state either way).
- Optionally also set the nested `IFLA_INET6_CONF` attributes
  (`DEVCONF_DISABLE_IPV6 = 1`, `DEVCONF_ACCEPT_RA = 0`) when the running kernel
  accepts writes for them. The addr-gen-mode attribute alone already removes the
  address, and without an address there is no DAD/MLD/RS.
- Do **not** write `/proc/sys/net/ipv6/conf/<if>/disable_ipv6`. The sysctl files
  are root-owned mode 0644, so a setcap'd, non-root uBridge can be refused by
  the DAC check despite holding `CAP_NET_ADMIN`. The netlink route has no such
  problem.
- Failure handling: `EOPNOTSUPP` / `EINVAL` from an old kernel without the
  attribute must be **non-fatal** (log, continue) so device creation never fails
  because of this hardening; `ENODEV` and any other error are real and reported.

## D. Reply contract & error codes

| Code | Meaning |
|------|---------|
| `100` | OK — device verified L2-only (or verified restored for `off`) |
| `203` | Bad number of parameters |
| `204` | Invalid parameter (`on`/`off` expected) |
| `208` | Object not found (`ENODEV`): no such device |
| `206` | Unable to set (netlink error other than EOPNOTSUPP/EINVAL) |

## E. Test requirements

1. **No addresses.** After each creator: `ip -6 addr show dev <dev>` is empty
   (in particular no `fe80::`) and `ip -4 addr show dev <dev>` is empty; the
   same for the bridge created by `brctl create`.
2. **Idle silence, after the settle window.** Let the last port enslavement
   settle (≥ 2 s — that burst is expected, see §0), then with the device UP and
   in its normal role (TAP with an open fd / veth with its peer up / bridge with
   two attached ports) nothing appears on it for 5 s — measured from the peer
   end, or via `capture start_kernel <dev> <pcap>` while idle with the pcap
   asserted empty. Baseline before this work: 6 frames / 2 s, continuous.
3. **Idempotency & revert.** `on` twice → `100` both times, state unchanged;
   `off` restores the kernel default (link-local returns after the device is
   cycled down/up).
4. **No transient device.** `link l2only nosuchif0` → `208`, and no interface is
   created (check `ip -o link`).
5. **Far side untouched.** Inside the container / VM the normal IPv6 link-local
   still exists — nothing in this change reaches the peer.
6. **Non-fatal on old kernels.** Simulated by testing on a kernel without the
   attribute: the creators still succeed, and §E.1 is then expected to fail with
   the device left in the default state.

## gns3-server alignment (informational — not uBridge scope)

- **Call sites**: the creators harden the devices; the server issues no
  `link l2only` itself, and no NIO/JSON schema, filter or MCP tool
  description changes. This is host-side hygiene only.
- **The fifth creator was found by these servers' e2e assertions**: on a
  build predating `fb72758`, the Ethernet switch's relay port TAPs
  (`gns3{id}-N`, created implicitly by `bridge add_nio_tap`) carried a live
  `fe80::` — the §E.1 assertion failed on exactly that device, live. The
  close is uBridge-side (§B table row 5): the transient TAP is hardened at
  creation, attaches stay untouched. The server side needed no change for
  it — the assertion alone caught it, and it now guards the fixed build.
- **e2e assertions** (landed in `tests/e2e/harness.py`, asserted by the
  kernel-datapath suites alongside the existing capture/marker/filter checks):
  - anchors and per-link bridges have no IPv4/IPv6 addresses, addrgenmode
    `none` (`assert_pure_l2`, §E.1) — on the kernel scenarios' anchors and
    bridges, and on relay-mode anchors/switch TAPs alike (the hardening is a
    creation-time property, not a datapath one). The switch relay-TAP
    assertion is what exercises the fifth creator end-to-end (the same
    uBridge creation path cloud's transient TAPs take);
  - an idle link stays silent for 5 s after the settle window
    (`assert_idle_silence`, §E.2) — measured with the guests silenced (the
    IOS consoles' interfaces shut, the Docker guests' links down, all four
    cascade routers shut) over the anchors, the per-link bridge and the
    switch bridges, in every kernel scenario: Dynamips, Docker, QEMU, IOU,
    the IOL container, the switch fast path and the switch cascade. That
    covers each creation
    path — `tap create`, `docker create_veth` (plus the server-side
    harden-after-create on the cascade's race-loser end), `bridge
    add_nio_tap` and the `brctl` switch bridges (whose multicast snooping
    is off precisely so the bridge role can reach silence);
  - a silent-failure guard found while validating this spec: after attach, every
    bridge port reports `brport/state == 3` (forwarding) (`assert_forwarding`).
    A bridge device left DOWN keeps its ports `DISABLED` (`state == 0`) and
    forwards nothing — with no error anywhere, so the assertion is the only
    signal.
- **Rollout**: with a uBridge that lacks the command the anchors keep today's
  behaviour (noise present). The e2e assertions skip when `link l2only` answers
  `202-Unknown command` (`harness.l2only_supported()` probes a throwaway
  uBridge once), mirroring the existing tc-capability degradation. A build
  that has the command but predates `fb72758` fails the switch relay-TAP
  assertion instead of skipping: the gap is exactly what it exists to catch.
