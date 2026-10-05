<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.

# NetworkManager Releases Enslaved TAP Anchors from Their Bridge (Silent Link Death)

## Bug Report

**Date**: 2026-10-05 (root-caused; the same signature first hit on 2026-10-01 during the Ethernet-switch kernel-datapath development)
**Severity**: High on affected hosts (one link dies silently — API and UI stay green; ~50 % per re-enslavement while NetworkManager has not yet assumed the TAP; environment-dependent and intermittent)
**Status**: **Root-caused; host-side fix verified.** The NetworkManager declaration (`unmanaged-devices`) takes the reproducing loop from 19-20/40 to 0/40 and lets the e2e scenario pass with all test-side workarounds disabled. Test-side best-effort hardening is shipped (`harness.unmanage_from_networkmanager`); a product-side guard remains an open decision.
**Component**: Host environment — NetworkManager × uBridge-created TAP anchors. No GNS3 code path performs the detaching operation: gns3-server and uBridge log nothing and their bookkeeping stays intact.

## Symptoms

On a kernel-datapath link, after a **re-enslavement of the TAP anchor** — a link delete + recreate, a port re-join after a peer restart — the link may die: ping 0 %, routing protocols never form — while every API/UI surface reports health (`kernel_datapath: true`, no error, no log). The node, the emulated router and the anchor device itself keep running; only the bridge membership is gone.

Self-heal exists but nothing forces it: any subsequent NIO update re-checks `/sys/class/net/<bridge>/brif/<anchor>` and re-attaches (`EthernetSwitch.update_nio`'s "not joined" branch, and the equivalent attach path per node type), which is why the state heals on the next filter change, suspend toggle or peer restart. The *first* enslavement of a freshly created TAP is stable in every observation; the hazard is re-enslavement before NetworkManager has assumed the device (a window of minutes), at ~50 % per attempt.

## Forensic signatures (what the corpse looks like)

- `/sys/class/net/<bridge>/brif/<anchor>` missing, `/sys/class/net/<anchor>/brport/` gone — the port was released, not the device destroyed: **ifindex unchanged**, `ip -d link show` reports no master.
- Flags drop `IFF_PROMISC|IFF_ALLMULTI` (0x300, set by the kernel bridge on enslavement): as seen with a 50 Hz brif sampler, `fl 0x1303 → 0x1003` while administrative UP is kept.
- The release lands **58-87 ms after the join** — after the attach API has already returned success, so `wait_until`-style checks see the join and the next traffic sample sees the blackhole.
- No `brctl delif` (or any netlink write) from any GNS3 process; server-side registrations (`_kernel_ports`, NIO state) are untouched; uBridge logs stay clean.
- `nmcli device status` shows the anchor as managed by NetworkManager: `disconnected` before it assumes the device, `connected (externally)` after.

## Root Cause (NetworkManager side, source-level)

On hosts where NetworkManager manages the anchors — it claims uBridge-created tun/tap devices by default (`nmcli device` then shows them managed) — NM's device state machine resolves the fresh enslavement in its own favour while the device is in its pre-assumption window:

1. An **external enslavement** triggers an assumption recheck — NetworkManager commit `a6ceb382e9` ("device: connect slave assumption recheck on external enslavement") exists precisely for `ip link set <dev> master <bridge>` performed by someone else.
2. The recheck activates (assumes) the device, and activation enforces that **a connection which does not declare a master must not keep its kernel master**: the slave is force-released, reason `NM_DEVICE_STATE_REASON_CONNECTION_ASSUMED` — NetworkManager commit `ec12912908` ("device: enforce the absence of a master during activation"). This is the detaching operation; it runs several asynchronous state-machine steps after the enslavement, which is the 60-80 ms latency.
3. Once the device is assumed (`connected (externally)`), later external enslavements take the opposite path: **external changes must not touch the device** — NetworkManager commit `3127fb0d17` ("device: don't let external changes cause a release of the slave", `configure = FALSE`, "let the device be"). The model is updated; the kernel is left alone. This is why assumed taps were stable across 14 re-enslavements in the field, and why the hazard window ends at assumption.

Both processes' worlds are mutually exclusive here: NM requires "no master during activation", the datapath requires "enslaved to the switch/per-link bridge" — there is no configuration in which both hold. The sanctioned resolution is a jurisdiction declaration (mark the devices unmanaged), not a race.

Docker veth host ends are not NM-managed (and the veth naming/type heuristics historically keep NM away — see History), so only the TAP anchor families are affected: `gd` (Dynamips), `gq` (QEMU), `gi` (IOU), `gx` (IOL runner containers), and switch-absorbed anchors.

## Reproduction (minimal, gns3-server not involved)

Self-contained harness: one uBridge (`ubridge -U <sock>`), one fresh TAP (`tap create`), one kernel bridge (`brctl create` + `vlanfiltering on`), then loop { `link set <tap> up`, `brctl addif <br> <tap>`, 200 ms of ~1 kHz membership sampling, `brctl delif`, `link set down` }. Measured on an affected host (same code, five baseline runs, then single-variable A/B on one tap):

| Condition | Releases / 40 re-enslavements |
|---|---|
| NM-managed (default) | 19, 20, 19, 20, 20 |
| `nmcli device set <tap> managed no` | **0** |
| re-managed (`nmcli device set <tap> managed yes`) | 20 |

e2e-level reproduction: `tests/e2e/test_ethernet_switch_kernel_datapath.py::test_ethernet_switch_kernel_fast_path` fails at its link delete/recreate step (`wait_ping` after the anchor re-join) roughly half of fresh runs on an NM host — it failed twice consecutively on 2026-10-05 during the 3.1 rebase validation before the fix.

## Fix

Three layers, of which the first is the verified root fix:

1. **Host declaration** — `/etc/NetworkManager/conf.d/99-gns3-datapath.conf`:

   ```ini
   [keyfile]
   unmanaged-devices=interface-name:gd*;interface-name:gq*;interface-name:gi*;interface-name:gx*;interface-name:gv*;interface-name:gns3*
   ```

   then `systemctl reload NetworkManager`. Devices matching are unmanaged from birth (also future ones and after re-creations); hosts without NM treat the file as inert. Verified on the affected host: minimal loop **0/40**, and the e2e scenario passes with the test-side workaround disabled (pure host config). This belongs in installers/documentation, not in the server (no root; and the server must not reconfigure the host's NM).

2. **Test-side best effort** — `harness.unmanage_from_networkmanager(*taps)` runs `nmcli device set <tap> managed no` where nmcli exists (no-op otherwise); kernel-datapath scenarios that re-enslave anchors call it after their nodes have booted. This keeps the e2e deterministic on un-declared hosts.

3. **Product-side guard** — open decision: a bounded post-attach re-check (~250 ms) that re-attaches once and warns (naming NetworkManager), a warn-only variant, or nothing (documentation only). Until decided, an undeclared host relies on the existing heal-on-next-update path.

## Scope

- Affected: Linux hosts where NetworkManager manages the TAPs — desktop-native `gns3server` deployments (the most common GNS3 form factor for Linux users). Every TAP anchor family, the switch fast path and per-link kernel links alike.
- Not affected: the GNS3 VM (its Ubuntu-server stack is netplan/systemd-networkd, no NM — verified against the gns3-vm repository), hosts without NM, Docker veth anchors, relay links, cross-compute links (relay by default).
- Blast radius of one occurrence: exactly one link, silently dead; no incorrect data, but it can mislead an experiment's conclusions (e.g. "this protocol never converges here") and it mimics the project's own "API green, data plane dead" bug class — during the rebase validation it was triaged as a regression until the timing signature (join, then +60 ms release with no command) identified it as environmental.

## History

- **2026-10-01**: the same signature first hit during the Ethernet-switch development, described then as "an anchor occasionally losing its bridge membership right after a `ports_mapping` update"; reproduced with QEMU, IOU and Dynamips peers (all TAPs) and never with Docker veths; the then-unknown cause was worked around by making VLAN reconfiguration in-place (no re-enslavement) and the failure mode was assumed gone "by construction". See `docs/features/ethernet-switch-kernel-datapath.md`.
- **2016**: the same NM-vs-GNS3 jurisdiction class hit Docker veths — NM configured them like plain NICs and a container DHCP server hijacked the host's default route (issue #440, closed). Upstream worked around it by renaming `gns3-veth…` to `veth-gns3-…`, the commit message reading "the name create different behavior with network manager" (`59c1e125d`). NM's management heuristics even depend on interface names — the rename moved the veths into NM's ignored namespace.
- **2026-10-05**: root-caused with the minimal harness and the single-variable A/B; host fix applied and verified; test-side hardening shipped; full write-up (this document).

## Related

- NetworkManager commits: [`a6ceb382e9`](https://codetest.hyprland.org/fdo-mirrors/NetworkManager/commit/a6ceb382e90a9ebc278e380a3b204ad8c2c543c4), [`ec12912908`](http://git.baserock.org/cgit/delta/NetworkManager.git/commit/src/devices/nm-device.c?id=ec12912908d739459ff3913917e9937500345c2a), [`3127fb0d17`](https://codetest.hyprland.org/fdo-mirrors/NetworkManager/commit/3127fb0d17bff0b250218c7bf82b4335b5290825).
- GNS3 issue [#440](https://github.com/GNS3/gns3-server/issues/440) and commit `59c1e125d` (veth rename).
- `docs/design/ubridge-l2-anchor-spec.md` — "NetworkManager releases managed TAPs from bridges" subsection (short form).
- `docs/features/ethernet-switch-kernel-datapath.md` — the corrected account of the 2026-10-01 incident.
- `tests/e2e/harness.py` — `unmanage_from_networkmanager`.
