---
name: docker-container-stop-delay
description: Docker containers not responding to SIGTERM cause ~5s stop delays when closing a project
metadata:
  type: reference
---

# Docker Container Stop Delay Analysis

## Background
When stopping a GNS3 project, some Docker containers take ~5s to exit while others stop instantly.

## Root Cause
Docker's `stop` command sends SIGTERM and waits `t` seconds (GNS3 sets `t=5`) before sending SIGKILL. Containers that don't handle SIGTERM are stuck waiting for the full timeout.

## Affected Containers

| Container | PID 1 | Why it's slow |
|-----------|-------|---------------|
| **AlpiNet** (alpine) | `dumb-init` → `bash -i` | Interactive bash ignores SIGTERM by design |
| **OstinatoWireshark** | `bash` (PID 1) | Linux kernel won't apply default signal actions to PID 1 without an explicit handler; interactive bash doesn't install one |

## Normal Containers (for comparison)

| Container | PID 1 | Why fast |
|-----------|-------|----------|
| Chromium | `/usr/bin/chromium` | Chromium handles SIGTERM natively |
| webterm | `dumb-init` → firefox | Firefox responds to SIGTERM immediately |

## Related Files
- `gns3-registry/docker/alpinet/Dockerfile`
- `gns3-registry/docker/ostinato-wireshark/Dockerfile`
- `gns3-registry/docker/ostinato-wireshark/entry.sh`
- `gns3-registry/docker/chromium/Dockerfile`
- `gns3-registry/docker/ipterm/web/Dockerfile`
- `gns3-server/gns3server/compute/docker/docker_vm.py:1040` — stop timeout parameter `t=5`

## Note
This is not a GNS3 server bug (except a minor `or` vs `and` logic issue at `docker_vm.py:1037` which doesn't affect behavior). The root cause is in the Docker images themselves.

See also: [[docker-container-stop-delay]]
