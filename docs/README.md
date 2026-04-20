<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.

# GNS3 Server Documentation

---

## License

This documentation is licensed under the **Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0)**.

⚠️ **Important - ShareAlike Requirement**: If you create derivative works based on this documentation (including software that incorporates substantial portions of the documentation), your work must also be licensed under **CC BY-SA 4.0 or a compatible license** (such as GPLv3).

- 📄 **Full License Text**: See [docs/LICENSE](./LICENSE)
- 🔗 **License URL**: https://creativecommons.org/licenses/by-sa/4.0/
- 📖 **Compatibility**: https://creativecommons.org/compatiblelicenses

**Dual License Structure**:
- 📚 **Documentation**: CC BY-SA 4.0 (this directory)
- 💻 **Software Code**: GPLv3 (see root [LICENSE](../LICENSE))

---

Technical documentation for the GNS3 server project, covering features, AI Copilot, development setup, and known issues.

## Directory Structure

```
docs/
├── README.md                                    # This file
├── development-setup.md                         # Ubuntu 24.04 development environment setup
├── openapi.json                                 # OpenAPI specification
├── features/                                    # Feature documentation
│   ├── compute-controller-setup.md              # Controller + Compute architecture & configuration
│   ├── statistics-api.md                        # Aggregated statistics API for monitoring
│   ├── vnc-websocket-console.md                 # Browser-based VNC console via WebSocket
│   └── web-wireshark-business-process.md        # Web Wireshark (Docker + xpra packet capture)
├── gns3-copilot/                                # AI Copilot feature documentation
│   ├── netmiko_devices.md                       # Netmiko supported devices (366 types)
│   ├── template-based-configuration-roadmap.md  # Future: template-based config with HITL
│   └── implemented/                             # Implemented features
│       ├── chat-api.md                          # Chat API (SSE, session management)
│       ├── llm-model-configs.md                 # LLM model configuration system
│       ├── command-security.md                  # Command security and filtering
│       ├── context-window-management.md         # Context window optimization
│       ├── node-control-tools.md                # Node start/stop/suspend tools
│       └── multi-vendor-device-support.md       # Multi-vendor device support
└── bugs/                                        # Known issues & bug reports
    └── telnet-server-connection-race-condition.md
```

---

## Features

### Controller + Compute Setup (`features/compute-controller-setup.md`)
Architecture and minimum configuration for setting up GNS3 Controller with remote Compute nodes. Covers compute node config, controller registration, and multi-compute deployment.

### Statistics API (`features/statistics-api.md`)
Aggregated server statistics API (`GET /v3/statistics`) for monitoring dashboards. Collects compute resources, project/node/link counts, and Web Wireshark container status in a single request.

### VNC WebSocket Console (`features/vnc-websocket-console.md`)
Browser-based VNC console access via WebSocket. The Controller acts as WebSocket-to-WebSocket relay, and Compute bridges WebSocket to TCP for QEMU/Docker VMs. Supports noVNC clients.

### Web Wireshark (`features/web-wireshark-business-process.md`)
Web-based packet capture analysis using Docker + xpra HTML5 client. Zero-install Wireshark experience directly in the browser, integrated with GNS3 topologies.

---

## GNS3 AI Copilot (`gns3-copilot/`)

### Implemented Features

| Feature | Description | Status |
|---------|-------------|--------|
| [Chat API](gns3-copilot/implemented/chat-api.md) | SSE streaming, session management, token statistics | Implemented |
| [LLM Model Configs](gns3-copilot/implemented/llm-model-configs.md) | Multi-level model config (system/group/user) | Implemented |
| [Command Security](gns3-copilot/implemented/command-security.md) | Command filtering, dangerous operation detection, HITL | Implemented |
| [Context Window Management](gns3-copilot/implemented/context-window-management.md) | Token optimization, content filtering, compression | Implemented |
| [Node Control Tools](gns3-copilot/implemented/node-control-tools.md) | Start/stop/suspend with batch ops and progress tracking | Implemented |
| [Multi-Vendor Support](gns3-copilot/implemented/multi-vendor-device-support.md) | Cisco, Huawei, Ruijie, VPCS with custom Netmiko drivers | Implemented |

### Reference

- [Netmiko Supported Devices](gns3-copilot/netmiko_devices.md) — 366 device types (154 SSH, 55 Telnet, 3 custom GNS3 drivers)

### Roadmap

- [Template-Based Configuration with HITL](gns3-copilot/template-based-configuration-roadmap.md) — Jinja2 templates with human-in-the-loop confirmations for device configuration and node creation

---

## Known Issues (`bugs/`)

- [Telnet Server Connection Race Condition](bugs/telnet-server-connection-race-condition.md) — `getpeername()` error when client disconnects during connection setup (High severity, Open)

---

## Development Setup (`development-setup.md`)

Quick-start guide for Ubuntu 24.04: install via PPA, set up dependencies, and run gns3-server from source.

---

## Related Documentation

- [GNS3 Server API Documentation](https://api.gns3.com/) — Interactive API docs (also available locally via `redoc.html`)
- [GNS3 Web UI Documentation](https://docs.gns3.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)

---

_Last updated: 2026-04-20_
