# GNS3 Web Wireshark Container Management Guide

This document describes how to manage GNS3 Web Wireshark containers, enabling communication with the host via Docker network without port binding.

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
│  │  │  Link 1: Display :1, Port 10001     │ │ │
│  │  │  Link 2: Display :2, Port 10002     │ │ │
│  │  │  Link 3: Display :3, Port 10003     │ │ │
│  │  │  ...                                 │ │ │
│  │  └──────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## Performance Metrics and Resource Planning

### Per Wireshark Instance Resource Usage

| Resource Type | Usage | Description |
|-------------|-------|-------------|
| **Memory** | 150-250 MB | Depends on capture traffic and number of parsed protocols |
| **CPU** | 0.5-2% | Lower at idle, increases with high traffic |
| **Threads** | ~30 threads | Wireshark multi-threaded architecture (GUI, capture, parsing, rendering) |
| **Disk I/O** | Minimal | Mostly log writing |

### Container Resource Configuration Recommendations

Based on `--pids-limit 1000` and `--memory="2g"` configuration:

| Wireshark Instances | Estimated Threads | Estimated Memory | Recommended Use Case |
|-------------------|-------------------|-----------------|---------------------|
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

## 1. Create Docker Network

First, create a bridge network for communication between containers and the host:

```bash
# Create gns3-wireshark network
docker network create \
  --driver bridge \
  --subnet=100.64.0.0/22 \
  gns3-wireshark
```

**Notes:**
- Use bridge driver
- Subnet range: 100.64.0.0/22
- After containers connect to this network, services can be accessed directly via container IP

### Delete Docker Network

```bash
# Delete gns3-wireshark network
docker network rm gns3-wireshark
```

**Warning:**
- Before deleting a network, stop and disconnect all containers connected to it
- Otherwise you'll get: `Error: network X has active endpoints`
- Force deleting a network will interrupt all container network connections

### View Network Information

```bash
# List all Docker networks
docker network ls

# View gns3-wireshark network details
docker network inspect gns3-wireshark

# List containers connected to the network
docker network inspect gns3-wireshark -f '{{range .Containers}}{{.Name}} {{end}}'
```

### Disconnect Container from Network

```bash
# Disconnect specified container from network
CONTAINER_NAME="gns3-${PROJECT_ID}"
docker network disconnect gns3-wireshark "${CONTAINER_NAME}"
```

### Safe Network Deletion Procedure

```bash
# 1. List all containers in the network
docker network inspect gns3-wireshark -f '{{range .Containers}}{{.Name}} {{end}}'

# 2. Stop all containers using the network
docker stop gns3-project-1
docker stop gns3-project-2
# ... or batch stop all related containers

# 3. Delete the network
docker network rm gns3-wireshark
```

## 2. Start Container

```bash
# Set project ID
PROJECT_ID="5af0fe00-f39d-4985-8669-7e8c512d729c"

# Start container
docker run -d \
  --name "gns3-5af0fe00-f39d-4985-8669-7e8c512d729c" \
  --memory="2g" \
  --memory-swap="2g" \
  --cpus="1.0" \
  --pids-limit 1000 \
  --log-driver json-file \
  --log-opt max-size="10m" \
  --log-opt max-file="3" \
  --network gns3-wireshark \
  --health-cmd="xpra list || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  --restart unless-stopped \
  gns3/web-wireshark:test
```

**Parameter Description:**
- `--name`: Container name in format `gns3-PROJECT-ID`
- `--network`: Connect to gns3-wireshark network
- `-d`: Run in background

## 3. Start Wireshark Instance

Start different Wireshark instances based on Link ID, each instance corresponds to an independent Display and Port.

### 3.1 Start Wireshark for a Single Link

```bash
# 8a14355e-4a62-406c-98de-acf5ec9394de
# f233f27f-7432-49c3-9aa2-50e326a10eec
# a0d9132c-0f65-4ff8-9e5f-1c8061f70bdd

# Start xpra session
docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
  xpra start ":101" \
  --xvfb="Xvfb -screen 0 1920x1080x24 +extension RANDR" \
  --html=on \
  --bind-tcp=0.0.0.0:12345 \
  --session-name="link-8a14355e-4a62-406c-98de-acf5ec9394de" \
  --daemon=yes \
  --dbus-launch=no \
  --resize-display=yes


docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
  xpra start ":102" \
  --xvfb="Xvfb -screen 0 1920x1080x24 +extension RANDR" \
  --html=on \
  --bind-tcp=0.0.0.0:12346 \
  --session-name="link-f233f27f-7432-49c3-9aa2-50e326a10eec" \
  --daemon=yes \
  --dbus-launch=no \
  --resize-display=yes


docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
  xpra start ":103" \
  --xvfb="Xvfb -screen 0 1920x1080x24 +extension RANDR" \
  --html=on \
  --bind-tcp=0.0.0.0:12347 \
  --session-name="link-a0d9132c-0f65-4ff8-9e5f-1c8061f70bdd" \
  --daemon=yes \
  --dbus-launch=no \
  --resize-display=yes

# Wait for xpra initialization
sleep 3

# Start Wireshark application
docker exec -d "${CONTAINER_NAME}" \
  sh -c "DISPLAY=:${DISPLAY_ID} wireshark &"

# Wait for Wireshark to start
sleep 2

# Verify Wireshark is running
docker exec "${CONTAINER_NAME}" \
  ps aux | grep wireshark | grep -v grep

# Verify xpra started successfully
docker exec "${CONTAINER_NAME}" \
  xpra list | grep ":${DISPLAY_ID}"
```

### 3.2 Pass GNS3 Capture Traffic to Wireshark

Run inside the container:

```bash
docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
    bash -c 'curl -N -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTcyMjMwMCwidmVyIjowfQ.gCv42XkJu9AeoUssVCOjp1aJdqoYSEsXLWHk00C8PZk" \
      "http://192.168.1.140:3080/v3/projects/5af0fe00-f39d-4985-8669-7e8c512d729c/links/8a14355e-4a62-406c-98de-acf5ec9394de/capture/stream" | \
      wireshark -i - -k -display :101'

docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
    bash -c 'curl -N -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTcyMjMwMCwidmVyIjowfQ.gCv42XkJu9AeoUssVCOjp1aJdqoYSEsXLWHk00C8PZk" \
      "http://192.168.1.140:3080/v3/projects/5af0fe00-f39d-4985-8669-7e8c512d729c/links/f233f27f-7432-49c3-9aa2-50e326a10eec/capture/stream" | \
      wireshark -i - -k -display :102'

docker exec gns3-5af0fe00-f39d-4985-8669-7e8c512d729c \
    bash -c 'curl -N -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTcyMjMwMCwidmVyIjowfQ.gCv42XkJu9AeoUssVCOjp1aJdqoYSEsXLWHk00C8PZk" \
      "http://192.168.1.140:3080/v3/projects/5af0fe00-f39d-4985-8669-7e8c512d729c/links/a0d9132c-0f65-4ff8-9e5f-1c8061f70bdd/capture/stream" | \
      wireshark -i - -k -display :103'
```

**Parameter Description:**
- `curl -N`: Disable buffering, stream data in real-time
- `-H "Authorization: Bearer ${GNS3_JWT_TOKEN}"`: Add JWT authentication header
- `/v3/projects/{project_id}/links/{link_id}/capture/stream`: GNS3 capture stream interface
- `docker exec -i`: Keep stdin open, pass pipe data
- `wireshark -i - -k`: Read pcap data from stdin and start capturing immediately

**Notes:**
1. Ensure Wireshark is already running on the specified Display
2. JWT Token needs permission to access the project
3. If you encounter permission issues, check GNS3 server authentication configuration



## 4. Get Container IP Address

```bash
# Get container IP address
CONTAINER_NAME="gns3-${PROJECT_ID}"
CONTAINER_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "${CONTAINER_NAME}")

echo "Container IP: ${CONTAINER_IP}"
```

## 5. Access Wireshark Web Interface

Access in browser:

```
http://<containerIP>:<port>
```

**Examples:**
- Link 1: http://100.64.0.2:10001
- Link 2: http://100.64.0.2:10002
- Link 3: http://100.64.0.2:10003

## 6. Management Commands

### 6.1 View All Active xpra Sessions

```bash
docker exec "${CONTAINER_NAME}" xpra list
```

### 6.2 Stop Session for Specified Link

```bash
LINK_ID=1
DISPLAY_ID=$LINK_ID

docker exec "${CONTAINER_NAME}" xpra stop ":${DISPLAY_ID}"
```

### 6.3 View Container Logs

```bash
docker logs "${CONTAINER_NAME}"
```

### 6.4 View Processes Inside Container

```bash
docker exec "${CONTAINER_NAME}" ps aux | grep -E "Xvfb|xpra"
```

### 6.5 Enter Container Shell

```bash
docker exec -it "${CONTAINER_NAME}" /bin/bash
```

### 6.6 Stop Container

```bash
docker stop "${CONTAINER_NAME}"
```

### 6.7 Delete Container

```bash
docker rm "${CONTAINER_NAME}"
```

## 9. Troubleshooting

### 9.1 Check if Container is Running

```bash
docker ps | grep "${CONTAINER_NAME}"
```

### 9.2 Check Network Connection

```bash
# Ping container from host
docker exec "${CONTAINER_NAME}" ping -c 3 100.64.0.1

# Check port listening
docker exec "${CONTAINER_NAME}" netstat -tlnp | grep xpra
```

### 9.3 View xpra Logs

```bash
docker exec "${CONTAINER_NAME}" ls -la /tmp/sessions/
```

### 9.4 Restart Specific Session

```bash
LINK_ID=1
DISPLAY_ID=$LINK_ID

# Stop session
docker exec "${CONTAINER_NAME}" xpra stop ":${DISPLAY_ID}"

# Clean up session files
docker exec "${CONTAINER_NAME}" rm -rf "/tmp/sessions/link-${LINK_ID}"

# Restart (see previous start commands)
```

### 9.5 Thread Creation Error (QThread::start: Thread creation error)

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
- Refer to "Performance Metrics and Resource Planning" section for appropriate configuration

### 9.6 XDG_RUNTIME_DIR Warning

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
