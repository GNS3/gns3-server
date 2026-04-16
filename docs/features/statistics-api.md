<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# Statistics API

## `GET /v3/statistics`

Returns aggregated server statistics including compute resources, projects, nodes, links, and Web Wireshark containers.

**Authentication:** Requires active user session

**Method:** `GET`

**URL:** `http://server:3080/v3/statistics``

### Response

```json
{
  "computes": [
    {
      "compute_id": "string",
      "compute_name": "string",
      "statistics": {
        "memory_total": 16777216000,
        "memory_free": 8000000000,
        "memory_used": 8777216000,
        "swap_total": 2147479552,
        "swap_free": 1500000000,
        "swap_used": 647279552,
        "cpu_usage_percent": 45,
        "memory_usage_percent": 52,
        "swap_usage_percent": 30,
        "disk_usage_percent": 67,
        "load_average_percent": [12, 8, 5]
      }
    }
  ],
  "projects": {
    "total": 5,
    "opened": 3,
    "closed": 2
  },
  "nodes": {
    "total": 42,
    "open_project_nodes": 30,
    "closed_project_nodes": 12,
    "by_type": {
      "qemu": 20,
      "docker": 12,
      "dynamips": 6,
      "vpcs": 4
    },
    "by_status": {
      "started": 25,
      "stopped": 12,
      "suspended": 5
    }
  },
  "links": {
    "total": 38,
    "capturing": 2
  },
  "webwireshark": {
    "total_containers": 1,
    "running_containers": 1,
    "active_sessions": 2,
    "containers": [
      {
        "project_id": "e16e2b51-9ba9-403b-9df4-b2915d7508a3",
        "project_name": "test-project",
        "container_id": "6edc9029bac0",
        "status": "running",
        "running": true,
        "active_sessions": 2,
        "memory": "272.5MiB / 4GiB",
        "cpu": "0.23%",
        "pids": 69
      }
    ]
  }
}
```

### Field Descriptions

#### `computes`

Array of compute node statistics. Each compute reports:

| Field | Type | Description |
|-------|------|-------------|
| `compute_id` | string | Unique identifier for the compute |
| `compute_name` | string | Human-readable name |
| `statistics` | object | Resource usage statistics |

#### `computes[].statistics`

| Field | Type | Description |
|-------|------|-------------|
| `memory_total` | integer | Total physical memory in bytes |
| `memory_free` | integer | Free memory in bytes |
| `memory_used` | integer | Used memory in bytes |
| `swap_total` | integer | Total swap space in bytes |
| `swap_free` | integer | Free swap space in bytes |
| `swap_used` | integer | Used swap space in bytes |
| `cpu_usage_percent` | integer | CPU usage percentage (0-100) |
| `memory_usage_percent` | integer | Memory usage percentage (0-100) |
| `swap_usage_percent` | integer | Swap usage percentage (0-100) |
| `disk_usage_percent` | integer | Disk usage percentage for project directory (0-100) |
| `load_average_percent` | integer[] | Load average as percentage per CPU core (1/5/15 min) |

#### `projects`

| Field | Type | Description |
|-------|------|-------------|
| `total` | integer | Total number of projects |
| `opened` | integer | Number of projects currently opened |
| `closed` | integer | Number of projects currently closed |

#### `nodes`

| Field | Type | Description |
|-------|------|-------------|
| `total` | integer | Total number of nodes across all projects |
| `open_project_nodes` | integer | Nodes in opened projects (has real status) |
| `closed_project_nodes` | integer | Nodes in closed projects (loaded from topology JSON, no status) |
| `by_type` | object | Node count grouped by node type (qemu, docker, dynamips, etc.) |
| `by_status` | object | Node count grouped by status (only for `open_project_nodes`) |

**Note on `by_status`:** Status is a runtime attribute only available for nodes in opened projects. Closed projects store topology data in JSON format which does not include runtime status. Therefore `by_status` only reflects nodes from opened projects.

Valid node statuses: `started`, `stopped`, `suspended`

#### `links`

| Field | Type | Description |
|-------|------|-------------|
| `total` | integer | Total number of links across all projects |
| `capturing` | integer | Number of links currently capturing packets |

#### `webwireshark`

Web Wireshark container statistics for monitoring packet capture sessions.

| Field | Type | Description |
|-------|------|-------------|
| `total_containers` | integer | Total number of Web Wireshark containers |
| `running_containers` | integer | Number of containers currently running |
| `active_sessions` | integer | Total active packet capture sessions across all containers |
| `containers` | array | Array of container details |

#### `webwireshark.containers[]`

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | string | Project UUID |
| `project_name` | string | Project name |
| `container_id` | string | Docker container ID (truncated to 12 chars) |
| `status` | string | Container status (running, exited, etc.) |
| `running` | boolean | Whether container is running |
| `active_sessions` | integer | Number of active capture sessions in this project |
| `memory` | string | Memory usage (e.g., "272.5MiB / 4GiB") |
| `cpu` | string | CPU usage percentage (e.g., "0.23%") |
| `pids` | integer | Number of processes in container |

### Example Usage

```bash
# Get statistics
curl -X GET http://localhost:3080/v3/statistics \
  -H "Authorization: Bearer <token>"
```

### Dashboard Integration

This API is designed for monitoring dashboards that need:

- **System health**: CPU, memory, disk from `computes[].statistics`
- **Project overview**: Project counts from `projects`
- **Node inventory**: Node counts by type and status from `nodes`
- **Capture monitoring**: Active capture sessions from `links.capturing`
- **Web Wireshark**: Container status and resource usage from `webwireshark`

### Error Responses

| Status | Description |
|--------|-------------|
| 401 | Unauthorized - invalid or missing session |
| 500 | Internal server error |

### Future Optimizations

#### Per-Compose Node Statistics

Currently `nodes` are aggregated globally. Future enhancement could add per-compute breakdown:

```json
"nodes": {
  "total": 42,
  "by_compute": {
    "local": {
      "total": 30,
      "open_project_nodes": 20,
      "closed_project_nodes": 10,
      "by_type": { "qemu": 20, "docker": 10 }
    },
    "remote-server-1": {
      "total": 12,
      "open_project_nodes": 10,
      "closed_project_nodes": 2,
      "by_type": { "docker": 12 }
    }
  },
  "by_type": { "qemu": 20, "docker": 22 },
  "open_project_nodes": 30,
  "closed_project_nodes": 12,
  "by_type": { "qemu": 20, "docker": 22 },
  "by_status": { "started": 25, "stopped": 12, "suspended": 5 }
}
```

This requires tracking which compute each node runs on (Node._compute).
