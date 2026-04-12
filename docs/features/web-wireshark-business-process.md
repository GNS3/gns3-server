# Web Wireshark Feature - Business Process Documentation

## Overview

The **Web Wireshark** feature enables users to run Wireshark packet capture analysis directly in a web browser without requiring a desktop environment or VNC connection. This is achieved through an **xpra** (persistent remote applications) HTML5 client running inside a Docker container.

## Feature Summary

- **Core Capability**: Web-based packet capture visualization using Wireshark
- **Technology Stack**: Docker container + xpra + HTML5 WebSocket proxy
- **Target Users**: Network engineers and students who need to analyze network traffic in GNS3 topologies
- **Key Benefit**: Zero-install, browser-based packet capture analysis

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GNS3 Server                                     │
│                                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────────────────┐│
│  │   Web UI    │───▶│  Controller  │───▶│   Link Controller                ││
│  │  (Browser)  │◀───│              │◀───│   (start_capture, stop_capture)  ││
│  └─────────────┘    └──────────────┘    └─────────────────────────────────┘│
│        │                   │                          │                      │
│        │                   │                          ▼                      │
│        │                   │            ┌───────────────────────────────────┐│
│        │                   │            │  manage_wireshark.py (CLI)        ││
│        │                   │            │  - start / stop / restart         ││
│        │                   │            │  - stop-all / delete-container    ││
│        │                   │            └───────────────────────────────────┘│
│        │                   │                          │                      │
│        │                   │            ┌──────────────┴───────────────┐     │
│        │                   │            │                              │     │
│        │                   │            ▼                              ▼     │
│        │                   │   ┌─────────────────┐      ┌─────────────────┐ │
│        │                   │   │ Docker Client   │      │ WebWireshark    │ │
│        │                   │   │ (HTTP API)      │      │ Manager         │ │
│        │                   │   └─────────────────┘      └─────────────────┘ │
│        │                   │                                     │         │
└────────│───────────────────│─────────────────────────────────────│─────────┘
         │                   │                                     │
         │ WebSocket         │ Docker API                          │ Docker
         │ (xpra proxy)      │ (Unix Socket)                        │ Protocol
         ▼                   ▼                                     ▼
┌─────────────────┐  /var/run/docker.sock                  ┌─────────────────────┐
│  Client Browser │◀──────────────────────────────────────▶│  Docker Daemon      │
│  (HTML5 Client) │        WebSocket Proxy                  │                     │
└─────────────────┘                                        │  ┌───────────────┐  │
                                                             │  │ gns3-wireshark│  │
                                                             │  │ -PROJECT_ID   │  │
                                                             │  │               │  │
                                                             │  │ [xpra server] │  │
                                                             │  │ [Xvfb]        │  │
                                                             │  │ [Wireshark]   │  │
                                                             │  └───────────────┘  │
                                                             └─────────────────────┘
```

---

## Component Description

### 1. Web UI (Client Browser)
- User interface for starting/stopping packet capture
- Receives WebSocket URL for connecting to xpra HTML5 client
- No plugins required - pure HTML5/JavaScript

### 2. GNS3 Controller
- Orchestrates the capture workflow
- Validates user permissions (RBAC)
- Manages link capture state

### 3. manage_wireshark.py (Management CLI)
- Command-line interface for container and session management
- Handles Docker container lifecycle
- Manages xpra sessions per link

### 4. WebWiresharkManager
- Core business logic for Web Wireshark
- Handles container creation, session startup/shutdown
- Deterministic port allocation based on link_id

### 5. DockerHTTPClient
- Async HTTP client for Docker API
- Communicates via Unix socket (/var/run/docker.sock)
- Manages container lifecycle

### 6. Docker Container (gns3-wireshark-{project_id})
- Runs xpra server with HTML5 support
- Contains Xvfb (virtual framebuffer) for headless Wireshark
- Streams display to browser via WebSocket

---

## Business Processes

### Process 1: Start Packet Capture with Web Wireshark

```
┌─────────┐     ┌────────────┐     ┌──────────────┐     ┌──────────────────┐
│  User   │     │   Web UI   │     │  Controller   │     │ Link Controller  │
└────┬────┘     └─────┬──────┘     └──────┬───────┘     └────────┬─────────┘
     │                │                    │                       │
     │ 1.Start Capture│                    │                       │
     │───────────────▶│                    │                       │
     │                │ 2.Start Capture   │                       │
     │                │───────────────────▶│                       │
     │                │                    │ 3._start_web_wireshark│
     │                │                    │─────────────────────▶│
     │                │                    │                       │
     │                │                    │  4.manage_wireshark.py│
     │                │                    │       start          │
     │                │                    │─────────────────────▶│
     │                │                    │                       │
     │                │                    │                       │ 5.Ensure network
     │                │                    │                       │   exists
     │                │                    │                       │────┐
     │                │                    │                       │    │
     │                │                    │                       │◀───┘
     │                │                    │                       │
     │                │                    │                       │ 6.Get/create container
     │                │                    │                       │────┐
     │                │                    │                       │    │
     │                │                    │                       │◀───┘
     │                │                    │                       │
     │                │                    │                       │ 7.Start xpra session
     │                │                    │                       │   (display + port)
     │                │                    │                       │────┐
     │                │                    │                       │    │
     │                │                    │                       │◀───┘
     │                │                    │                       │
     │                │                    │                       │ 8.Start Wireshark
     │                │                    │                       │   (background)
     │                │                    │                       │────┐
     │                │                    │                       │    │
     │                │                    │                       │◀───┘
     │                │                    │                       │
     │                │                    │◀───────────────────────│
     │ 9.ws_url       │ 10.ws_url          │                       │
     │◀───────────────│◀───────────────────│                       │
     │                │                    │                       │
     │                │ 11.Connect via     │                       │
     │                │    WebSocket       │                       │
     │                │───────────────────│─────────────────────▶│
     │                │                    │                       │ 12.Proxy to container
     │                │                    │                       │────┐
     │                │                    │                       │    │
     │                │◀───────────────────│───────────────────────│◀───┘
     │                │                    │                       │
```

**API Endpoint**: `POST /v3/projects/{project_id}/links/{link_id}/capture/start`

**Request Body**:
```json
{
  "wireshark": true,
  "data_link_type": "DLT_EN10MB",
  "capture_file_name": "capture.pcap"
}
```

**Response**:
```json
{
  "id": "link-uuid",
  "capturing": true,
  "ws_url": "ws://192.168.1.100:14500"
}
```

### Process 2: Container Lifecycle (Per Project)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Project Lifecycle                             │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Project Open │───▶│  First Link  │───▶│  Container   │
│              │    │  Capture     │    │  Created     │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                                │
                    ┌────────────────────────────┼────────────────────────────┐
                    │         Container Running │ (one per project)          │
                    │                            │                             │
                    │  ┌─────────────────────────▼─────────────────────────┐ │
                    │  │                   Architecture                      │ │
                    │  │                                                  │ │
                    │  │  ┌──────────────────────────────────────────────┐  │ │
                    │  │  │         gns3-wireshark-{project_id}         │  │ │
                    │  │  │                                              │  │ │
                    │  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐     │  │ │
                    │  │  │  │ Link 1  │  │ Link 2  │  │ Link N  │     │  │ │
                    │  │  │  │ :10001  │  │ :10002  │  │ :10NNN  │     │  │ │
                    │  │  │  │ xpra    │  │ xpra    │  │ xpra    │     │  │ │
                    │  │  │  │ session │  │ session │  │ session │     │  │ │
                    │  │  │  └────┬────┘  └────┬────┘  └────┬────┘     │  │ │
                    │  │  │       │            │            │          │  │ │
                    │  │  │       ▼            ▼            ▼          │  │ │
                    │  │  │  ┌─────────────────────────────────────┐   │  │ │
                    │  │  │  │         Xvfb :1 (virtual display) │   │  │ │
                    │  │  │  │         1920x1080x24              │   │  │ │
                    │  │  │  └─────────────────────────────────────┘   │  │ │
                    │  │  │                                              │  │ │
                    │  │  │  ┌─────────────────────────────────────┐   │  │ │
                    │  │  │  │         Wireshark (per link)        │   │  │ │
                    │  │  │  │         Reads pcap stream           │   │  │ │
                    │  │  │  │         Displays in window          │   │  │ │
                    │  │  │  └─────────────────────────────────────┘   │  │ │
                    │  │  └──────────────────────────────────────────────┘  │ │
                    │  └──────────────────────────────────────────────────────┘ │
                    │                                                             │
                    │  Each xpra session:                                        │
                    │  - Binds to unique port (10000-19999, based on link_id)   │
                    │  - Provides HTML5 access via WebSocket                      │
                    │  - Runs Wireshark with curl-piped pcap stream             │
                    │                                                             │
                    └─────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Project Close│───▶│ Stop All     │───▶│  Container   │
│              │    │  Sessions    │    │  Stopped     │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                                │
                    ┌────────────────────────────┼────────────────────────────┐
                    │  Container Stopped         │ (preserved for reuse)       │
                    │  Sessions Cleaned          │                             │
                    └───────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Project      │───▶│ Delete       │───▶│  Container   │
│ Deleted      │    │  Container   │    │  Removed     │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Process 3: WebSocket Connection Flow

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────────┐
│ Client      │     │  GNS3 Server     │     │  Docker Container   │
│ Browser     │     │  (API Route)     │     │  (xpra server)      │
└──────┬──────┘     └────────┬─────────┘     └──────────┬─────────┘
       │                      │                           │
       │ 1.WSS Connect        │                           │
       │ w/ JWT token         │                           │
       │─────────────────────▶│                           │
       │                      │                           │
       │                      │ 2.Validate JWT            │
       │                      │ (RBAC: Link.Capture)       │
       │                      │────┐                       │
       │                      │    │                       │
       │                      │◀───┘                       │
       │                      │                           │
       │                      │ 3.Get container IP        │
       │                      │ from Docker API            │
       │                      │────┐                      │
       │                      │    │                      │
       │                      │◀───┘                      │
       │                      │                           │
       │ 4.Accept connection  │                           │
       │◀─────────────────────│                           │
       │                      │                           │
       │ 5.Start WebSocket    │                           │
       │    proxy             │                           │
       │                      │                           │
       │                      │ 6.Connect to xpra         │
       │                      │    ws://container:port     │
       │                      │─────────────────────────▶│
       │                      │                           │
       │                      │ 7.xpra validates          │
       │                      │    subprotocol            │
       │                      │◀─────────────────────────│
       │                      │                           │
       │ 8.Bidirectional      │ 9.Proxy data             │
       │    WebSocket         │─────────────────────────▶│
       │◀═════════════════════│◀══════════════════════════│
       │                      │                           │
       │ 10.HTML5 client      │                           │
       │     renders          │                           │
       │     Wireshark        │                           │
       │     window           │                           │
       │                      │                           │
```

**WebSocket Endpoint**: `ws://host/v3/projects/{project_id}/links/{link_id}/capture/web-wireshark?token=<jwt_token>`

### Process 4: Capture Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Packet Capture Flow                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  GNS3 Node   │         │   Compute    │         │   Link       │
│  (Router/    │────────▶│   Node       │────────▶│   Capture    │
│   Switch)    │  TAP    │              │  pcap   │   Buffer     │
└──────────────┘         └──────────────┘         └──────┬───────┘
                                                         │
                                                         │ pcap stream
                                                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        GNS3 Server                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ API Route: GET /v3/projects/{id}/links/{id}/capture/stream            │ │
│  │                                                                         │ │
│  │ Proxies pcap stream from compute node to:                              │ │
│  │   - Docker container (for live Wireshark analysis)                     │ │
│  │   - Download endpoint (for file export)                                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
                              │ curl -N -H "Authorization: Bearer {jwt}"
                              │   '{server}/v3/projects/{id}/links/{id}/capture/stream'
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     Docker Container (gns3-wireshark-{project_id})           │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  bash (curl)                                                         │   │
│  │    │                                                                │   │
│  │    │ reads pcap stream                                              │   │
│  │    ▼                                                                │   │
│  │  ┌──────────────────────────────────────────────────────────────┐  │   │
│  │  │ wireshark -i - -k                                              │  │   │
│  │  │     │                                                         │  │   │
│  │  │     │ reads from stdin (-)                                    │  │   │
│  │  │     │ parses PCAP packets                                     │  │   │
│  │  │     ▼                                                         │  │   │
│  │  │  ┌────────────────────────────────────────────────────────┐   │  │   │
│  │  │  │ Xvfb :display (virtual X11 framebuffer)              │   │  │   │
│  │  │  │     │                                                   │   │  │   │
│  │  │  │     │ renders Wireshark window                         │   │  │   │
│  │  │  │     ▼                                                   │   │  │   │
│  │  │  │  ┌─────────────────────────────────────────────────┐  │   │  │   │
│  │  │  │  │ xpra :display                                    │  │   │  │   │
│  │  │  │  │     │                                            │  │   │  │   │
│  │  │  │  │     │ encodes X11 to HTML5                       │  │   │  │   │
│  │  │  │  │     ▼                                            │  │   │  │   │
│  │  │  │  │  ws://0.0.0.0:{port}                             │  │   │  │   │
│  │  │  │  └─────────────────────────────────────────────────┘  │   │  │   │
│  │  │  └────────────────────────────────────────────────────────┘   │  │   │
│  │  └──────────────────────────────────────────────────────────────────┘   │
│  └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Client Browser                                      │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  HTML5/xpra Client                                                       │ │
│  │    │                                                                    │ │
│  │    │ WebSocket connection                                               │ │
│  │    ▼                                                                    │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │ │
│  │  │  Wireshark Web Interface                                           │   │ │
│  │  │                                                                     │   │ │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │   │ │
│  │  │  │ File     │  │ Edit     │  │ View     │  │ Capture          │   │   │ │
│  │  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘   │   │ │
│  │  │                                                                     │   │ │
│  │  │  ┌─────────────────────────────────────────────────────────────┐   │   │ │
│  │  │  │ Packet List          │ Packet Details                       │   │   │ │
│  │  │  │ ─────────────────────┼─────────────────────────────────────│   │   │ │
│  │  │  │ No. Time    Source   │ Frame: 74 bytes on wire...          │   │   │ │
│  │  │  │ 1   0.000  10.0.0.1 │ Ethernet II, Src: Cisco_00:01:00... │   │   │ │
│  │  │  │ 2   0.001  10.0.0.2 │ Internet Protocol Version 4...     │   │   │ │
│  │  │  │ 3   0.002  10.0.0.1 │ ...                                 │   │   │ │
│  │  │  └─────────────────────────────────────────────────────────────┘   │   │ │
│  │  │                                                                     │   │ │
│  │  │  ┌─────────────────────────────────────────────────────────────┐   │   │ │
│  │  │  │ Packet Bytes                                                │   │   │ │
│  │  │  │ 0000  00 00 00 00 00 01 00 00 00 00 00 02 08 00 45 00 00   │   │   │ │
│  │  │  └─────────────────────────────────────────────────────────────┘   │   │ │
│  │  └──────────────────────────────────────────────────────────────────────┘   │
│  └──────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Port Allocation Strategy

### Deterministic Port Mapping

```
┌─────────────────────────────────────────────────────────────────┐
│              link_id_to_port(link_id)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   port = 10000 + (hash(link_id) % 10000)                        │
│                                                                  │
│   Result: 10000 - 19999                                          │
│                                                                  │
│   Example:                                                       │
│   ┌────────────────────────────────────────────────────────────┐ │
│   │ link_id                              │ port               │ │
│   ├────────────────────────────────────────────────────────────┤ │
│   │ f233f27f-7432-49c3-9aa2-50e326a10eec │ 14503               │ │
│   │ a1b2c3d4-1234-5678-90ab-cdef12345678 │ 11024               │ │
│   │ 12345678-90ab-cdef-1234-567890abcdef │ 17892               │ │
│   └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Benefits**:
- Same link always gets same port (deterministic)
- No port conflicts between sessions
- Easy to predict and debug

---

## Network Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Docker Network Setup                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  Host Machine                                                              │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  Docker Bridge Network: gns3-wireshark                             │  │
│  │  Subnet: 172.31.0.0/22 (configurable)                              │  │
│  │                                                                        │  │
│  │  ┌──────────────────────────────────────────────────────────────┐   │  │
│  │  │ Gateway: 172.31.0.1                                           │   │  │
│  │  │                                                              │   │  │
│  │  │  ┌────────────────────────────────────────────────────────┐  │   │  │
│  │  │  │ Container: gns3-wireshark-{project_id}               │  │   │  │
│  │  │  │ IP: 172.31.0.x (DHCP assigned)                        │  │   │  │
│  │  │  │                                                      │  │   │  │
│  │  │  │ Ports exposed:                                        │  │   │  │
│  │  │  │   :14501 -> xpra session for link 1                   │  │   │  │
│  │  │  │   :14502 -> xpra session for link 2                   │  │   │  │
│  │  │  │   :14503 -> xpra session for link 3                   │  │   │  │
│  │  │  │   ...                                                 │  │   │  │
│  │  │  └────────────────────────────────────────────────────────┘  │   │  │
│  │  └──────────────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  DockerNAT/Host: 192.168.1.100 (GNS3 Server)                      │  │
│  │                                                                        │  │
│  │  WebSocket Proxy forwards:                                          │  │
│  │    client --ws--> 192.168.1.100:3080 --proxy--> 172.31.0.x:{port}   │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Session Management Commands

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    manage_wireshark.py Commands                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  start                                                                     │
│  ─────                                                                     │
│  Starts Web Wireshark session for a specific link                           │
│                                                                              │
│  Arguments:                                                                 │
│    --project-id     Project UUID (required)                                 │
│    --link-id        Link UUID (required)                                    │
│    --jwt-token      JWT authentication token (required)                     │
│    --capture-url    PCAP stream URL (auto-detected if not provided)         │
│    --image          Docker image (default: gns3/web-wireshark:latest)        │
│    --memory         Memory limit (default: 2g)                               │
│    --cpus           CPU cores (default: 1.0)                                │
│    --pids-limit     Process limit (default: 1000)                            │
│                                                                              │
│  Example:                                                                   │
│    python manage_wireshark.py start \                                        │
│      --project-id "5af0fe00-..." \                                          │
│      --link-id "f233f27f-..." \                                            │
│      --jwt-token "eyJhbG..."                                                │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  stop                                                                      │
│  ────                                                                      │
│  Stops Web Wireshark session for a specific link                            │
│                                                                              │
│  Arguments:                                                                 │
│    --project-id     Project UUID (required)                                 │
│    --link-id        Link UUID (required)                                    │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  restart                                                                   │
│  ──────                                                                    │
│  Restarts Web Wireshark session (reopens Wireshark window)                  │
│  Used when user accidentally closes the Wireshark window                    │
│                                                                              │
│  Arguments:                                                                 │
│    --project-id     Project UUID (required)                                 │
│    --link-id        Link UUID (required)                                    │
│    --jwt-token      JWT authentication token (required)                     │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  stop-all                                                                  │
│  ────────                                                                  │
│  Stops all Web Wireshark sessions for a project                             │
│  Called when project is closed                                              │
│                                                                              │
│  Arguments:                                                                 │
│    --project-id     Project UUID (required)                                 │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  stop-container                                                            │
│  ─────────────                                                              │
│  Stops the Docker container (without deleting)                              │
│  Called when project is closed                                              │
│                                                                              │
│  Arguments:                                                                 │
│    --project-id     Project UUID (required)                               │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  delete-container                                                           │
│  ────────────────                                                            │
│  Deletes the Docker container                                                │
│  Called when project is deleted                                              │
│                                                                              │
│  Arguments:                                                                 │
│    --project-id     Project UUID (required)                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Close/Delete Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Project Lifecycle Events                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────┐
│    Project Close       │
└───────────┬────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         Step 1: Stop All Sessions                            │
│                                                                            │
│  Called: _cleanup_web_wireshark_xpra_sessions()                            │
│                                                                            │
│  Action:                                                                   │
│    - Execute: manage_wireshark.py stop-all --project-id {id}               │
│    - Kills all xpra, Xvfb, and Wireshark processes for the project          │
│    - Container remains running                                               │
│                                                                            │
│  Reason:                                                                   │
│    - Preserves container for quick reuse if project is reopened            │
│    - Frees memory by stopping processes                                     │
└────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         Step 2: Stop Container                               │
│                                                                            │
│  Called: _stop_web_wireshark_container()                                   │
│                                                                            │
│  Action:                                                                   │
│    - Execute: manage_wireshark.py stop-container --project-id {id}        │
│    - Stops Docker container (docker stop)                                   │
│                                                                            │
│  Reason:                                                                   │
│    - Container will be recreated on next capture start                     │
│    - Frees container resources (memory, processes)                         │
└────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────┐
│    Project Reopened    │
└───────────┬────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         On First Capture Start                              │
│                                                                            │
│  Action:                                                                   │
│    - Container is started (docker start)                                   │
│    - New xpra sessions created as needed                                    │
│                                                                            │
│  Benefit:                                                                  │
│    - Faster subsequent captures (container already exists)                  │
└────────────────────────────────────────────────────────────────────────────┘


┌────────────────────────┐
│   Project Delete       │
└───────────┬────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         Delete Container                                    │
│                                                                            │
│  Called: _cleanup_web_wireshark_container()                                │
│                                                                            │
│  Action:                                                                   │
│    - Execute: manage_wireshark.py delete-container --project-id {id}      │
│    - Stops and removes Docker container                                    │
│    - Resets _web_wireshark_container_created flag                          │
│                                                                            │
│  Reason:                                                                   │
│    - Project is being deleted, container is no longer needed               │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints Summary

| Method | Endpoint | Description | Privilege |
|--------|----------|-------------|-----------|
| POST | `/v3/projects/{id}/links/{id}/capture/start` | Start capture with Web Wireshark | Link.Capture |
| POST | `/v3/projects/{id}/links/{id}/capture/stop` | Stop capture | Link.Capture |
| POST | `/v3/projects/{id}/links/{id}/capture/wireshark/restart` | Restart Wireshark window | Link.Capture |
| GET | `/v3/projects/{id}/links/{id}/capture/stream` | Stream PCAP data | Link.Capture |
| GET | `/v3/projects/{id}/links/{id}/capture/file` | Download PCAP file | Link.Capture |
| WS | `/v3/projects/{id}/links/{id}/capture/web-wireshark` | WebSocket proxy for xpra | Link.Capture |

---

## Security Considerations

1. **RBAC Authentication**: All endpoints require `Link.Capture` privilege
2. **JWT Token Validation**: WebSocket connections validate JWT token
3. **WebSocket Subprotocol Negotiation**: Proper xpra subprotocol handling
4. **Container Isolation**: Each project gets its own container with isolated resources
5. **Network Segmentation**: Container runs on isolated Docker network (not host network)

---

## Performance Characteristics

### Startup & Shutdown Performance

| Step | Before Optimization | After Optimization | Improvement |
|------|---------------------|-------------------|-------------|
| **Health Check** | ~1.0s | ~0s | Docker native status |
| **Gateway Detection** | 0.85s | ~0.001s | Docker API vs exec |
| **Process Cleanup** | ~850ms | ~40ms | Host perspective recursive tree walk |
| **Xpra Startup** | 6.4s | ~3s | HTML5 client disabled |
| **Wireshark Launch** | ~1s | ~1s | No change |
| **Total Startup** | **~15s** | **~5-6s** | **67% faster** |

| Step | Before Optimization | After Optimization | Improvement |
|------|---------------------|-------------------|-------------|
| **Process Termination** | ~8s | ~20-40ms | Recursive tree walk, no orphans |
| **File Cleanup** | ~850ms | ~850ms | Docker exec (safety) |
| **Total Shutdown** | **~9s** | **~2s** | **78% faster** |

#### Startup Breakdown: First vs Subsequent

| Phase | First Startup (Container stopped) | Subsequent Startup (Container running) |
|-------|-----------------------------------|----------------------------------------|
| Container startup | ~1-2s | ~0s (already running) |
| Container health check | ~1s (unhealthy→healthy) | ~0s (already healthy) |
| Gateway detection | ~0.001s | ~0.001s |
| Process cleanup | ~40ms | ~40ms |
| Xpra startup | ~3s | ~3s |
| Wireshark launch | ~1s | ~1s |
| **Total** | **~6s** | **~5s** |

#### Measured Performance Data

**Startup (from production logs):**
```
13:46:53 → 13:46:59 = 6s (first startup with container start)
13:47:38 → 13:47:43 = 5s (subsequent startup, container running)
```

**Shutdown (from production logs):**
```
13:48:15 → 13:48:17 = 2s (complete cleanup, no orphan processes)
13:48:50 → 13:48:52 = 2s (complete cleanup, no orphan processes)
```

#### Key Optimizations

- **Complete Process Cleanup**: Recursive process tree traversal eliminates orphaned processes (Xvfb, pulseaudio, ibus-daemon)
- **Fast Gateway Detection**: Docker API query instead of container exec
- **Smart Health Check**: Trust Docker built-in status, no manual ping
- **Xpra Optimization**: Disabled unnecessary HTML5 client (`--html=off`)

### Resource Usage (Per Wireshark Instance)
| Resource | Typical Usage |
|----------|---------------|
| Memory | 150-250 MB |
| CPU | 0.5-2% (idle to active) |
| Threads | ~30 threads |
| Disk I/O | Minimal |

### Container Configuration
| Parameter | Default | Recommended |
|-----------|---------|-------------|
| Memory | 2GB | 2-4GB |
| CPUs | 1.0 | 1.0-2.0 |
| PIDs Limit | 1000 | 1000 |

### Scaling Guidelines
| Instances | Memory | Use Case |
|-----------|--------|----------|
| 1-3 | 450-750 MB | Light projects |
| 4-6 | 600-1.5 GB | Medium projects |
| 7-10 | 1-2.5 GB | Large projects |
| 10+ | >2.5 GB | Increase memory |

---

## Known Limitations

1. **JWT Token Visibility**: Token passed via command-line arguments (visible in `/proc/<pid>/cmdline`)
2. **Single Container**: All Wireshark instances run in a single container per project
3. **Docker Dependency**: Requires Docker daemon running on the server
4. **Browser Support**: Requires modern browser with WebSocket support
5. **Port Range**: Limited to 10,000 unique ports (10000-19999)

---

## File Structure

```
gns3server/
├── controller/
│   ├── link.py                    # Link capture lifecycle
│   └── project.py                 # Project cleanup hooks
├── api/routes/controller/
│   └── links.py                   # REST/WebSocket API endpoints
└── agent/web_wireshark/
    ├── manage_wireshark.py        # CLI management tool
    ├── manager.py                 # Session management logic
    ├── docker_client.py           # Docker API client
    ├── docker/
    │   └── Dockerfile            # Container image definition
    └── WEB_WIRESHARK.md          # Technical documentation
```
