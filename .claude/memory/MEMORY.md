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
