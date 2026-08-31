---
name: gns3-api-testing
description: Use this skill when testing GNS3 server REST API endpoints with curl — covers JWT auth, common patterns, and marker/link examples.
version: 1.0.0
---

# GNS3 Server API Testing with curl

## Core Principle

Fixed routine for testing the GNS3 server API: **get a JWT token first, then send `Authorization: Bearer <token>` with every request.**
Default address `http://127.0.0.1:3080`, API prefix `/v3`.

---

## Authentication (always first)

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:3080/v3/access/users/authenticate \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

Persist to a file for reuse (avoids re-logging in each time):

```bash
echo "$TOKEN" > /tmp/gns3_token.txt
TOKEN=$(cat /tmp/gns3_token.txt)
```

Then attach to every request:
```bash
AUTH="Authorization: Bearer $TOKEN"
curl -s -H "$AUTH" http://127.0.0.1:3080/v3/...
```

> **Endpoint note**: login is `/v3/access/users/authenticate`, **not** `/v3/auth/login`.
> OpenAPI spec is at `/openapi.json` (not `/v3/openapi.json`).

---

## Common Variables

```bash
BASE="http://127.0.0.1:3080/v3"
PID=<project_id>
LID=<link_id>
NID=<node_id>
AUTH="Authorization: Bearer $TOKEN"
```

---

## Generic Request Patterns

### GET (query)
```bash
curl -s -H "$AUTH" $BASE/projects/$PID/links | python3 -m json.tool
```

### POST (create) — with JSON body
```bash
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"foo","bpf":"icmp"}' \
  $BASE/projects/$PID/links/$LID/markers
```

### HTTP status code only (body not needed)
```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X DELETE -H "$AUTH" \
  $BASE/projects/$PID/links/$LID/markers/global-icmp
```

### Extract a field from the response
```bash
LID=$(curl -s -H "$AUTH" -X POST ... | python3 -c "import sys,json; print(json.load(sys.stdin)['link_id'])")
```

---

## Status Code Reference

| Code | Meaning |
|---|---|
| 200 | GET/PUT succeeded |
| 201 | POST created |
| 204 | DELETE succeeded (no body) |
| 401 | Not authenticated (token missing/expired) |
| 404 | Resource not found |
| 409 | Conflict (e.g. per-link edit of an inherited marker) |
| 422 | Schema validation failed (e.g. marker name starting with `global`) |

---

## Marker Cheat Sheet

### Project-level global marker definitions (inheritance)
```bash
# Create a def → fans out to every link automatically
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"icmp","bpf":"icmp","tag":1,"color":"#ff5722"}' \
  $BASE/projects/$PID/marker-definitions

# List all defs + the link_ids each is bound to
curl -s -H "$AUTH" $BASE/projects/$PID/marker-definitions

# Update a def → syncs to every link
curl -s -X PUT -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"bpf":"icmp","tag":99}' \
  $BASE/projects/$PID/marker-definitions/icmp

# Delete a def → removes the inherited marker from every link
curl -s -X DELETE -H "$AUTH" $BASE/projects/$PID/marker-definitions/icmp
```

### Per-link markers
```bash
# List markers on a link
curl -s -H "$AUTH" $BASE/projects/$PID/links/$LID/markers

# Create a private marker (name cannot start with "global")
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"bpf":"tcp port 80"}' \
  $BASE/projects/$PID/links/$LID/markers

# Delete (inherited markers return 409)
curl -s -X DELETE -H "$AUTH" $BASE/projects/$PID/links/$LID/markers/<name>
```

### Project-level aggregation query
```bash
curl -s -H "$AUTH" $BASE/projects/$PID/markers   # all markers across links, flattened
```

---

## Link / Node Cheat Sheet

```bash
# List all links in a project (includes the markers field)
curl -s -H "$AUTH" $BASE/projects/$PID/links

# List nodes (check ports[].link_id to find free ports)
curl -s -H "$AUTH" $BASE/projects/$PID/nodes

# Create a VPCS
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"t1","node_type":"vpcs","compute_id":"local"}' \
  $BASE/projects/$PID/nodes

# Start a node
curl -s -o /dev/null -X POST -H "$AUTH" $BASE/projects/$PID/nodes/$NID/start

# Create a link (both ends: node + adapter/port)
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"nodes\":[{\"node_id\":\"$N1\",\"adapter_number\":0,\"port_number\":0},{\"node_id\":\"$N2\",\"adapter_number\":0,\"port_number\":0}]}" \
  $BASE/projects/$PID/links
```

> **Port occupancy**: VPCS has only one interface (port 0); once linked it cannot connect again.
> Confirm `ports[].link_id` is empty before creating a link; `"Port is already used"` means the port is taken.

---

## Gotchas

- **`POST /links` response may show `markers: []`** — the create response is serialized before the inheritance hook runs.
  The inherited marker is actually applied; check `GET /links/{lid}/markers` or refresh `GET /links` to see it.
- **Restart gns3server after code changes** — the Python process does not hot-reload.
- **Wrap JSON bodies in single quotes** in the shell (double quotes inside); to interpolate a shell variable use `\"$VAR\"`.
- **Pipe long output through `python3 -m json.tool`** to pretty-print; extract fields with `python3 -c "import sys,json; ..."`.
