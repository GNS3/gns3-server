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
