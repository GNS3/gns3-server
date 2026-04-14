# GNS3 uBridge Permission Issue

## Problem
Docker container node fails to start with error: `uBridge requires root access or the capability to interact with network adapters`

## Root Cause
- uBridge needs to create TAP network interfaces to connect Docker containers to GNS3 virtual network
- This requires `CAP_NET_ADMIN` and `CAP_NET_RAW` capabilities
- Other node types (like QEMU) may have their own network implementation and don't need uBridge

## Solution
```bash
sudo setcap cap_net_admin,cap_net_raw=eip /usr/bin/ubridge
```

## Code Locations
- uBridge path check: `gns3server/compute/base_manager.py:298` (`has_privileged_access`)
- Permission check call: `gns3server/compute/base_node.py:851`
- Error message definition: `gns3server/compute/base_node.py:852`

## Error Propagation Flow
Error is propagated via `NodeError` exception:
1. `NodeError` is caught at `gns3server/api/routes/compute/__init__.py:131-137`
2. Returns HTTP 409 with JSON: `{"message": "...", "exception": "NodeError"}`
3. Frontend should read error info from `message` field
