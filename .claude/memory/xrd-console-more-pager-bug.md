# XRd Console --More-- Pager Bug (PTY window size paging vs terminal length 0)

## Background

Copilot commands with long output consistently failed against XRd (IOS XRv 9000 container) nodes: `device_show_run` running `show ipv4 interface brief` always reported `netmiko_multiline (failed)` (even as a single command); short-output commands like `show ipv4 interface <iface>` worked fine.

Failure sequence (from the 2026-08-18 logs):

1. First failure: `ReadTimeout: Pattern not detected: 'RP/0/RP0/CPU0:ios\#'` — the command echo matched, but the prompt never appeared within 60s
2. The copilot's single-retry reused the same netmiko session (nornir caches it on the host object) with half-consumed output in the buffer → the second failure died earlier in `command_echo_read` — a follow-on effect of the dirty session, not an independent fault

## Root Cause (fully traced)

The XRd node uses the `docker_exec` console type (`gns3server/compute/docker/vendor_docker_vm.py`, `_LazyExecTelnetServer`): a telnet TCP server whose backend is a `docker exec` PTY. Three facts combine:

1. The XR pager (at least for table-engine/TABLAST-style commands) pages on the **PTY window size (TIOCGWINSZ)**, not the CLI-level `terminal length` — `show terminal` happily reports `Length: 0 lines` while output still pages
2. `_LazyExecTelnetServer.client_connected_hook` explicitly resized the exec PTY to **80×24** "before NAWS" (`await self._on_naws(80, 24)`) — the 24 rows were **our own initial geometry, not a Docker default**. Live test: `show ipv4 interface brief` paged after exactly 24 lines
3. netmiko's telnetlib never negotiates **NAWS**, so the initial geometry is never corrected for copilot/bare-telnet clients. Real NAWS clients resize to their own geometry via the existing `_on_naws` → `POST /exec/{id}/resize` wiring

### Dead ends (do not retry)

- `show ipv4 interface brief | no-more` → `% Invalid input detected`. `| no-more` is a **Junos** pipe modifier; IOS-XR does not have it
- `terminal length 0`: takes effect at the CLI layer, but this pager ignores it
- The XR CLI has no command to change PTY rows

### Related fact: paramiko vs docker_exec

paramiko (SSH) cannot connect to a `docker_exec` console — the client-side endpoint is a plain telnet server (`AsyncioTelnetServer`); only `console_type: ssh` (standard attach path, `AsyncioSSHServer`) speaks SSH. The copilot correctly uses netmiko `*_telnet` drivers (netmiko's vendored `_telnetlib`, stdlib-free on Python 3.13).

## Decision/Implementation

### Fix (implemented 2026-08-18, branch `feat/docker-exec-default-pty-geometry`)

Change the initial exec geometry in `vendor_docker_vm.py` `client_connected_hook` from 80×24 to **511×10000** (`await self._on_naws(511, 10000)`):

- Tall/wide default so CLIs that page on PTY rows never hit `--More--` for clients that never send NAWS (netmiko, bare telnet)
- Width 511 matches netmiko's `terminal width 511` convention
- Real NAWS clients still resize to their actual geometry right after connecting (existing `_on_naws` path unchanged)
- Test: `test_first_connect_sets_tall_default_pty_geometry` in `tests/compute/docker/test_vendor_docker_vm.py`

### Fallback design (NOT implemented — keep if the pager ever resurfaces on another console type)

Channel-level loop answering `--More--` in the copilot display tool for `cisco_xr*`: prompt regex breaks; **tail-anchored** `re.search(r"--More--\s*$", buf)` with a ~150ms quiet double-confirmation before `write_channel(" ")`. Never put `--More--` into netmiko's `expect_string` — expect `re.search`es accumulated output, so content containing "More" would false-trigger.

### Still-open copilot improvements (agreed, not yet implemented)

1. Reconnect before retry: `_run_all_device_configs_with_single_retry` (display tool) and the config tool's retry should `task.host.close_connection("netmiko")` first — retrying on a dirty session is doomed
2. `session_log_file` in hosts_data netmiko extras — the copilot has no session_log anywhere, which made this bug a guessing game

## Rationale

Resizing the PTY at exec creation attacks the root (geometry is fixed before the CLI outputs anything); it covers every consumer of the docker_exec console (copilot, MCP, bare telnet) with a one-line change, while the `--More--` auto-answer design remains as a generic fallback for consoles without a resize path.

## Related Files

- `gns3server/compute/docker/vendor_docker_vm.py` — `_LazyExecTelnetServer`: `_on_naws` (exec resize), `_create_exec` (Tty=True, TERM=xterm), `client_connected_hook` (initial geometry — the fix)
- `gns3server/compute/docker/docker_vm.py:1074-1087` — standard console path: NAWS → `containers/{cid}/resize`
- `gns3server/agent/gns3_copilot/tools_v2/display_tools_nornir.py:284-341` — dirty-session retry (open item)
- `gns3server/agent/gns3_copilot/utils/get_gns3_device_port.py` — hosts_data (session_log extras insertion point)

## Examples

Live console transcript (2026-08-17):

```
RP/0/RP0/CPU0:ios#show terminal
Length: 0 lines, Width: 511 columns      <- CLI-layer setting in effect

RP/0/RP0/CPU0:ios#show ipv4 interface brief
(exactly 24 lines: timestamp + blank + header + 21 interface rows)
 --More--                                 <- the 80x24 initial exec geometry was paging
```
