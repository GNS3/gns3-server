> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.


# GNS3 Web Wireshark Container Management Guide

This document describes how to manage GNS3 Web Wireshark containers using the management script or Docker commands.

## Installation

Before using Web Wireshark, you need to set up the Docker image:

```bash
pip install . && gns3-wireshark-setup
```

This will:
1. First try to pull the `gns3/web-wireshark:latest` image from Docker Hub
2. If pull fails, build the image locally using the Dockerfile

The setup command shows the output from `docker pull` or `docker build` directly, so you can see the progress.

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│              Host Machine                        │
│                                                  │
│  ┌────────────────────────────────────────────┐ │
│  │   Docker Network: gns3-wireshark           │ │
│  │   (Bridge network for container-host       │ │
│  │    communication)                          │ │
│  │                                             │ │
│  │  ┌──────────────────────────────────────┐ │ │
│  │  │  Container: gns3-PROJECT-ID          │ │ │
│  │  │                                      │ │ │
│  │  │  Link 1: Display :10001, Port 10001  │ │ │
│  │  │  Link 2: Display :10002, Port 10002  │ │ │
│  │  │  Link 3: Display :10003, Port 10003  │ │ │
│  │  │  ...                                 │ │ │
│  │  └──────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## Quick Start (Using Management Script)

### Prerequisites
- Docker is running
- Virtual environment is activated: `source venv/bin/activate`

### Start Session

```bash
# Start session (using all defaults)
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "5af0fe00-f39d-4985-8669-7e8c512d729c" \
  --link-id "f233f27f-7432-49c3-9aa2-50e326a10eec" \
  --jwt-token "YOUR_JWT_TOKEN"

# Use custom image
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "5af0fe00-f39d-4985-8669-7e8c512d729c" \
  --link-id "f233f27f-7432-49c3-9aa2-50e326a10eec" \
  --jwt-token "YOUR_JWT_TOKEN" \
  --image "gns3/web-wireshark:test"
```

### Access Web Interface

After starting, access Wireshark at:
```
ws://<container-ip>:<port>
```

### Stop Session

```bash
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  stop \
  --project-id "test-project" \
  --link-id "link-1"
```

### Delete Container

```bash
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  delete-container \
  --project-id "test-project"
```

## Resource Parameter Configuration

### Memory Configuration

```bash
# Default 2GB memory
--memory "2g"

# Custom memory
--memory "4g"      # 4GB
--memory "512m"   # 512MB
--memory "1g" \
--memory-swap "2g" # 1GB memory + 2GB swap
```

### CPU Configuration

```bash
# Default 1 CPU core
--cpus 1.0

# Custom CPU
--cpus 0.5    # 50% CPU
--cpus 2.0    # 2 CPU cores
--cpus 4.0    # 4 CPU cores
```

### Process Limit Configuration

```bash
# Default max 1000 processes
--pids-limit 1000

# Custom limit
--pids-limit 500     # Max 500 processes
--pids-limit 2000    # Max 2000 processes
```

### Complete Example

```bash
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "test-project" \
  --link-id "link-1" \
  --jwt-token "test-token" \
  --image "gns3/web-wireshark:latest" \
  --memory "4g" \
  --memory-swap "6g" \
  --cpus 2.0 \
  --pids-limit 2000
```

## Parameter Reference Table

| Parameter | Default Value | Description | Example |
|-----------|---------------|-------------|---------|
| --image | gns3/web-wireshark:latest | Docker image | ubuntu:latest |
| --memory | 2g | Memory limit | 4g, 512m |
| --memory-swap | Same as memory | Memory swap limit | 4g, 8g |
| --cpus | 1.0 | CPU cores | 0.5, 2.0 |
| --pids-limit | 1000 | Process limit | 500, 2000 |

## Docker Network Management

### Create Network

```bash
docker network create \
  --driver bridge \
  --subnet=100.64.0.0/22 \
  gns3-wireshark
```

### Delete Network

```bash
docker network rm gns3-wireshark
```

**Warning:** Stop and disconnect all containers before deleting the network.

### View Network Information

```bash
# List all Docker networks
docker network ls

# View network details
docker network inspect gns3-wireshark

# List containers connected to the network
docker network inspect gns3-wireshark -f '{{range .Containers}}{{.Name}} {{end}}'
```

## Performance Metrics

### Per Wireshark Instance Resource Usage

| Resource Type | Usage | Description |
|---------------|-------|-------------|
| **Memory** | 150-250 MB | Depends on capture traffic and number of parsed protocols |
| **CPU** | 0.5-2% | Lower at idle, increases with high traffic |
| **Threads** | ~30 threads | Wireshark multi-threaded architecture |
| **Disk I/O** | Minimal | Mostly log writing |

### Container Resource Configuration Recommendations

Based on `--pids-limit 1000` and `--memory="2g"` configuration:

| Wireshark Instances | Estimated Threads | Estimated Memory | Recommended Use Case |
|---------------------|-------------------|------------------|---------------------|
| 1-3 | 120-200 threads | 450-750 MB | Lightweight projects, small topologies |
| 4-6 | 230-290 threads | 600-1.5 GB | Medium projects, multiple network links |
| 7-10 | 320-410 threads | 1-2.5 GB | Large projects, dense capture |
| 10+ | >400 threads | >2.5 GB | Warning: Increase memory limit |

### Actual Test Data

**Test Environment:** 3 Wireshark instances running simultaneously

```
CONTAINER ID   NAME                     CPU %     MEM USAGE / LIMIT   MEM %     NET I/O          BLOCK I/O     PIDS
19363d29bd9d   gns3-PROJECT-ID          4.59%     735.6MiB / 2GiB     35.92%    386kB / 38.6MB   0B / 15.5MB   201
```

**Detailed Process Statistics:**
- Total threads: ~204
- Total processes: ~61
- Per Wireshark instance: ~30 threads + 1 parent process

### Performance Optimization Recommendations

1. **Memory is the main bottleneck**, not PID limit
   - Default 2GB memory can support 6-8 Wireshark instances
   - When needing more instances, increase memory first rather than PID limit

2. **Start Wireshark on demand**
   - Only start Wireshark for links that need packet capture
   - Stop sessions promptly when done to release resources

3. **Multi-container strategy**
   - For super large projects (10+ links), consider using multiple containers
   - Each container handles 5-8 links for better resource isolation and stability

4. **Monitor resource usage**
   ```bash
   # Real-time container resource monitoring
   docker stats gns3-PROJECT-ID

   # Check process count inside container
   docker exec gns3-PROJECT_ID bash -c "ps -eLf | wc -l"
   ```

## Management Commands (Docker)

### View All Active xpra Sessions

```bash
docker exec "${CONTAINER_NAME}" xpra list
```

### View Container Logs

```bash
docker logs "${CONTAINER_NAME}"
```

### View Processes Inside Container

```bash
docker exec "${CONTAINER_NAME}" ps aux | grep -E "Xvfb|xpra"
```

### Enter Container Shell

```bash
docker exec -it "${CONTAINER_NAME}" /bin/bash
```

### Stop Container

```bash
docker stop "${CONTAINER_NAME}"
```

### Delete Container

```bash
docker rm "${CONTAINER_NAME}"
```

## Troubleshooting

### Check if Container is Running

```bash
docker ps | grep "${CONTAINER_NAME}"
```

### Check Network Connection

```bash
# Ping container from host
docker exec "${CONTAINER_NAME}" ping -c 3 100.64.0.1

# Check port listening
docker exec "${CONTAINER_NAME}" netstat -tlnp | grep xpra
```

### View xpra Logs

```bash
docker exec "${CONTAINER_NAME}" ls -la /tmp/sessions/
```

### Restart Specific Session

```bash
LINK_ID=1
DISPLAY_ID=$LINK_ID

# Stop session
docker exec "${CONTAINER_NAME}" xpra stop ":${DISPLAY_ID}"

# Clean up session files
docker exec "${CONTAINER_NAME}" rm -rf "/tmp/sessions/link-${LINK_ID}"

# Restart (see previous start commands)
```

### Thread Creation Error (QThread::start: Thread creation error)

**Error Message:**
```
QThread::start: Thread creation error (Resource temporarily unavailable)
```

**Root Cause Analysis:**
- Docker container PID limit (`--pids-limit`) actually limits thread count
- Each Wireshark instance requires approximately 30 threads
- Default limit of 200 may not be enough for multiple Wireshark instances

**Solution:**

```bash
# Check current thread usage
docker exec "${CONTAINER_NAME}" bash -c "ps -eLf | wc -l"

# Increase PID limit (recommended to set to 1000)
docker update --pids-limit 1000 "${CONTAINER_NAME}"

# Verify new limit
docker inspect "${CONTAINER_NAME}" --format '{{.HostConfig.PidsLimit}}'
```

**Prevention:**
- Set a reasonable PID limit when starting the container: `--pids-limit 1000`
- Refer to "Performance Metrics" section for appropriate configuration

### XDG_RUNTIME_DIR Warning

**Warning Message:**
```
Warning: XDG_RUNTIME_DIR is not defined
 and '/run/user/1000' does not exist
 using '/tmp'
```

**Explanation:**
- This is a warning, not an error; Xpra falls back to using `/tmp`
- May affect some features relying on XDG specification

**Solution:**
Ensure you are using the latest Docker image, which includes the following fix:
- Create `/run/user/1000` directory
- Set `XDG_RUNTIME_DIR` environment variable

For manual fix:
```bash
docker exec "${CONTAINER_NAME}" mkdir -p /run/user/1000
docker exec "${CONTAINER_NAME}" bash -c "export XDG_RUNTIME_DIR=/run/user/1000"
```

## Manual Testing (Step-by-Step)

This section preserves the original manual testing steps used during development.

### Prerequisites
- Docker is running
- Virtual environment is activated: `source venv/bin/activate`

### Basic Test Commands

```bash
# 1. Start session (using all defaults)
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "5af0fe00-f39d-4985-8669-7e8c512d729c" \
  --link-id "f233f27f-7432-49c3-9aa2-50e326a10eec" \
  --jwt-token "YOUR_JWT_TOKEN"

# 2. Use custom image
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "5af0fe00-f39d-4985-8669-7e8c512d729c" \
  --link-id "f233f27f-7432-49c3-9aa2-50e326a10eec" \
  --jwt-token "YOUR_JWT_TOKEN" \
  --image "gns3/web-wireshark:test"

# 3. View containers
docker ps | grep gns3-wireshark
docker logs gns3-wireshark-test-project

# 4. Stop session
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  stop \
  --project-id "test-project" \
  --link-id "link-1"

# 5. Delete container
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  delete-container \
  --project-id "test-project"
```

### WebSocket Access URL

After starting a session, access Wireshark via WebSocket:
```
ws://192.168.1.140:3080/v3/projects/5af0fe00-f39d-4985-8669-7e8c512d729c/links/f233f27f-7432-49c3-9aa2-50e326a10eec/capture/web-wireshark?token=YOUR_JWT_TOKEN
```

## Cleanup (If Tests Fail)

```bash
# Delete test containers
docker ps -a | grep 'gns3-wireshark-test' | awk '{print $1}' | xargs -r docker rm -f

# Delete test networks
docker network ls | grep 'gns3-wireshark' | awk '{print $2}' | xargs -r docker network rm
```

## File Structure

```
gns3server/agent/web_wireshark/
├── setup_wireshark_image.py      # Docker image setup tool (gns3-wireshark-setup)
├── manage_wireshark.py           # CLI management tool
├── manager.py                    # Session management logic
├── docker_client.py             # Docker API client
├── docker/
│   └── Dockerfile               # Container image definition
└── WEB_WIRESHARK.md             # This documentation
```

## Known Issues

- JWT token is passed via command-line arguments (visible in `/proc/<pid>/cmdline`). Consider using a temporary file inside the container for improved security.
- `cmd_delete_container` and `cmd_delete` in manage_wireshark.py are duplicate code.
- `stop-container` and `delete-container` subcommands are defined but not registered in the commands dictionary.
- `link_id_to_display` and `link_id_to_port` return the same value (10000-19999), which may cause confusion since xpra typically uses different display numbers and ports.
- Container health check timeout (5 seconds) may be insufficient on slow systems.
- Docker Unix socket connection error handling could be improved (FileNotFoundError not properly caught).

## Notes

- Default uses `gns3/web-wireshark:latest` image
- Use `--verbose` to see detailed logs
- Containers use 100.64.0.0/22 network
- xpra port range: 10000-19999 (deterministic based on link_id)
- Health check: `xpra list`
- Log configuration: json-file, max-size=10m, max-file=3
