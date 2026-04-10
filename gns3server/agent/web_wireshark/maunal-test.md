# Web Wireshark Management Script - Standalone Testing Guide

## Quick Testing

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
  --jwt-token "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTc4MjI5MywidmVyIjowfQ.gFHuLijX86YOdmMYNckRJNiCbTTfYzGnE6RWJUlmQdk"

# 2. Use custom image
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "5af0fe00-f39d-4985-8669-7e8c512d729c" \
  --link-id "f233f27f-7432-49c3-9aa2-50e326a10eec" \
  --jwt-token "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTc4MjI5MywidmVyIjowfQ.gFHuLijX86YOdmMYNckRJNiCbTTfYzGnE6RWJUlmQdk" \
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

# ws

ws://192.168.1.140:3080/v3/projects/5af0fe00-f39d-4985-8669-7e8c512d729c/links/f233f27f-7432-49c3-9aa2-50e326a10eec/capture/web-wireshark?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3NTc4MjI5MywidmVyIjowfQ.gFHuLijX86YOdmMYNckRJNiCbTTfYzGnE6RWJUlmQdk

## Resource Parameter Configuration

### Memory Configuration

```bash
# Default 2GB memory
--memory "2g"

# Custom memory
--memory "4g"      # 4GB
--memory "512m"    # 512MB
--memory "1g" \
--memory-swap "2g"  # 1GB memory + 2GB swap
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

### Complete Example (Custom Resources)

```bash
# Using custom resource configuration
python3 gns3server/agent/web_wireshark/manage_wireshark.py \
  --verbose start \
  --project-id "test-project" \
  --link-id "link-1" \
  --jwt-token "test-token" \
  --image "ubuntu:latest" \
  --memory "4g" \
  --memory-swap "6g" \
  --cpus 2.0 \
  --pids-limit 2000
```

## Parameter Reference Table

| Parameter | Default Value | Description | Example |
|------|--------|------|------|
| --image | gns3/web-wireshark:latest | Docker image | ubuntu:latest |
| --memory | 2g | Memory limit | 4g, 512m |
| --memory-swap | Same as memory | Memory swap limit | 4g, 8g |
| --cpus | 1.0 | CPU cores | 0.5, 2.0 |
| --pids-limit | 1000 | Process limit | 500, 2000 |

## Cleanup (If Tests Fail)

```bash
# Delete test containers
docker ps -a | grep 'gns3-wireshark-test' | awk '{print $1}' | xargs -r docker rm -f

# Delete test networks
docker network ls | grep 'gns3-wireshark' | awk '{print $2}' | xargs -r docker network rm
```

## Notes

- Default uses `gns3/web-wireshark:latest` image
- Use `--verbose` to see detailed logs
- Containers use 100.64.0.0/22 network
- xpra port range: 12300-12309
- **Fixed**: CPU is now correctly allocated as 1.0 cores (previously incorrectly set to 0.1 cores)
- **Added**: Health check (xpra list)
- **Added**: Log configuration (json-file, max-size=10m, max-file=3)

