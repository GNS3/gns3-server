# Project Open Performance

## Overview

Optimizations to accelerate project opening (`POST /projects/{id}/open`) and node creation for topologies with many nodes and links. The main bottlenecks were sequential link creation, redundant subprocess calls, and SQLite write contention.

## Before vs After

| Scenario | Before | After |
|----------|--------|-------|
| 20 IOU nodes + 20 links (project open) | ~2s | ~1s |
| 40 QEMU nodes creation (MCP batch) | ~40s | ~1-2s |

## Optimizations

### 1. Parallel Link Creation

**File:** `gns3server/controller/project.py`

Links were created sequentially during project loading, each requiring up to 5 HTTP round-trips to the compute. Now uses `Pool(concurrency=100)` for parallel creation.

```python
# Before: sequential loop
for link_data in topology.get("links", []):
    link = await self.add_link(...)
    await link.add_node(...)

# After: parallel Pool
pool = Pool(concurrency=100)
for link_data in topology.get("links", []):
    pool.append(self._create_link_from_topology_data, link_data)
await pool.join()
```

### 2. Batch UDP Port Allocation

**Files:** `gns3server/api/routes/compute/compute.py`, `gns3server/controller/project.py`, `gns3server/controller/udp_link.py`

During project loading, all required UDP ports are pre-allocated per compute in a single batch call before link creation begins. `UDPLink.create()` checks the pre-allocated pool first, falling back to individual allocation if unavailable.

```python
# New batch endpoint
POST /projects/{id}/ports/udp/batch  →  {"count": N}  →  {"udp_ports": [...]}
```

### 3. IOU Image Subprocess Cache

**File:** `gns3server/compute/iou/iou_vm.py`

Each IOU VM creation spawned `ld-linux --verify` and `iou-image -h` subprocesses. With 20 nodes using the same image, this ran 40 redundant subprocesses. Now results are cached per image path at the class level.

```python
# Class-level caches shared across all instances
IOUVM._loader_cache = {}           # image path → loader command
IOUVM._default_values_cache = {}   # image path → (ram, nvram)
```

Only the first node with a given image runs the subprocesses; subsequent nodes reuse cached values.

### 4. SQLite WAL Mode

**File:** `gns3server/db/tasks.py`

Write-Ahead Logging allows concurrent reads without blocking on writes. The PRAGMA is registered on `engine.sync_engine` instead of the `Engine` class to correctly fire for async engine connections.

```python
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

Without WAL mode, concurrent API requests caused `sqlite3.OperationalError: database is locked`.

### 5. API Key Authentication O(1) Lookup

**Files:** `gns3server/api/routes/controller/api_keys.py`, `gns3server/api/routes/controller/dependencies/authentication.py`

**Old format:** `gns3_<random>` — required scanning ALL keys and running bcrypt on each (O(n)).
**New format:** `gns3_<api_key_id>_<random_secret>` — extract UUID from token, single DB query (O(1)), single bcrypt.

```python
# New auth flow
parts = token.split("_", 2)
key_id = UUID(parts[1])
secret = parts[2]
db_key = await api_keys_repo.get_api_key(key_id)  # O(1) lookup
if await asyncio.to_thread(bcrypt.checkpw, secret.encode(), db_key.key_hash.encode()):
    # Authenticated — 1 query + 1 bcrypt regardless of total key count
```

### 6. bcrypt in Thread Pool

**File:** `gns3server/api/routes/controller/dependencies/authentication.py`

`bcrypt.checkpw()` is CPU-bound (~1.3s per call) and was blocking the async event loop. With 5 API keys and 10 concurrent requests, this caused ~13s delay before any handler could start.

```python
# Before: blocking the event loop
if bcrypt.checkpw(token.encode(), db_key.key_hash.encode()):
    ...

# After: offloaded to thread pool
if await asyncio.to_thread(bcrypt.checkpw, secret.encode(), db_key.key_hash.encode()):
    ...
```

### 7. Concurrency Settings

| Setting | Before | After | File |
|---------|--------|-------|------|
| Node creation Pool | 5 | 100 | `controller/project.py` |
| Link creation Pool | 5 | 100 | `controller/project.py` |
| MCP BATCH_MAX_WORKERS | 10 | 100 | `agent/mcp/nodes.py` |
| MCP HTTP timeout | 10s | 30s | `agent/gns3_copilot/gns3_client/connector.py` |
| HTTP connection pool | 10 (default) | 500/1000 | `agent/gns3_copilot/gns3_client/connector.py` |
| Start nodes Pool | 3 | 3 (unchanged) | `controller/project.py` |

### 8. MCP Auth Returns JWT

**File:** `gns3server/agent/mcp/__init__.py`

When an MCP client connects with an API key, the `_resolve_token` function validates the key then returns a fresh short-lived JWT instead of the raw API key. The JWT is stored in a `ContextVar` and reused for all subsequent tool calls within the same SSE session — zero extra bcrypt.

```python
if user:
    fresh_token = auth_service.create_access_token(user.username)
    return fresh_token  # JWT for subsequent REST API calls
```

## Related Files

| File | Changes |
|------|---------|
| `gns3server/controller/project.py` | Parallel link creation, batch UDP, Pool(100) |
| `gns3server/compute/iou/iou_vm.py` | Image subprocess cache |
| `gns3server/db/tasks.py` | WAL mode + sync_engine event listener |
| `gns3server/api/routes/compute/compute.py` | Batch UDP endpoint |
| `gns3server/controller/udp_link.py` | Pre-allocated port consumption |
| `gns3server/api/routes/controller/api_keys.py` | O(1) key format |
| `gns3server/api/routes/controller/dependencies/authentication.py` | O(1) auth + thread pool bcrypt |
| `gns3server/agent/mcp/__init__.py` | Auth returns JWT, tool enhancements |
| `gns3server/agent/mcp/nodes.py` | fields filter, inherited template_id, name passthrough |
| `gns3server/agent/mcp/links.py` | fields filter, compact array format |
| `gns3server/agent/gns3_copilot/gns3_client/connector.py` | Timeout 30s, connection pool 500/1000 |
| `gns3server/utils/images.py` | md5sum cache error → warning |
