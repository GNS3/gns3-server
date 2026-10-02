<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# Live end-to-end tests

Tests under this directory run against a **real** server: real uBridge, real
kernel interfaces (privileged), real emulator binaries and real images. They
verify what unit tests cannot — that a datapath actually forwards traffic,
that kernel bridges actually enslave anchors, that tc impairments actually
shape packets. They are marked `e2e` and **excluded from normal test runs**
(see `tests/pytest.ini`); run them explicitly:

```bash
pytest -m e2e tests/e2e -s            # -s shows the progress prints
pytest -m e2e tests/e2e -k dynamips   # one scenario
```

Two run modes, chosen per test through `harness.live_server(kernel=...)`:

* **Target an existing server** — set `GNS3_E2E_URL` (e.g.
  `http://127.0.0.1:3080/v3`, plus `GNS3_E2E_USER`/`GNS3_E2E_PASSWORD`,
  default admin/admin). The server must already be configured for the
  datapath under test (kernel links need `enable_kernel_datapath = True`).
* **Isolated instance** (the default) — the harness starts its own server
  process on a free port with its own config directory (the controller DB
  and every path follow the config), so nothing on the machine is touched.
  It needs `ubridge`, `dynamips` and an images directory
  (`GNS3_E2E_IMAGES`, default `~/GNS3/images`) available locally — the IOU
  scenario takes its L3 image from that directory's `IOU` subfolder, the
  QEMU scenario its L3 IOSv qcow2 from the `QEMU` subfolder; the Docker
  scenarios additionally need the Docker daemon the server talks to.

Either way each test creates its own project and deletes it again. Set
`GNS3_E2E_KEEP=1` to keep the project (and a started instance) on failure
and print where to look at it.

The dynamips scenarios give their routers an idle-PC: detected once per
image through the controller's `auto_idlepc` (a throwaway project and a
real CPU-usage measurement — the GUI's idle-PC finder path) and cached in
`~/.cache/gns3-e2e/idlepc.json` keyed by the image checksum. Without one,
each c7200 burns a **full CPU core** for the whole scenario — the e2e
creates raw nodes, so no template supplies a value. Set `GNS3_E2E_IDLEPC`
to skip the detection and use the given value (detection failing is never
fatal: the routers simply run without one).

`harness.py` holds the shared pieces — REST client, server lifecycle, the
IOS console driver, the Docker guest driver (a tiny Docker Engine API
client over the daemon socket, plus the digest-pinned image helper), a
WebSocket notification collector (a sync facade over `websockets`' sync
client for asserting on live notification streams), host-side kernel
inspections (bridge membership, tap admin state, tc qdiscs, the L2-anchor
spec §E assertions) — so a new node type adds only its own scenario module.

Current scenarios:

* `test_dynamips_kernel_datapath.py` — two real c7200 routers: kernel link
  (anchors, per-link bridge, netem delay, suspend, capture, delete/re-create,
  stop/start) plus a serial link staying on the relay, and a negative
  control on an isolated relay-configured instance.
* `test_ethernet_switch_kernel_datapath.py` — a real Ethernet switch
  (kernel bridge) between two c7200 routers: deferred joins on boot, VLAN
  isolation, absorbed-anchor filters/suspend/capture, VPCS peers staying on
  the relay, and a relay negative control.
* `test_ethernet_switch_cascade.py` — two Ethernet switches cascaded through
  the link-owned veth pair (`gs<link_id>0/1`, each end enslaved into its own
  switch's bridge): a dot1q trunk cascade carrying two VLANs at once across
  two c7200 routers per switch, the symmetric access/trunk mode flip on the
  cascade ends, two-sided netem (one end per direction), suspend, link
  delete/re-create (the pair dies with the link, the replacement mints new
  names), zero residue.
* `test_iol_docker_kernel_datapath.py` — two real iol-xe containers (Cisco
  CML iol-runner images): kernel link through the port bridge's swappable
  TAP leg (anchors at start, netem delay, the TAP-anchor classifier spot
  check for bpf match-drop and the eBPF every-nth mode, suspend, capture,
  link delete/re-create swap, node stop/start rewiring) and a relay
  negative control.
* `test_iou_kernel_datapath.py` — two real IOU routers (a real IOU image
  from the images directory, the real IOS CLI on the server's telnet
  console): kernel link through the [IOL fabric ↔ TAP] port bridge (same
  lifecycle as the iol-xe containers) including the TAP-anchor classifier
  spot check and a filter surviving a node restart, a serial link staying
  on the relay (serial bays never anchor), and a relay negative control
  whose filters ride the IOU-specific `iol_bridge add_packet_filter` engine
  (delay and frequency_drop measured through real traffic).
* `test_qemu_kernel_datapath.py` — two real IOSv routers (a real qcow2
  image from the images directory's `QEMU` subfolder, linked clone, the
  real IOS CLI on the server's telnet console): the anchor TAP is QEMU's
  own netdev (no port bridge in between) — the full kernel lifecycle plus
  a relay negative control where the anchor carries as the relay's
  AF_PACKET endpoint. IOSv boots a real IOS: this is the slowest scenario
  pair (~6½ min kernel, ~5 min relay).
* `test_docker_kernel_datapath.py` — two real Alpine containers (the plain
  veth datapath): the per-link kernel bridge enslaves exactly the two veth
  host ends, real ICMP crosses, the filter matrix runs one type at a time
  (netem core and extensions, cls_bpf match-drop, the eBPF classifier —
  each measured through real traffic), plus a relay negative control whose
  own filters (delay, frequency_drop, bpf) really shape the wire as uBridge
  userspace bridge filters, and a relay→kernel reopen upgrade (the server's
  datapath choice is flipped across a restart).
* `test_marker_kernel_datapath.py` — two real Alpine containers on a
  kernel-only link with traffic-insight markers attached to a veth anchor
  (`marker add_kernel`): `marker.match` signals collected off the dedicated
  marker WebSocket with their full identity (filter/tag/link_id/node_id/len
  and the tx/rx direction set of a ping), the main project channel asserted
  free of matches, BPF and direction enforcement, host pcap exactness,
  pause/resume silence counting against a still-firing sibling, tag replay
  (timeline, display filter, link narrowing, window, the 409 gate) and
  marker delete taking pcap plus signals with it.

The Docker scenarios run a digest-pinned `alpine:3`, so every developer
tests the same bytes: a cached copy in the local Docker daemon costs no
network, a cache miss pulls through the server's own image-pull route, and
with neither cache nor registry the scenario skips (`GNS3_E2E_DOCKER_IMAGE`
overrides the reference). Their guests are addressed the way a GNS3 user
does it — the node's persistent `/etc/network/interfaces`, which the
container's `init.sh` applies at boot — and driven through the Docker
daemon socket the server itself uses.

Every kernel scenario also asserts the L2-anchor spec's server-side
guarantees (`docs/design/ubridge-l2-anchor-spec.md` §E): anchors and bridges
carry no L3 identity (`assert_pure_l2`), joined ports are FORWARDING
(`assert_forwarding`), and — in the Dynamips suite — an idle link with the
guests silenced stays silent for 5 s (`assert_idle_silence`). These skip on
a uBridge without `link l2only` (probed once by `harness.l2only_supported()`).

Set `GNS3_E2E_DEBUG=1` to run the isolated instance with debug logging (the
uBridge command stream lands in its `server.log`).
