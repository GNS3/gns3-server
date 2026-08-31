# GNS3 Server Project Memory

> **Note**: This directory stores important project-related memories and case studies, managed with the code repository.
>
> **How to record**: Use the `/memory` skill to record important information to the project memory directory.

## Quick Reference
- **Memory directory**: `.claude/memory/`
- **Skill file**: `.claude/skills/memory/SKILL.md`
- **Main index**: `MEMORY.md` (this file)

## Topics

### Web Wireshark Integration
- **[JWT Token Flow](./web-wireshark-jwt-token-flow.md)** - JWT token transmission path in Web Wireshark
  - Key point: UDPLink only passes through jwt_token, ultimately used by curl command inside Web Wireshark container to authenticate with GNS3 capture stream API
- **[Xpra HTML5 Client](./xpra-html5-client.md)** - Xpra HTML5 client menu control parameters for customizing the web interface

### RBAC & User Isolation
- **[RBAC User Isolation Design](./rbac-user-isolation-design.md)** — Three-step permission check design: ACE batch check → created_by filtering → resource pools

### Appliance Management
- **[GNS3 Appliance Loading](./gns3-appliance-loading.md)** - How GNS3 loads appliance files from builtin and custom directories with priority rules

### uBridge Permission
- **[uBridge Permission Issue](./gns3-ubridge-permission.md)** - Docker containers fail to start due to missing CAP_NET_ADMIN/CAP_NET_RAW capabilities on uBridge
- **[Docker iptables FORWARD blocks bridge](./docker-iptables-forward-bridge.md)** - Docker sets FORWARD chain to DROP, blocking kernel bridge forwarding; `sudo iptables -P FORWARD ACCEPT` to fix

### Docker Container Stop Delay
- **[Docker Container Stop Delay](./docker-container-stop-delay.md)** - Some containers take ~5s to stop because they don't handle SIGTERM (AlpiNet, OstinatoWireshark)

### Device Console / Copilot Known Bugs
- **[XRd Console --More-- Pager Bug](./xrd-console-more-pager-bug.md)** - FIXED: root cause was our own 80x24 initial PTY geometry for the docker_exec console (the XR pager reads PTY rows, not `terminal length`); initial geometry is now 511x10000. Copilot reconnect-before-retry + session_log still open; `--More--` auto-answer kept as fallback design

### MCP Service
- **[MCP Service Design](./mcp-service-design.md)** - MCP (Model Context Protocol) service architecture using FastMCP with SSE transport, JWT auth, 29 tools across 5 domains
- **[MCP Tool Description Location](./mcp-tool-description-guide.md)** - Where to define MCP tool descriptions: in `@mcp.tool()` functions in `__init__.py`, not in `*_TOOLS` arrays

### Python Code Verification
- **[Import Validation](./python-import-validation.md)** - Use actual module imports (`python -c "from ... import ..."`) instead of `py_compile` to catch missing imports
