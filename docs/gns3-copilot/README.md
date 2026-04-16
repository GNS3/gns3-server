<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# GNS3 AI Copilot Documentation

This directory contains design documentation, implementation guides, and future plans for the GNS3 AI Copilot feature.

## Directory Structure

```
docs/gns3-copilot/
├── README.md                               # This file
├── template-based-configuration-roadmap.md # Future: Template-based config with HITL
└── implemented/                            # Implemented features and designs
    ├── chat-api.md                        # Chat API design (SSE, session management)
    ├── llm-model-configs.md               # LLM model configuration system
    ├── command-security.md                # Command security and filtering
    ├── context-window-management.md       # Context window optimization
    ├── node-control-tools.md              # Node start/stop/suspend tools for lab automation
    └── multi-vendor-device-support.md     # Multi-vendor device support (Cisco, Huawei)
```

## Implemented Features

### Chat API (`implemented/chat-api.md`)
The core Chat API that enables AI-powered conversations within GNS3 projects.

**Key Features:**
- Server-Sent Events (SSE) for streaming responses
- Project-level session isolation
- Session management (CRUD operations)
- Statistics tracking (messages, tokens, LLM calls)
- User-level LLM configuration

**Status:** ✅ Implemented

### LLM Model Configs (`implemented/llm-model-configs.md`)
Multi-level LLM model configuration system.

**Key Features:**
- System-wide defaults
- Group-level configurations
- User-level overrides
- Runtime parameter adjustment
- Model provider abstraction

**Status:** ✅ Implemented

### Command Security (`implemented/command-security.md`)
Security framework for AI-generated commands.

**Key Features:**
- Command filtering and validation
- Dangerous operation detection
- HITL (Human-in-the-Loop) confirmations
- Audit logging

**Status:** ✅ Implemented

### Context Window Management (`implemented/context-window-management.md`)
Optimization strategies for handling large project contexts.

**Key Features:**
- Intelligent content filtering
- Token usage optimization
- Summary generation
- Context compression

**Status:** ✅ Implemented

### Node Control Tools (`implemented/node-control-tools.md`)
Tools for controlling network device lifecycle in GNS3 projects.

**Key Features:**
- Start nodes with progress tracking
- Quick start for automated workflows
- Stop nodes for lab shutdown
- Batch operations support
- Mode-based access control

**Status:** ✅ Implemented

### Multi-Vendor Device Support (`implemented/multi-vendor-device-support.md`)
Multi-vendor network device support with custom Netmiko drivers for Huawei, Ruijie, and VPCS devices.

**Key Features:**
- Custom HuaweiTelnetCE driver for Huawei CloudEngine (no authentication)
- Custom RuijieTelnetEnhanced driver for Ruijie OS (interactive command handling)
- Custom VPCSTelnet driver for VPCS simulator (no authentication, ANSI code stripping)
- Cisco IOS Telnet support
- Dynamic device type detection from GNS3 tags
- Unified Nornir + Netmiko architecture
- Vendor-specific command handling (VRP system-view, Ruijie interactive prompts, VPCS simple prompts)

**Tested Vendors:**
- Cisco IOS (Telnet)
- Huawei CloudEngine (Telnet, custom driver)
- Ruijie (锐捷) OS (Telnet, custom enhanced driver)
- VPCS (Virtual PC Simulator, Telnet, custom driver)

**Status:** ✅ Implemented

## Future Enhancements

### Template-Based Configuration with HITL (`template-based-configuration-roadmap.md`)
**Status:** 💡 Proposed | **Target:** Next Release

A revolutionary approach to network device configuration using Jinja2 templates with Human-in-the-Loop confirmations.

**Key Features:**
- Three-step HITL workflow (Template → Parameters → Execute)
- 70-80% token savings for multi-device configurations
- Template reusability across projects
- Human review at every critical step
- Configuration preview before execution

**Benefits:**
- Massive token cost reduction
- Enhanced safety through human oversight
- Template library for common configurations
- Multi-vendor support (Cisco, Huawei, H3C, etc.)

**Implementation Timeline:**
- Phase 1: Core MVP (3-5 days) - Basic template workflow
- Phase 2: UX Enhancement (2-3 days) - Review interfaces, preview
- Phase 3: Template Library (2-3 days) - Pre-built templates, caching
- Phase 4: Advanced Features (3-4 days) - Multi-vendor, composition, analytics

See [`template-based-configuration-roadmap.md`](./template-based-configuration-roadmap.md) for complete details.

### Other Proposed Features

- Vision-based Topology Creation: Create network topologies from images/diagrams
- Enhanced HITL Workflows: Advanced confirmation patterns for other operations
- Web UI Enhancements: Improved management interfaces
- Configuration Diff & Comparison: Compare configurations across devices
- Rollback & Undo: Revert configuration changes

## Contributing

When adding new documentation:

1. **Implementation:** Add documentation to `implemented/` when feature is complete
2. **Naming:** Use concise names like `{feature}.md`

## Document Status Legend

| Status | Description |
|--------|-------------|
| ✅ Implemented | Feature is fully implemented and deployed |
| 📋 Design Complete | Design is done, awaiting implementation |
| 🚧 In Progress | Currently being implemented |
| 💡 Proposed | Initial idea or proposal |

## Related Documentation

- [GNS3 Server API Documentation](https://api.gns3.com/)
- [GNS3 Web UI Documentation](https://docs.gns3.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## Quick Links

- **Current Feature Branch:** `feature/ai-copilot-bridge`
- **Main Branch:** `master`
- **Issue Tracker:** [GitHub Issues](https://github.com/GNS3/gns3-server/issues)

---

_Last updated: 2026-03-20_
