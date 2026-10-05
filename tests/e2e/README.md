<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# Live end-to-end tests

Tests under this directory run against a **real** server: real uBridge, real kernel interfaces (privileged), real emulator binaries and real images. They verify what unit tests cannot — that a datapath actually forwards traffic, that kernel bridges actually enslave anchors, that tc impairments actually shape packets. They are marked `e2e` and **excluded from normal test runs** (see `tests/pytest.ini`) — and from CI, which runs the unit suite only. Run them explicitly, on a real machine:

```bash
pytest -m e2e tests/e2e -s            # -s shows the progress prints
pytest -m e2e tests/e2e -k dynamips   # one scenario
```

Two run modes, chosen per test through `harness.live_server(kernel=...)`:

* **Target an existing server** — set `GNS3_E2E_URL` (e.g. `http://127.0.0.1:3080/v3`, plus `GNS3_E2E_USER`/`GNS3_E2E_PASSWORD`, default admin/admin). The server must already be configured for the datapath under test (kernel links need `enable_kernel_datapath = True`).
* **Isolated instance** (the default) — the harness starts its own server process on a free port with its own config directory (the controller DB and every path follow the config), so nothing on the machine is touched besides the kernel devices the scenarios themselves create. It needs `ubridge`, `dynamips` and an images directory (`GNS3_E2E_IMAGES`, default `~/GNS3/images`) available locally — the IOU scenario takes its L3 image from that directory's `IOU` subfolder, the QEMU scenario its L3 IOSv qcow2 from the `QEMU` subfolder; the Docker scenarios additionally need the Docker daemon the server talks to.

Either way each test creates its own project and deletes it again. Set `GNS3_E2E_KEEP=1` to keep the project (and a started instance) on failure and print where to look at it.

## Host requirements

Beyond a Linux kernel with the datapath features (bridges, veth/TAP devices, tc netem/clsact/cls_bpf, the eBPF stateful classifier — each probed where it matters, and the affected assertions skip on kernels or uBridge builds without them):

* **uBridge** with `cap_net_admin,cap_net_raw,cap_bpf` on `PATH` — the normal server install.
* **`tc` (iproute2)** for the filter scenarios: their qdisc and classifier assertions read it from `PATH`. Without it those assertions cannot run.
* **A Docker daemon** for the Docker scenarios (the harness's own guest driver talks to the same daemon as the server; socket override: `GNS3_E2E_DOCKER_SOCKET`).
* **A C compiler that can link statically** (`cc -static`) for the raw-frame probe of the link-local scenario; without it that probe skips.
* **Emulator images** — see the matrix below.

## Test images

Every scenario picks its image from the images directory (`GNS3_E2E_IMAGES`, default `~/GNS3/images`; a missing directory skips everything image-based). The first preferred name wins when present; otherwise the fallback pattern scans the directory. A missing image **skips** the scenario — never a false failure.

| Scenario | Where | Preferred file(s) | Fallback |
|---|---|---|---|
| Dynamips (c7200) | images dir root | — | any file name starting with `c7200` |
| IOU | `IOU/` | `x86_64_crb_linux-adventerprisek9-ms.iol`, then `l3-adventerprisek9-ms-17.15.01.bin` | any name containing `adventerprisek9` and **not** `l2` |
| QEMU (IOSv) | `QEMU/` | `vios-adventerprisek9-m.spa.159-3.m12.qcow2` | any `vios` `.qcow2` without `l2` |
| IOL runner containers | Docker daemon | — | any locally loaded `iol-xe/iol-xe:*` image (any tag) |
| Docker scenarios | Docker daemon | `alpine:3` pinned at digest `sha256:28bd5fe8b56d…` | none — cached, else pulled, else skip (below) |

Notes on the rows:

* The Dynamips image must be a bootable c7200 IOS that supports the `PA-2FE-TX` module; the idle-PC story is described below.
* The IOU scenario needs an **L3** image — the `l2` exclusion is deliberate (the scenarios exercise the classic 2×4 Ethernet port model; L2 IOU images have their own issues). The isolated instance has the IOU license check disabled, so no `iourc` is needed.
* The IOL runner scenario stages the repository's `gns3server/configs/iol-xe-base.txt` as the base config so Cisco's iol-runner boots past its setup dialog.
* The preferred names are the exact builds the suites were live-verified against (Cisco-licensed artifacts — they cannot ship with the repo, hence the fallbacks). A fallback-selected build is tolerated but is an unverified combination.

The dynamips scenarios give their routers an idle-PC: detected once per image through the controller's `auto_idlepc` (a throwaway project and a real CPU-usage measurement — the GUI's idle-PC finder path) and cached in `~/.cache/gns3-e2e/idlepc.json` keyed by the image checksum. Without one, each c7200 burns a **full CPU core** for the whole scenario — the e2e creates raw nodes, so no template supplies a value. Set `GNS3_E2E_IDLEPC` to skip the detection and use the given value (detection failing is never fatal: the routers simply run without one).

`harness.py` holds the shared pieces — REST client, server lifecycle, the IOS console driver, the Docker guest driver (a tiny Docker Engine API client over the daemon socket, plus the digest-pinned image helper), a WebSocket notification collector (a sync facade over `websockets`' sync client for asserting on live notification streams), host-side kernel inspections (bridge membership, tap admin state, tc qdiscs, the L2-anchor spec §E assertions) — so a new node type adds only its own scenario module.

Current scenarios:

* `test_dynamips_kernel_datapath.py` — two real c7200 routers: kernel link (anchors, per-link bridge, netem delay, suspend, capture, delete/re-create, stop/start) plus a serial link staying on the relay, and a negative control on an isolated relay-configured instance.
* `test_ethernet_switch_kernel_datapath.py` — a real Ethernet switch (kernel bridge) between two c7200 routers: deferred joins on boot, VLAN isolation, absorbed-anchor filters/suspend/capture, VPCS peers staying on the relay, and a relay negative control.
* `test_ethernet_switch_cascade.py` — two Ethernet switches cascaded through the link-owned veth pair (`gs<link_id>0/1`, each end enslaved into its own switch's bridge): a dot1q trunk cascade carrying two VLANs at once across two c7200 routers per switch, the symmetric access/trunk mode flip on the cascade ends, two-sided netem (one end per direction), suspend, link delete/re-create (the pair dies with the link, the replacement mints new names), zero residue.
* `test_iol_docker_kernel_datapath.py` — two real iol-xe containers (Cisco CML iol-runner images): kernel link through the port bridge's swappable TAP leg (anchors at start, netem delay, the TAP-anchor classifier spot check for bpf match-drop and the eBPF every-nth mode, suspend, capture, link delete/re-create swap, node stop/start rewiring) and a relay negative control.
* `test_iou_kernel_datapath.py` — two real IOU routers (a real IOU image from the images directory, the real IOS CLI on the server's telnet console): kernel link through the [IOL fabric ↔ TAP] port bridge (same lifecycle as the iol-xe containers) including the TAP-anchor classifier spot check and a filter surviving a node restart, a serial link staying on the relay (serial bays never anchor), and a relay negative control whose filters ride the IOU-specific `iol_bridge add_packet_filter` engine (delay and frequency_drop measured through real traffic, capture and markers on `iol_bridge start_capture` and the port's `mark` filter).
* `test_qemu_kernel_datapath.py` — two real IOSv routers (a real qcow2 image from the images directory's `QEMU` subfolder, linked clone, the real IOS CLI on the server's telnet console): the anchor TAP is QEMU's own netdev (no port bridge in between) — the full kernel lifecycle plus a relay negative control where the anchor carries as the relay's AF_PACKET endpoint. IOSv boots a real IOS: this is the slowest scenario pair (~6½ min kernel, ~5 min relay).
* `test_docker_kernel_datapath.py` — two real Alpine containers (the plain veth datapath): the per-link kernel bridge enslaves exactly the two veth host ends, real ICMP crosses, the filter matrix runs one type at a time (netem core and extensions, cls_bpf match-drop, the eBPF classifier — each measured through real traffic), plus a relay negative control whose own filters (delay, frequency_drop, bpf) really shape the wire as uBridge userspace bridge filters and whose capture and markers ride the relay engine (`bridge start_capture` / the bridge `mark` filter), and a relay→kernel reopen upgrade (the server's datapath choice is flipped across a restart).
* `test_docker_link_local_frames.py` — two real Alpine containers on a kernel link, with a static raw-Ethernet probe built at run time and docker-cp'd in: guest 1 injects frames per destination MAC while guest 2 counts what arrived. Asserts the per-port `brport/group_fwd_mask` reads 0xfffd (applied by `brctl addif`) and the bridge-level mask stays 0; the live matrix: ordinary multicast, STP/RSTP, LACP, EAPOL and LLDP/DCBX cross, MAC PAUSE does not (a documented kernel hard-drop — PFC labs need a relay link); a container stop/start re-applies the mask (the reconnect story). Needs `cc -static` on the host.
* `test_marker_kernel_datapath.py` — two real Alpine containers on a kernel-only link with traffic-insight markers attached to a veth anchor (`marker add_kernel`): `marker.match` signals collected off the dedicated marker WebSocket with their full identity (filter/tag/link_id/node_id/len and the tx/rx direction set of a ping), the main project channel asserted free of matches, BPF and direction enforcement, host pcap exactness, pause/resume silence counting against a still-firing sibling, tag replay (timeline, display filter, link narrowing, window, the 409 gate) and marker delete taking pcap plus signals with it.

The Docker scenarios run a digest-pinned `alpine:3`, so every developer tests the same bytes: a cached copy in the local Docker daemon costs no network, a cache miss pulls through the server's own image-pull route, and with neither cache nor registry the scenario skips (`GNS3_E2E_DOCKER_IMAGE` overrides the reference). Their guests are addressed the way a GNS3 user does it — the node's persistent `/etc/network/interfaces`, which the container's `init.sh` applies at boot — and driven through the Docker daemon socket the server itself uses.

Every kernel scenario also asserts the L2-anchor spec's server-side guarantees (`docs/design/ubridge-l2-anchor-spec.md` §E): anchors and bridges carry no L3 identity (`assert_pure_l2`), joined ports are FORWARDING (`assert_forwarding`), and an idle link with the guests silenced stays silent for 5 s (`assert_idle_silence`) — the guests are the IOS consoles' interfaces shut, the Docker guests' links down, or all four cascade routers silenced, whichever the scenario runs. These skip on a uBridge without `link l2only` (probed once by `harness.l2only_supported()`).

## Host environment notes

* **NetworkManager**: on hosts where NM manages the TAP anchors (many desktop Linux installs), NM can release a freshly (re-)enslaved anchor from its bridge ~60 ms after the join — silently, leaving the API green and the link dead until the next NIO update. The harness takes the anchors out of NM's reach where scenarios re-enslave them (`harness.unmanage_from_networkmanager` — a no-op where `nmcli` is absent), and the permanent host-side fix (an `unmanaged-devices` declaration) plus the full root-cause record live in `docs/bugs/networkmanager-tap-release.md`. A host with NM but without `nmcli` can still see the rare spontaneous release on the first runs.
* **Timing and load**: the traffic assertions of the IOS-based scenarios are three-packet averages over real emulated routers; the RTT bounds are deliberately generous (`harness.FAST_RTT_MS`) but a heavily loaded host can still push a sample over — run the suite on a machine with a few cores to spare. Boot waits (`_boot` timeouts) assume a responsive host too.
* **CI**: these tests do not run in CI (the testing workflow runs the unit suite, with the `e2e` marker deselected). They are a developer/validator tool for real machines.

## Environment variables

* `GNS3_E2E_URL`, `GNS3_E2E_USER`, `GNS3_E2E_PASSWORD` — target an existing server instead of starting an isolated instance (default user/password: admin/admin).
* `GNS3_E2E_KEEP=1` — keep the project (and an isolated instance) on failure and print where to look at it.
* `GNS3_E2E_IMAGES` — the images directory (default `~/GNS3/images`).
* `GNS3_E2E_DOCKER_IMAGE` — override the pinned Docker image entirely (the operator then owns its content).
* `GNS3_E2E_DOCKER_SOCKET` — the Docker daemon socket the harness's guest driver talks to (default `/var/run/docker.sock` — the same daemon the server uses).
* `GNS3_E2E_IDLEPC` — skip idle-PC detection for the Dynamips scenarios and use the given value.
* `GNS3_E2E_DEBUG=1` — run the isolated instance with debug logging (the uBridge command stream lands in its `server.log`).
