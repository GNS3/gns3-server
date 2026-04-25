<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.


# Controller + Compute Setup

This document describes the minimum configuration required to set up a GNS3 Controller with remote Compute nodes.

## Architecture Overview

- **Compute**: Runs individual nodes (QEMU, Docker, etc.) and provides resource monitoring
- **Controller**: Manages multiple computes, projects, and provides the REST API
- **Database**: Controller uses SQLite to store projects, nodes, and compute registration

## Minimum Configuration

### 1. Compute Node Configuration

Create the configuration file at `~/.config/GNS3/3.1/gns3_server.conf`:

```ini
[Server]
host = 0.0.0.0
port = 3080
compute_username = gns3
compute_password = gns3
```

Start the Compute:
```bash
gns3server
```

### 2. Controller Node Configuration

Create the configuration file at `~/.config/GNS3/3.1/gns3_server.conf`:

```ini
[Server]
host = 192.168.1.140
port = 3080
compute_username = gns3
compute_password = gns3
```

Start the Controller:
```bash
gns3server
```

### 3. Register Compute with Controller

Use the API to register a remote compute:

```bash
POST /v3/computes
{
  "protocol": "http",
  "host": "192.168.1.x",
  "port": 3080,
  "user": "gns3",
  "password": "gns3"
}
```

## Important Notes

### Host Configuration

- **Controller `host`**: If set to `0.0.0.0`, the controller will register itself as `127.0.0.1`, which breaks remote compute connections
- **Symptom**: Compute nodes report "No common subnet for compute X (controller) and Y" even when on the same network
- **Solution**: Always use the actual LAN IP address for the Controller's `host` field (e.g., `host = 192.168.1.104`)
- **Dynamic IP**: If the controller machine uses DHCP, set a static lease on the router or use mDNS (`.local` domain)

### Password Configuration

- If `compute_password` is not set, a random 16-character password is auto-generated on startup
- The Controller must use the same credentials as the Compute's configuration

### Network Requirements

- Controller and Compute must be on the same LAN for cross-compute links to work
- UDP tunnel is used for cross-compute links, requiring network connectivity on UDP ports

### Configuration File Location

- Default location: `~/.config/GNS3/3.1/gns3_server.conf`
- Version `3.0` uses `~/.config/GNS3/3.0/`

## Troubleshooting

### 401 Unauthorized on Compute Connect

1. Check that Compute's `compute_username` and `compute_password` match what was passed to the API
2. Verify the Compute's configuration file is correctly loaded
3. Ensure the `[Server]` section is used (not `[Controller]`)

### No Common Subnet Error

If compute nodes report:
```
Cannot get an IP address on same subnet: No common subnet for compute X (controller) and Y
```

1. **Primary cause**: Controller's `host` is set to `0.0.0.0` - it registers as `127.0.0.1` which is unreachable from compute nodes
2. Check the controller's `/v3/version` endpoint - if `controller_host` shows `127.0.0.1`, this is the issue
3. Set the Controller's `host` to its actual LAN IP address (e.g., `192.168.1.104`)
4. Verify both machines are on the same network and can ping each other
5. Check firewall rules allow TCP/UDP communication on required ports

### WebSocket Console Authentication Failed

When connecting to a remote compute node's console via WebSocket, the connection may fail with errors in the logs:

**Controller log:**
```
New client 192.168.1.104:33268 has connected to controller console WebSocket
Forwarding console WebSocket to 'ws://192.168.1.3:3080/v3/compute/projects/.../console/ws'
Client 192.168.1.104:33268 has disconnected from controller console WebSocket
```

**Compute log:**
```
WebSocket /v3/compute/projects/.../console/ws" [accepted]
ERROR gns3server.api.routes.compute.dependencies.authentication:103 Could not authenticate while connecting to compute WebSocket: Could not validate credentials
```

**Cause**: The Controller forwards its own `compute_username` and `compute_password` credentials when connecting to the Compute's WebSocket endpoint. If the Compute node does not have matching credentials configured, authentication fails.

**Solution**: Ensure the Compute node's configuration file has matching credentials:

```ini
[Server]
enable_http_auth = True
compute_username = gns3
compute_password = your_password
```

The Controller automatically uses its configured `compute_username` and `compute_password` when establishing WebSocket connections to remote computes (see `gns3server/api/routes/controller/nodes.py` lines 627-628).

**Note**: If `compute_password` is not explicitly set in the Compute's config, a random 16-character password is auto-generated at startup, making authentication impossible for any external Controller.

