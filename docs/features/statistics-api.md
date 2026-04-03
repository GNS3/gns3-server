# Statistics API

## `GET /statistics`

Returns aggregated server statistics including compute resources, projects, nodes, and links.

**Authentication:** Requires active user session

**Method:** `GET`

**URL:** `http://server:3080/v1/statistics`

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

### Example Usage

```bash
# Get statistics
curl -X GET http://localhost:3080/v1/statistics \
  -H "Authorization: Bearer <token>"
```

### Dashboard Integration

This API is designed for monitoring dashboards that need:

- **System health**: CPU, memory, disk from `computes[].statistics`
- **Project overview**: Project counts from `projects`
- **Node inventory**: Node counts by type and status from `nodes`
- **Capture monitoring**: Active capture sessions from `links.capturing`

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
