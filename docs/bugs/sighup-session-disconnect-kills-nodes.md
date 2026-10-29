<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.

# SIGHUP on SSH Session Disconnect Kills All Node Processes (Server Survives)

## Bug Report

**Date**: 2026-10-29 (incident), root-caused 2026-10-30
**Severity**: Medium — every node dies silently while the server stays up; only affects interactive-session launches
**Status**: Root-caused; addressed by deployment guidance (systemd / `setsid nohup` / tmux), no code change. Product-side hardening options noted under *Fix* are deliberately deferred.
**Component**: `gns3server/server.py` `_signal_handling()` — the SIGHUP→reload semantics — interacting with default SIGHUP disposition in every emulator child (uBridge, IOU, Dynamips, QEMU, VPCS) and with the kernel-datapath persistent anchor TAPs.

## Symptoms

`gns3server` started directly from an interactive SSH session (plain `gns3server ... &`, no `nohup`/`setsid`/tmux) with running kernel-datapath nodes. When the SSH client disconnects:

- Every node becomes `stopped`, but **gns3server keeps running** (it treats SIGHUP as reload).
- The server log records **no stop operation at all** — no `stopping N nodes`, nothing. The nodes simply vanish from its perspective.
- Anchor TAPs (`gi*`, `gq*`, `gd*`, …) survive as orphans — the children died without running any cleanup.
- The next `start`/`start_all` typically fails on the first round with
  `Error while sending command 'tap create "gi…"': Could not create TAP gi…: Device or resource busy`
  (HTTP 409 on the batch endpoint) and succeeds on the retry seconds later, once the sweep has won.

## Evidence (from the live occurrence)

Second-level correlation between the system journal and the GNS3 server log, 2026-10-29:

| Time | Source | Record |
|---|---|---|
| 01:43:41 | journalctl / sshd | `Received disconnect from 192.168.1.140 port 48684:11: disconnected by user` |
| 01:43:41 | gns3.log | `Server has got signal SIGHUP, reloading...` (server.py:164) followed by `Controller is reloading` |
| 01:43:42 | gns3.log | node consoles dying: repeated `EOFError: telnet connection closed` (R-3/R-4/R-5) |

Supporting state:

- The server process ran uninterrupted from 01:13 through the incident (single PID, never restarted); its PPID became 1 — the launching shell was gone.
- Five IOU nodes plus their uBridge hypervisors were dead; no `stopping`/`stopped` lines exist for this project in the log.
- Dozens of anchor TAPs still present on the host afterwards, still enslaved to their `gns3*` per-link bridges — only an unclean death leaves that surface behind.
- uBridge's own stderr during the recovery attempt shows the sweep fighting the leftovers: `Error configuring kernel: File exists` / `No such file or directory`, then the `tap create … Device or resource busy` failure at 23:51:55, and clean hypervisor starts at 23:52:03–22 on the immediate retry.

## Root Cause (confirmed)

Standard Unix session machinery, not a GNS3 logic error — but GNS3's mixed signal dispositions turn it into a silent mass death:

1. SSH disconnect → sshd tears down the PTY → kernel sends **SIGHUP to the session**; bash, on receiving SIGHUP, **forwards it to all its jobs** — i.e. the whole process group: gns3server *and* every emulator/ubridge child it spawned.
2. gns3server installs a SIGHUP handler (`server.py` `_signal_handling`, upstream since 2013) whose semantics are *reload* — so the server absorbs the signal and stays up.
3. The children have the **default SIGHUP disposition** and terminate immediately, bypassing every cleanup path (`stop()`, `_delete_anchor_taps`, port release). The persistent anchor TAPs — designed to outlive their creator and be swept on the next start — are exactly what remains behind.
4. `_create_anchor_taps` (kernel_datapath.py) sweeps same-name leftovers with a suppressed `tap delete` before `tap create`, but that sweep assumes an *unheld* leftover. On the first start after this incident the delete did not take effect yet, so `tap create` surfaced EBUSY; the second round, seconds later, succeeded.

## Fix

No code change required; the fix is how the server is launched:

- **systemd** (the gns3vm deployment — a service is outside every SSH session, gets `Restart=on-failure`, journald logging, and ordered SIGTERM shutdown that cleans up nodes properly), or
- `setsid nohup gns3server … >/dev/null 2>&1 &` (ignored dispositions are inherited across fork/exec, protecting the whole child tree), or
- tmux/screen.

Recovery after hitting it: start the nodes again (the anchor sweep wins on the second round); manually `ip link delete <tap>` only for interfaces that stay DOWN and block a start.

Product-side hardening (deferred, recorded for a rainy day):

- children spawned with SIGHUP ignored or `start_new_session=True` would make the whole tree immune; and
- `_create_anchor_taps` could take the sysfs-check + short-grace retry pattern its sibling `_delete_anchor_taps` already uses (`kernel_datapath.py`), so a *held* leftover self-heals instead of failing the first start with 409.

## Scope

- Affected: bare-metal `gns3server` launched from an interactive SSH/login session without `nohup`/`setsid`/tmux — including "typed `&` and forgot about it" runs that stay up for days.
- Not affected: the GNS3 VM and any systemd/service deployment; a clean `exit` from the shell usually leaves jobs alive (bash's `huponexit` is off by default, and its SIGHUP forwarding only fires on disconnect-type hangups), which is why this bites intermittently rather than always.
- Blast radius: all nodes on the server, silently, with no log trail — plus a 409 on the first start attempt afterwards.

## Related

- `gns3server/server.py` — `_signal_handling()`: SIGHUP→`Controller.instance().reload()` since 2013 (commit `798f0367b`, "Catch SIGTERM, SIGINT, SIGHUP and SIGQUIT…").
- `gns3server/compute/kernel_datapath.py` — `_create_anchor_taps` (the sweep) and `_delete_anchor_taps` (the sysfs+grace retry pattern a future hardening would mirror).
- `docs/bugs/networkmanager-tap-release.md` — same "stale TAP surface after an uncooperative host event" family, different mechanism.
- `docs/features/*-kernel-datapath.md` — the anchor-TAP lifecycle these leftovers come from.
