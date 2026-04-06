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

- **Controller `host`**: If set to `0.0.0.0`, it will be changed to `127.0.0.1`, which breaks cross-subnet link creation
- **Solution**: Always use the actual IP address for Controller's `host` field

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

1. Verify Controller's `host` is set to its actual IP, not `0.0.0.0`
2. Ensure both machines are on the same network
3. Check firewall rules allow UDP communication
