---
name: mcp-service-design
description: MCP (Model Context Protocol) service architecture and tool design for GNS3 server
metadata:
  type: project
---

# MCP (Model Context Protocol) Service Design

## Background

Provide a standard MCP interface for GNS3 Server, allowing AI assistants (Claude Code, Claude Desktop) to interact with GNS3 network simulations through the Model Context Protocol.

## Decision/Implementation

### Transport
- **SSE (Server-Sent Events)** with JWT token authentication
- Endpoint: `/v3/mcp/transport/sse`
- Message endpoint: `/v3/mcp/transport/messages/`

### Authentication
- JWT token obtained via `/v3/access/users/authenticate`
- Two ways to pass token:
  - `Authorization: Bearer <jwt>` header (Claude Code via `-H`)
  - `?token=<jwt>` query param (Claude Desktop, EventSource limitation)
- Token validated using GNS3's existing `auth_service`
- Token stored in `contextvars.ContextVar` for per-session isolation
- Python ≥ 3.9 `asyncio.to_thread` propagates contextvars to threads

### Architecture
```
Claude Code / Desktop → SSE → Auth Wrapper → FastMCP Server → Tool Handler → Gns3Connector → GNS3 REST API
```

### Tool Organization
Tools are separated by domain into individual files under `gns3server/api/routes/mcp/`:

| File | Domain | Tool Count |
|------|--------|:----------:|
| `projects.py` | Project CRUD, open/close/stats | 7 |
| `nodes.py` | Node CRUD, start/stop/reload/suspend, console WS | 10 |
| `links.py` | Link CRUD | 5 |
| `templates.py` | Template CRUD | 5 |
| `computes.py` | Compute list/get/images | 3 |

**Total: 30 tools**

### Handler Pattern
- Synchronous functions receiving `(params: dict, gns3_ctx: dict)`
- Run via `asyncio.to_thread()` to avoid blocking the event loop
- `gns3_ctx` contains `server_url` and `jwt_token`
- `Gns3Connector` is created per-handler from `gns3_client.connector` (per-handler instantiation keeps each tool call isolated)

### Token Lifetime
- Default: 1440 minutes (24 hours)
- Configurable via `jwt_access_token_expire_minutes` in `gns3_server.conf`

## Rationale
- **Why not Direct Controller calls**: MCP layer calls GNS3's own REST API through Gns3Connector, keeping full decoupling and supporting future multi-user/multi-instance scenarios
- **Why not Streamable HTTP**: Claude Code supports SSE natively via `--transport sse` with custom headers; Streamable HTTP session manager lifecycle conflicts with FastAPI mount
- **Why not stdio**: stdio is local-only; SSE supports both local and remote deployments

## Related Files
- `gns3server/agent/mcp/__init__.py` — FastMCP server, `@mcp.tool()` decorators, auth wrapper (`_resolve_token` exchanges API keys for JWTs)
- `gns3server/agent/mcp/*.py` — tool handlers for projects/templates/computes/snapshots/drawings/symbols/appliances/images
- `gns3server/agent/gns3_copilot/gns3_client/api_handlers.py` — shared node/link handler layer (single implementation, consumed by both MCP tools and copilot `tools_v2`; tests must patch `_get_connector` HERE, not in mcp modules)
- `gns3server/agent/gns3_copilot/gns3_client/connector.py` — Gns3Connector (JWT auth + http_call only; the old `custom_gns3fy.py` Node/Link/Project wrappers were removed)
- `gns3server/agent/gns3_copilot/gns3_client/project_inventory.py` — nodes/links aggregation feeding the topology context and Nornir inventory

## Configuration

### Claude Code
```bash
claude mcp add --transport sse My_GNS3_Server \
  http://host:3080/v3/mcp/transport/sse \
  -H "Authorization: Bearer <jwt>"
```

### Claude Desktop
```json
{
  "mcpServers": {
    "My_GNS3_Server": {
      "url": "http://host:3080/v3/mcp/transport/sse?token=<jwt>"
    }
  }
}
```
