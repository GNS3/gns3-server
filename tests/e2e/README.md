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
  (`GNS3_E2E_IMAGES`, default `~/GNS3/images`) available locally.

Either way each test creates its own project and deletes it again. Set
`GNS3_E2E_KEEP=1` to keep the project (and a started instance) on failure
and print where to look at it.

`harness.py` holds the shared pieces — REST client, server lifecycle, the
IOS console driver, host-side kernel inspections (bridge membership, tap
admin state, tc qdiscs) — so a new node type adds only its own scenario
module.

Current scenarios:

* `test_dynamips_kernel_datapath.py` — two real c7200 routers: kernel link
  (anchors, per-link bridge, netem delay, suspend, capture, delete/re-create,
  stop/start) plus a serial link staying on the relay, and a negative
  control on an isolated relay-configured instance.
