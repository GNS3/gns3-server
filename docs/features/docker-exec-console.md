<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.


# Docker exec Console (Vendor NOS Containers)

## Overview

GNS3 Docker nodes normally expose their console by attaching to the container's
PID 1 stdio. That works for CLIs that run as PID 1 (e.g. FRR's `vtysh`), but it
does **not** work for vendor NOS containers (Nokia SR Linux, Arista cEOS,
Juniper cRPD, …) whose CLI is a separate, full-screen TUI process that is *not*
on PID 1. For those, attaching to PID 1 only shows boot logs and never yields a
CLI prompt.

The `docker_exec` console type solves this. It runs a chosen command inside the
running container via the Docker exec API (with a pty) and bridges it to the
GNS3 console, so the vendor's native TUI CLI renders in the Web UI (xterm.js)
exactly as if you had run `docker exec -it <container> <cli>` in a real
terminal.

Two companion environment knobs (`GNS3_SKIP_INIT`, `GNS3_INTERFACE_NAMES`) make
the container itself boot and wire correctly for vendor NOS images. Together
they let a vendor NOS run as a first-class GNS3 Docker router node.

> Prototype status: the knobs are environment-driven and intentionally avoid
> schema changes, so existing Docker nodes (FRR, ipterm, …) are unaffected.
> `console_type: "docker_exec"` is added to the `ConsoleType` enum.

## Environment knobs

All are read from the node's `environment` field. Entries prefixed with
`GNS3_` are **not** forwarded into the container (existing GNS3 behaviour), so
they stay host-side configuration. The console-relevant ones (the full vendor
set, incl. `GNS3_SHM_SIZE` / `GNS3_DEVICES` / `GNS3_MASK_UDEV` /
`GNS3_STOP_TIMEOUT`, is documented in [vendor-nos-xrd.md](./vendor-nos-xrd.md)):

| Variable | Purpose |
|----------|---------|
| `GNS3_SKIP_INIT=1` | Do **not** prepend `/gns3/init.sh` to the entrypoint. Vendor NOS images must run their own entrypoint (e.g. SR Linux's `sr_linux`); GNS3's init script (busybox bootstrap, `ifup`, eth wait) interferes with them. |
| `GNS3_INTERFACE_NAMES=mgmt0,e1-1,e1-2,e1-3` | Rename the injected interfaces in adapter order instead of the default `eth{N}`. SR Linux expects `mgmt0` + `e1-N`; without this it does not recognise its datapath. |
| `GNS3_CONSOLE_CMD=/opt/srlinux/bin/sr_cli` | Command run by the `docker_exec` console inside the container. |
| `GNS3_CONSOLE_RESIZE=0` | Ignore client-driven console resizes (WS terminal-size control frames / telnet NAWS) and keep the tall no-paging PTY geometry. Set for CLIs that page on the PTY window size (IOS-XR) — see [Terminal geometry](#terminal-geometry-and-size-forwarding). |

## Architecture: `VendorDockerVM` subclass

All vendor-specific logic lives in a `VendorDockerVM(DockerVM)` subclass in
`gns3server/compute/docker/vendor_docker_vm.py` — `docker_vm.py` itself stays
on its baseline behaviour and is never touched by this feature.

`DockerVM` exposes four small extension hooks (pure refactorings, zero
behaviour change for existing nodes):

| Hook | Baseline behaviour | `VendorDockerVM` override |
|------|--------------------|---------------------------|
| `_prepare_init_and_interface_env(params)` | prepend `/gns3/init.sh`, set `GNS3_MAX_ETHERNET=eth{N-1}` | conditional init.sh (`GNS3_SKIP_INIT`), `GNS3_MAX_ETHERNET` follows the interface rename |
| `_start_console_server()` | telnet/ssh/http console dispatch | adds the `docker_exec` branch |
| `_get_container_ifname(adapter_number)` | `eth{N}` | `GNS3_INTERFACE_NAMES` lookup, fallback `eth{N}` |
| `_cleanup_console_resources()` | no-op | closes the docker-exec pty socket before restart/stop |

### Class selection

The Docker manager picks the class per node in `Docker.create_node()`
(`gns3server/compute/docker/__init__.py`):

```python
def _select_node_class(self, **kwargs):
    if kwargs.get("console_type") == "docker_exec":
        return VendorDockerVM
    return DockerVM
```

`console_type == "docker_exec"` is the **only** trigger — every other console
type (telnet, vnc, ssh, http, …) keeps using the unmodified `DockerVM`. All
vendor features are opt-in: without the `GNS3_*` environment variables a
`VendorDockerVM` instance behaves identically to `DockerVM` (init.sh still
runs, interfaces stay `eth{N}`, the exec command defaults to `/bin/sh`), so a
regular container can use `docker_exec` too.

## The `docker_exec` console type

Setting `console_type: "docker_exec"` makes the node's primary console port run
`_start_docker_exec_console()` instead of the attach-to-PID-1 path.

### Console architecture

```mermaid
graph LR
    A[Web UI xterm.js] -->|console WS: text frames| B[Controller forward]
    B -->|WS: text + binary| C[GNS3 Compute telnet server]
    C -->|binary pty stream| D[Docker exec API]
    D -->|Tty:true pty| E[sr_cli / vendor CLI]
    A -.->|binary control frame {"cols","rows"}| B
    B -.-> C
    C -.->|POST exec/.../resize| D
```

The console uses GNS3's **existing shared/broadcast telnet model**: a single
exec instance (one CLI session) is broadcast to every console client, exactly
like the primary console shares one PID 1. There is deliberately **no
per-client session isolation** — this matches how every other GNS3 console
behaves. The PTY geometry is likewise shared: the last client resize wins
(see [Terminal geometry](#terminal-geometry-and-size-forwarding)).

### Implementation

**File**: `gns3server/compute/docker/vendor_docker_vm.py` —
`_start_docker_exec_console()`

A small subclass `_LazyExecTelnetServer(AsyncioTelnetServer)` implements the
console. Key points:

1. **Lazy exec creation.** The exec is created on the **first client
   connection** (`client_connected_hook`), not when the node starts. This is
   essential: vendor CLIs (e.g. `sr_cli` via `prompt_toolkit`) send a
   cursor-position request (`\e[6n`, CPR) during startup and block waiting for
   the terminal's answer. If the exec starts at node-start time there is no
   xterm.js client to answer, the probe times out, and the TUI degrades (no
   status bar, "Terminal doesn't support CPR" warning). Creating the exec on
   first connect means the probe runs with a real xterm.js attached, which
   answers CPR → full TUI. After creation the exec is shared by all clients.

2. **Exec API with a pty.** `POST containers/{cid}/exec` with
   `Tty: true`, `User: "root"` (vendor CLIs reject the image's default
   unprivileged user — SR Linux returns *"User 'user' is not authorized to use
   CLI"* otherwise), and `Env: ["TERM=xterm"]` (the TUI library needs a
   recognised terminal).

3. **No while-true wrapper.** The command runs as `sh -c "<cmd>"` (no
   restart loop). When the CLI exits (`quit`, the NOS's own idle timeout, or a
   crash) the exec pty closes, the broadcast task ends, and the next client
   connection **recreates** the exec (see *Reconnection*). A `while true`
   wrapper would restart the CLI mid-session with no client attached to
   answer its startup CPR probe, producing a blank/degraded screen on
   reconnect.

### Reconnection

The exec is created lazily and **recreated on reconnect if it has died**.
`client_connected_hook` checks `_upstream_alive()` (exec id set, writer open,
broadcast task not done) before each connect:

- **First connect / dead upstream** → (re)create the exec. Because a client is
  now attached, the CLI's startup CPR probe is answered by xterm.js → full
  TUI. A half-dead writer is closed first to avoid a socket leak.
- **Live upstream** → reuse the existing exec, just send `Ctrl-L` to redraw
  for the new client.

This is what makes the console survive `quit`, idle timeout, and CLI
crashes: the death is detected (pty EOF ends the broadcast task) and the
next connection spins up a fresh exec with a terminal present. The
`_LazyExecTelnetServer` is extracted to module level specifically so this
reconnect logic is unit-tested.

4. **Hijacked raw-HTTP start.** The exec is started with
   `POST exec/{eid}/start` sent as a raw HTTP upgrade over the Docker unix
   socket (`asyncio.open_unix_connection`), the same approach docker-py uses.
   This is required because aiohttp's websocket client (`ws_connect`) is
   rejected by Docker's exec-start endpoint (HTTP 400), while a raw POST
   upgrade succeeds (101). With `Tty:true` the response body is a raw,
   non-multiplexed bidirectional pty byte stream — no frame demux needed.

5. **NAWS → exec resize.** The telnet server runs with `naws=True`; the
   `window_size_changed_callback` (`_on_naws`, gated by
   `GNS3_CONSOLE_RESIZE`) calls `POST exec/{eid}/resize?h=&w=` so the TUI
   lays out for the client's window size. The internal `_resize_exec` path
   (creation-time default, restore-on-idle) is not gated. See
   [Terminal geometry](#terminal-geometry-and-size-forwarding).

6. **Binary passthrough + redraw.** `binary=True` so TUI escape sequences reach
   xterm.js intact; `echo=False` (the pty echoes). On every client (re)connect
   a `Ctrl-L` (`\x0c`) is sent to the pty so a TUI that already drew its
   screen for a previous client redraws for the new one (otherwise a
   reconnect shows a blank screen until the next output).

### Terminal geometry and size forwarding

The exec PTY geometry is a shared resource with three consumers that want
different things:

- **Browser clients (xterm.js)** need the PTY to match their real window, or
  TUI CLIs misrender and over-render (below).
- **Non-NAWS clients** (netmiko, bare telnet — no terminal-size negotiation)
  need the PTY *tall*: CLIs that page on the PTY window size (the IOS-XR
  pager ignores `terminal length 0`) park at `--More--` on a 24-row PTY.
- **Concurrent sessions share one exec** — one browser resize changes what
  every attached client sees.

Resolution:

1. **Tall default.** The exec is created at 511×10000 (width 511 matches
   netmiko's `terminal width 511` convention). Non-NAWS clients get no paging
   and no hard wrapping.
2. **WS terminal-size forwarding.** Console WebSocket clients may send
   **binary control frames** — UTF-8 JSON `{"cols": N, "rows": N}` —
   alongside text frames carrying terminal data (xterm.js's AttachAddon only
   sends text, so binary is an unambiguous side channel; valid ranges are
   cols 2–5000, rows 2–100000, anything else is silently ignored). The
   controller forwards binary frames (previously only text was forwarded —
   and a binary frame would have crashed the old `receive_text` loop), and
   the compute side turns them into a telnet NAWS subnegotiation for
   telnet-based consoles (docker_exec included) or an asyncssh
   `change_terminal_size` for SSH consoles
   (`base_node.py` `start_websocket_console`).
3. **Races.** A size frame that arrives before/during the exec creation is
   remembered and applied right after creation — it is **not** overwritten by
   the tall default. When the **last** client disconnects the exec goes back
   to 511×10000, so a later non-NAWS client attaching to the still-live exec
   doesn't inherit a browser geometry and hit PTY-window paging.
4. **`GNS3_CONSOLE_RESIZE=0`** makes the console ignore client resizes
   entirely (the tall default is then permanent). Set it for paging CLIs
   where a browser resize would break concurrent netmiko sessions on the
   shared exec — XRd, which is line-oriented and doesn't need browser
   resizing at all.

**Why the browser must send its size — the SR Linux flicker.** `sr_cli` is a
prompt_toolkit TUI that anchors its layout with cursor-position requests
(CPR), which xterm.js answers. On a 10000-row PTY canvas the CPR-anchored
model conflicts with the winsize model, and every incremental render re-emits
the accumulated output: measured with a CPR-answering client, one `info`
command produces **~145 KB instead of ~60 KB** (~7× duplicated lines either
way — the CLI re-renders its output region as a scroll-append stream; that
part is inherent to `sr_cli` and identical outside GNS3, verified via manual
`docker exec`). The inflation is driven by **rows** (24/32 → normal, 10000 →
pathological, at any width) and is invisible without CPR answers — which is
why plain-telnet probes and real xterm.js sessions behaved so differently.
In the Web UI the excess renders as frequent full-screen clear/redraw — the
"flicker". With the browser's real size forwarded (rows ≈ 30), output volume
and rendering return to normal.

**File**: `gns3server/compute/base_node.py` — the console WebSocket guard now
allows `docker_exec` (alongside `telnet`/`ssh`), since the WS bridge connects to
the console TCP port exactly as it does for telnet. The same WS handler also
intercepts binary control frames and propagates client terminal sizes (see
[Terminal geometry](#terminal-geometry-and-size-forwarding)).

### Why earlier approaches failed (context)

- `script` + `docker exec -it`: the `script` pty had size 0 (no NAWS) → the TUI
  could not lay out → blank.
- `docker exec -i` (no `-t`) + `sr_cli -d` (dumb mode): line-mode output was
  block-buffered and visually messy.
- Direct pipe relay: telnet `CRLF` polluted line input.

The exec-API approach fixes all of these: a real pty (`Tty:true`), a real size
(NAWS resize), and a real terminal emulator (xterm.js answering CPR).

## Configuration

### SR Linux node example

```json
{
  "name": "srlinux-1",
  "node_type": "docker",
  "image": "ghcr.io/nokia/srlinux:latest",
  "adapters": 4,
  "console_type": "docker_exec",
  "start_command": "sudo -E bash -c 'touch /.dockerenv && /opt/srlinux/bin/sr_linux'",
  "environment": "GNS3_SKIP_INIT=1\nGNS3_INTERFACE_NAMES=mgmt0,e1-1,e1-2,e1-3\nGNS3_CONSOLE_CMD=/opt/srlinux/bin/sr_cli"
}
```

- `start_command` is the SR Linux launch line (as used by containerlab).
- Connect the node's ports as usual — links still use GNS3's UDP NIO datapath
  (container-agnostic); the rename only affects the in-container interface name.
- For the Web UI port **labels** to match (display `mgmt0`/`e1-1` instead of
  `Ethernet0..3`), set `custom_adapters` per port
  (`{"adapter_number": 0, "port_name": "mgmt0"}`, …). Port labels are a
  controller-side concept, independent of the compute-side interface rename.

### Appliance (`gns3a`) packaging

A SR Linux appliance lives in `gns3-registry/appliances/srlinux.gns3a`
(`registry_version: 6`). It sets the full chassis — **35 adapters**
(`mgmt0` + `e1-1`..`e1-34`) — with matching `GNS3_INTERFACE_NAMES` and 35
`custom_adapters` entries (`mgmt0`, `e1-1`..`e1-34`) so the canvas labels,
the kernel interface names and the `ethernet-1/N` CLI names all line up.

Three appliance-schema fixes are required for this appliance to load (all on
the gns3-server side; the registry JSON schema is unchanged because its docker
block allows `additionalProperties`):

1. **`DockerConsoleType`** (`schemas/controller/appliances.py`) must include
   `docker_exec`, or the Pydantic appliance model rejects the file at import.
2. **`ApplianceV1_6.custom_adapters`** must be declared on the top-level
   appliance model, or `GET /appliances` (response_model=`schemas.Appliance`)
   strips `custom_adapters` from the API response even though the file and the
   server-side template conversion handle it. (Node creation still worked
   because `appliance_to_template._add_docker_config` reads it from the raw
   dict; only the GET response was lossy.)
3. `extra_volumes` rides inside the `docker` block (passed through by
   `new_config.update(appliance_config["docker"])`); no schema change needed.

> **Symbol theme caveat.** An appliance `symbol` that starts with
> `:/symbols/` is forcibly rewritten at load time
> (`appliance_manager._load_appliances`) to the current theme's default for the
> appliance category — so `:/symbols/affinity/circle/blue/router_cloud.svg` (or
> `router2.svg`) becomes `:/symbols/affinity/circle/blue/router.svg`, because
> the theme maps only the canonical name `"router"`. This is intentional: it
> lets theme switching re-skin every node consistently. To use a non-default
> icon (e.g. `router_cloud`), install it as a **custom symbol** under the
> configured `symbols_path` and reference it by filename (no `:/symbols/`
> prefix) — custom symbols do not participate in re-theming. The SR Linux
> appliance uses `router.svg`.

### Persistent state

For SR Linux, persist `/etc/opt/srlinux` (config / AAA users / TLS certs) and
`/var/log/srlinux` (logs, optional) by adding them to the node's
`extra_volumes`. The image also declares its own `VOLUME` directories
(e.g. `/opt/srlinux/appmgr`), which GNS3 persists automatically.

## Volume persistence with `GNS3_SKIP_INIT`

This is the one place where skipping init.sh changes behaviour beyond boot:
`/gns3/init.sh` normally performs the volume-persistence bridge, and without it
**nothing writes through to the host** — the container writes to its overlay
filesystem and the data is lost on stop.

init.sh (as the entrypoint) is safe because it runs **before** the
application: for each volume it seeds the host directory with the image's
original files on first start, then `mount --bind /gns3volumes<path> <path>`
bridges persistent storage into place.

`VendorDockerVM` cannot use that position (the NOS must own its entrypoint),
so the same persistence is established entirely **outside the container and
before it exists**:

```
create() 之前:  host dir seeded from the image (docker create + docker cp, first time only)
create() 时:    host ──Docker bind mount──▶ /etc/opt/srlinux   (direct, at the real path)
启动:           NOS native entrypoint — the persisted config is visible from the first process
```

1. **`_prepare_volumes()`** — host-side, at `create()` time (after the image
   is present, before the container is created). For each persistent volume
   whose host directory lacks the `.gns3_perms` marker, a throwaway
   `docker create` container (nothing executes) is used as a `docker cp -a`
   source to seed the host directory with the image's original content. The
   marker is written after the copy attempt — a volume that has it (every
   node that ever started, on any GNS3 version) is **never re-seeded**, so
   saved configuration is never overwritten with factory content.

2. **`_mount_binds()` override** — the volume binds target the **real
   in-container paths** (`/etc/opt/srlinux`) instead of `/gns3volumes<volume>`.
   With the content seeded first, the image's files are never shadowed by an
   empty mount, and the NOS sees its persisted configuration from the very
   first process — no post-start mount pass that could race the NOS reading
   its startup config (see "History: the exec-bridge race" below).

3. **Container-side `_fix_permissions()` override** — runs the same busybox
   record/chmod/chown script **inside the container (as root) on the volume
   paths**. Because the volumes are Docker bind mounts created with the
   container, the in-container paths resolve to the host files for the whole
   container lifetime. A stopped/exited container is **not** restarted (the
   base class would, just to chown; vendor NOS images are heavy to boot):
   the pass is skipped and the next start fixes ownership. It runs at start
   (so the controller can read project files while the node runs) and at
   stop (for files written during runtime).

> The fix must run container-side: files written by the container are
> host-side root-owned, and an unprivileged GNS3 process cannot chown them
> from the host. Container-side root (with GNS3's `UsernsMode: host`) can.

With `GNS3_SKIP_INIT`, GNS3's hardcoded `/etc/network` volume (see
`docker_vm.py` `_mount_binds()`) is dropped entirely by
`VendorDockerVM._mount_binds()`: it holds GNS3's own network config for
init.sh's `ifup`, which never runs for SKIP_INIT containers — the NOS
manages its own interfaces. The override removes the bind, filters the
volume out of `self._volumes`, and deletes the host-side skeleton directory
the base class just created. Without `GNS3_SKIP_INIT` the mount is kept
(behaviour matches the base class).

### Lifecycle summary

| Phase | Normal Docker node | `VendorDockerVM` + `GNS3_SKIP_INIT` |
|-------|--------------------|--------------------------------------|
| create | — | `_prepare_volumes()` seeds host dirs from the image (first create only); volumes bound **directly** at their real paths |
| start | init.sh seeds + bind-mounts + restores perms (in-container, before the app starts) | container-side `_fix_permissions` on the volume paths (skips dead containers, no restart) |
| stop | container-side `_fix_permissions` on in-container paths (restarts an exited container) | container-side `_fix_permissions` on the volume paths (skips dead containers, no restart) |
| volume config | `_mount_binds`: host → `/gns3volumes<path>` | `_mount_binds` override: host → `<path>` directly |

### Runtime ownership safety

The start-time fix pass chowns the volume files to the host user **while the
container is running** — a deliberate deviation from the standard model, where
init.sh restores container-native ownership at start and the container never
sees host-owned files during runtime. Verified harmless for SR Linux:

1. **Most processes run as root** (`sr_linux`, appmgr) — root ignores file
   ownership entirely.
2. **Self-healing daemons.** SR Linux's `aaamgr` rewrites its managed files
   with its own ownership at boot: after the start-time pass chowned
   `etc/opt/srlinux/aaamgr_local_user.json` to the host user, the daemon
   re-created it as `srlinux:srlinux` (uid 1002, mode 700) within seconds.
3. **ACL-based access.** The directory carries a default ACL
   (`default:group:srlinux:rwx`, `default:other::rwx`), so named group ACL
   entries grant access independently of the owner uid; the observed file ACL
   (`group:srlinux:rwx`, owner `srlinux`) survives chown.

Caveat: a NOS that strictly validates ownership of its files (e.g. "SSH keys
must be root:root 600 or refuse to start") would not tolerate this. If that
ever matters, drop the start-time pass and keep only the stop-time one
(standard behaviour — the trade-off is mid-run `Permission denied` in the
file browser, identical to regular Docker nodes).

### History: the exec-bridge race (fixed)

The first SKIP_INIT implementation replicated init.sh's script **via
`docker exec` after the container started** instead of binding directly at
create time. That copied the mechanism but not the invariant that makes
init.sh safe — the entrypoint position, which guarantees the volume is in
place *before* the application runs. An exec-based bind runs **concurrently**
with the NOS boot, so whether the NOS reads its persisted config or the
overlay's factory copy was a timing race:

- a single node stop/start on an idle system won it (the exec landed ~1 s
  in, SR Linux reads its startup config at ~2–4 s) — which is why the
  round-trip "save → stop → start → config still there" passed;
- a server restart + project reload lost it (all nodes start concurrently,
  the Docker API queue delays the execs by several seconds) — SR Linux
  booted factory while the persisted `config.json` sat intact on the host;
- XRd was immune either way (systemd boots for tens of seconds before any
  XR process touches `/xr-storage`), which is why the race was never seen
  on it.

The direct-bind-at-create design removes the window entirely; there is no
ordering requirement left to verify when adopting a new NOS image.

## Troubleshooting

**1. Console shows only boot logs, no CLI**
- You are on the primary attach console. Set `console_type: "docker_exec"` and
  use `GNS3_CONSOLE_CMD` to point at the vendor CLI.

**2. `User '...' is not authorized to use CLI`**
- The exec must run as root. The implementation sets `User: "root"`; if you
  fork it, keep that.

**3. `Terminal doesn't support cursor position requests (CPR)`**
- This means the exec was started without an xterm.js client connected (the
  startup probe had no one to answer). The lazy-start design avoids this; if you
  see it, ensure the exec is created on first connect, not at node start.

**4. Reconnecting the Web console shows a blank screen**
- A `Ctrl-L` is sent on each connect to force a TUI redraw. If the TUI does not
  redraw, verify the `client_connected_hook` still writes `\x0c` to the pty.

**5. `aiohttp WSServerHandshakeError: 400` on exec start**
- Do **not** use the websocket client to start an exec. Use the hijacked raw
  HTTP upgrade over the unix socket (see Implementation).

**6. SR Linux data interfaces stay down**
- SR Linux defaults its data ports to `admin-state disable`; enable them in the
  CLI (`interface ethernet-1/1 admin-state enable`) and bind the interface to a
  network-instance before ping works. This is SR Linux behaviour, not a GNS3
  issue.

**7. "Session has been idle, will logout in 300 seconds" → Connection closed**
- SR Linux's own CLI idle timeout logs the CLI out, the exec pty closes, and
  the console disconnects. Reopening the console recreates the exec (see
  *Reconnection*) and gives a fresh login. To keep a permanent session,
  disable the timeout in the CLI: `enter candidate` →
  `/system cli idle-timeout disable` → `commit now`.

**8. Controller logs `Permission denied` reading files under the node's
   project directory while the node runs**
- Root-written files inside a persistent volume. The container-side
  `_fix_permissions` pass runs at start (fixes the seeded files) and at stop;
  files created by the container *during* runtime become readable after the
  next stop.
- Concrete example: SR Linux's `aaamgr` daemon rewrites
  `etc/opt/srlinux/aaamgr_local_user.json` during boot, **after** the
  start-time pass, as the image's `srlinux` user (uid 1002, mode 700) — so
  the host-side file stays `1002:1002` until the stop-time pass chowns it.
- The log line comes from the file-browser API chain: Web UI *Show in file
  manager* → `GET /v3/projects/{pid}/nodes/{nid}/files`
  (`controller/nodes.py:538`) → `project.list_node_files`
  (`compute/project.py:510`), where `magic.from_file()` cannot read the
  file and the `file_type` field is left empty for that entry. The MCP
  `list_node_files` tool uses the same code path. Size/modified-at fields
  and everything else keep working; only the type sniff and one warning
  line are affected — same behaviour as any regular Docker node writing
  root-owned files at runtime.

**9. Persistent volume empty on the host after `save` + stop**
- Ensure `GNS3_SKIP_INIT=1` is set (so the direct-bind path is taken) and
  the volume path is in `extra_volumes`; check that the host directory
  carries the `.gns3_perms` marker (written at create-time seeding) and the
  compute log for `Seeded persistent volume`.

**10. Persisted config present on the host but not applied after restart**
- On builds since the direct-bind rework this should not happen: the volume
  is in place before the first process. If you see it, confirm the server
  build includes the rework (older builds established the bind via a
  post-start `docker exec` that could lose the race against the NOS reading
  its startup config — see *History: the exec-bridge race*).

**11. Web console flickers (full-screen clear/redraw) on every command**
- The PTY is stuck at the tall 511×10000 default while a CPR-answering client
  is attached — see
  [Terminal geometry](#terminal-geometry-and-size-forwarding). Check that the
  Web UI actually sends the binary size control frames on connect/resize
  (F12 → the console WS should show outgoing binary frames), and that the
  server is new enough to forward them (the controller used to forward text
  frames only). A client that never negotiates/forwards size (old Web UI,
  bare telnet without NAWS) cannot trigger the fix — but also never answers
  CPR, so it doesn't flicker either.
- The much milder per-keystroke/5 s cursor toggles (`\e[?25l…\e[?25h`) from
  the TUI are normal and not this bug.

## Limitations

1. **Shared session (broadcast).** All console clients share one CLI session
   and can see each other's input — identical to GNS3's existing primary
   console model. There is no per-client independent session. The PTY
   geometry is shared too (last resize wins): two browsers of different sizes
   disagree harmlessly, but a browser on a *paging* CLI needs
   `GNS3_CONSOLE_RESIZE=0` to stop resizing on behalf of concurrent netmiko
   sessions (see [Terminal geometry](#terminal-geometry-and-size-forwarding)).
2. **`reset_console` not wired.** The console-reset action only handles
   `telnet`/`ssh`; it is a no-op for `docker_exec` (non-blocking; reconnect
   works fine).
3. **Prototype knobs.** `GNS3_SKIP_INIT` / `GNS3_INTERFACE_NAMES` /
   `GNS3_CONSOLE_CMD` / `GNS3_CONSOLE_RESIZE` are environment-driven; they are
   not yet first-class node schema fields and are not declared in the
   appliance (`gns3a`) schema.
4. **Rootful-Docker assumption** (`UsernsMode: host`, set for all GNS3
   Docker nodes) so the container-side chown acts on the host files' real
   uid/gid (see the volume-persistence section).
5. **Docker CLI dependency.** Volume seeding shells out to the `docker`
   binary (`docker create` + `docker cp` + `docker rm`) at create time —
   the same dependency the permission passes already have.

## References

- `gns3server/compute/docker/vendor_docker_vm.py` — `VendorDockerVM`:
  `_start_docker_exec_console`, `_LazyExecTelnetServer`,
  `_prepare_volumes` (host-side seeding), direct volume binds in
  `_mount_binds`, container-side `_fix_permissions`, `start()`.
- `gns3server/compute/docker/docker_vm.py` — `DockerVM` extension hooks
  (`_prepare_init_and_interface_env`, `_start_console_server`,
  `_get_container_ifname`, `_cleanup_console_resources`).
- `gns3server/compute/docker/__init__.py` — `Docker._select_node_class` /
  `create_node` factory.
- `gns3server/compute/base_node.py` — console WebSocket guard; binary
  terminal-size control frames → NAWS / asyncssh resize
  (`start_websocket_console`).
- `gns3server/api/routes/controller/nodes.py` — console WS forwarding
  (text and binary frames).
- `gns3server/schemas/common.py` — `ConsoleType.docker_exec`.
- containerlab `nodes/srl/srl.go` — reference for SR Linux launch command and
  interface naming.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.7 | 2026-08-22 | SKIP_INIT volume persistence rebuilt: host-side seeding at create time (`docker create` + `docker cp -a`, marker-gated so saved config is never overwritten) and direct bind mounts at the real in-container paths replace the post-start `docker exec` bridge. Root cause: the exec bridge raced the NOS reading its startup config — SR Linux read `config.json` at ~2–4 s and booted factory whenever concurrent node starts (server restart + project reload) delayed the exec past that point, while single-node stop/start and XRd (systemd touches `/xr-storage` tens of seconds in) never lost the race. New `_prepare_volumes` hook on `DockerVM`; `_fix_permissions` now targets the volume paths directly. |
| 1.6 | 2026-08-20 | Terminal geometry and size forwarding: WS binary control frames `{"cols","rows"}` → NAWS / asyncssh resize (controller now forwards binary frames; compute intercepts them); tall 511×10000 default kept for non-NAWS clients, applied post-creation and restored on last disconnect (client size racing exec creation wins over the default); new `GNS3_CONSOLE_RESIZE=0` knob for paging CLIs (XRd) where a browser resize would break concurrent netmiko sessions on the shared exec; documented the SR Linux flicker root cause (tall rows × CPR-answering client → ~2.4× re-emitted output; rows-driven, width-independent). |
| 1.5 | 2026-08-13 | Add appliance (`gns3a`) packaging section: 35-adapter full-chassis design, the three server-side schema fixes (DockerConsoleType, ApplianceV1_6.custom_adapters, extra_volumes passthrough), and the symbol-theme caveat (any `:/symbols/` symbol is rewritten to the category default at load). |
| 1.4 | 2026-08-13 | Reconnect fix: drop the while-true wrapper (it restarted the CLI with no client to answer CPR → blank screen on reconnect); the exec is now recreated on connect when the upstream has died. `_LazyExecTelnetServer` extracted to module level and unit-tested. |
| 1.3 | 2026-08-12 | Document runtime ownership safety (root processes, self-healing daemons, ACL evidence for SR Linux), the boot-ordering caveat (bridge after boot → verify save/stop/start closed loop), and troubleshooting #10. |
| 1.2 | 2026-08-12 | `_fix_permissions` rewritten: container-side (as root) on the `/gns3volumes` bind-mount targets instead of host-side — host-side chown cannot touch root-owned files when GNS3 is unprivileged. Dead containers are skipped instead of restarted. |
| 1.1 | 2026-08-12 | Refactor: vendor logic extracted from `DockerVM` into `VendorDockerVM` subclass with 4 hook points + class-selection factory. Add SKIP_INIT volume persistence (`_setup_skip_init_volumes` + `_fix_permissions`) and lifecycle comparison. Add troubleshooting entries for idle timeout and permission-denied files. |
| 1.0 | 2026-08-12 | Initial documentation of the `docker_exec` console and vendor NOS knobs. |
