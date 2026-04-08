# Web Wireshark Integration

## Overview

Integrate Wireshark packet capture functionality into GNS3 Web UI, allowing users to view real-time capture data directly in the browser via noVNC.

## Installation

```bash
# Pull Docker image (standalone)
docker pull ghcr.io/gns3/web-wireshark:latest
```

**Module location:** `gns3server/compute/web_wireshark/`

**Note:** This feature is part of gns3server core. No additional Python dependencies required.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  GNS3 Web UI                                             │  │
│   │  - "Start Capture" on a link                            │  │
│   │  - "View in Wireshark" opens noVNC iframe               │  │
│   │  - Receives "ready" event via WebSocket                 │  │
│   └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket (ws://gns3-server:3080)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       GNS3 Server (Port 3080)                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  WiresharkSessionManager                                  │   │
│  │  - DisplayManager: tracks displays per container (:0-:50)│   │
│  │  - Session state: pending → starting → ready → error    │   │
│  │  - ProjectContainerManager: project container lifecycle │   │
│  │  - Docker API: direct container/session management       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Wireshark Container (Project-level)         │   │
│  │  gns3-ws-{project_id}                                    │   │
│  │  - Created when project opens                            │   │
│  │  - Destroyed when project closes                         │   │
│  │  - Contains multiple Wireshark sessions (one per link)  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Inside Container: xpra + noVNC Server (port 10000)     │   │
│  │  - Session dir: /tmp/sessions/link-{uuid}/               │   │
│  │    - token: JWT for capture/stream API                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Linux User Isolation (one user per link_id)            │   │
│  │  link-{uuid-1} ──▶ Xvfb :0 ──▶ wireshark              │   │
│  │  link-{uuid-2} ──▶ Xvfb :1 ──▶ wireshark              │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP (token via file)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        GNS3 Server                              │
│  Capture File Storage: /path/to/projects/{id}/captures/        │
│  Stream API: GET /v3/links/{link_id}/capture/stream          │
└─────────────────────────────────────────────────────────────────┘
```

## Design Principles

- **Distributed Architecture** - Uses GNS3's existing Docker management pattern
- **Project-level container isolation** - One container per project
- **On-demand Wireshark sessions** - Created only when user clicks "View in Wireshark"
- **Docker API direct management** - No Ansible or SSH required
- **Browser only connects to GNS3 Server** - WebSocket proxy handles forwarding
- **Secure token handling** - JWT token stored in session file, not CLI

## Container Lifecycle

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Project opens ──▶ Container starts ──▶ Container running              │
│  Project closes ──▶ Container stops                                       │
│                                                                          │
│  Within Container:                                                       │
│  Session requested ──▶ Session starting ──▶ Session ready                   │
│  Session closed ──▶ Session cleanup                                        │
└──────────────────────────────────────────────────────────────────────────┘
```

## Session State Machine

```
[idle] ──▶ [pending] ──▶ [starting] ──▶ [ready] ──▶ [closing] ──▶ [idle]
                │                │                │
                ▼                ▼                ▼
            User clicks     Docker exec     User views
            View Wireshark  (5-10s)        Wireshark

[idle] ──▶ [error]  (if Docker operation fails)
```

## Data Flow

### 1. Project Opens
```
Project opened → Docker API creates container → Container starts with xpra
```

### 2. Start Capture
```
POST /v3/links/{link_id}/capture/start
  Body: { "wireshark": true }
→ Starts packet capture (existing behavior)
→ Response includes wireshark_ws endpoint
```

### 3. View in Wireshark
```
User clicks "View in Wireshark"
  │
  └─▶ WebSocket /v3/links/{link_id}/capture/wireshark
      │
      ▼
  GNS3 Server:
  - Checks/creates container via Docker API
  - Allocates display :N (DisplayManager)
  - Creates session state: pending
  - Docker exec: create user, write token, start xpra/wireshark
      │
      ▼
  WebSocket sends: {"type": "ready", "display": ":0"}
```

### 4. Frontend Connection
```
Browser receives "ready" → Connects noVNC to xpra via GNS3 Server proxy
```

### 5. Stop View / Project Close
```
Stop View: Docker exec cleanup → Release display → Container stays running
Project Close: Cleanup all sessions → docker stop + rm container
```

## Key Components

### DisplayManager
- Manages X display allocation per container (:0 to :10)
- Each Wireshark session uses one display

### ProjectContainerManager
- Creates/destroys containers via Docker API
- One container per project
- Tracks container state and IP

### WiresharkSessionManager
- Creates/closes sessions via Docker exec
- Tracks session state per link
- Coordinates with DisplayManager

### WebSocket Handler
- Validates JWT token
- Sends state messages (waiting/ready/error)
- Proxies browser to xpra WebSocket

## Security

| Concern | Mitigation |
|---------|------------|
| JWT token in CLI | Token stored in session file, mode 0600 |
| Token visible in `ps aux` | Token file only readable by session user |
| Browser accessing container | All access via GNS3 Server WebSocket proxy |
| Unauthorized WebSocket | JWT validation + link ownership check |
| Resource abuse | cgroups limit memory (2GB) and processes (50) |
| SSH key management | Not required - uses Docker API |

### Trust Model
```
Browser ──▶ GNS3 Server (JWT validated) ──▶ Wireshark Container
              All traffic flows through GNS3 Server proxy
```

## Distributed Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    GNS3 Controller                               │
│         WiresharkSessionManager (coordinates)                    │
└─────────────────────────────────────────────────────────────────┘
                    │
                    │ HTTP API
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│Compute 1│   │Compute 2│   │Compute 3│
│ Docker  │   │ Docker  │   │ Docker  │
│ Manager │   │ Manager │   │ Manager │
└─────────┘   └─────────┘   └─────────┘
```

Each compute node:
- Runs own gns3-server instance
- Has local `/var/run/docker.sock` access
- Manages Wireshark containers via Docker API

## Wireshark Container

### Dockerfile
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y wireshark xpra xvfb curl python3
RUN mkdir -p /tmp/sessions && chmod 1777 /tmp/sessions
COPY start.sh /start.sh
EXPOSE 10000
CMD ["/start.sh"]
```

### start.sh
```bash
#!/bin/bash
xpra start :0 --html=on --bind-tcp=0.0.0.0:10000 --auth=allow --daemonize
tail -f /dev/null
```

### Container Structure
```
/
├── tmp/sessions/link-{uuid}/token   # JWT (0600)
├── usr/bin/wireshark
├── usr/bin/xpra
└── usr/bin/xvfb-run
```

## Local Development & Testing

### Build Container Locally
```bash
cd gns3server/compute/web_wireshark/
docker build -t gns3/web-wireshark:local .
```

### Test Container
```bash
# Run container
docker run -d --name ws-test \
  -p 10000:10000 \
  gns3/web-wireshark:local

# Verify xpra is running
docker exec ws-test ps aux | grep xpra

# Test WebSocket endpoint
curl -s http://localhost:10000
```

### Push to Registry (when ready)
```bash
# Tag for GitHub Container Registry
docker tag gns3/web-wireshark:local ghcr.io/gns3/web-wireshark:latest

# Push
docker push ghcr.io/gns3/web-wireshark:latest
```

## Frontend Integration Guide

### 0. Check System Capabilities (optional)

Before showing Wireshark options, check if the system has required components:

```javascript
// GET /v3/capabilities/web-wireshark
// Response:
{
  "available": true,
  "docker": true,
  "wireshark": true,
  "xpra": true,
  "xvfb": true,
  "missing": []
}

// If available is false, hide Wireshark UI options
```

### 1. Enable Wireshark when starting capture

```javascript
// POST /v3/projects/{project_id}/links/{link_id}/capture/start
{
  "wireshark": true
}
```

**Response includes `wireshark` field:**
```json
{
  "link_id": "xxx",
  "capturing": true,
  "wireshark": true
}
```

### 2. UI Requirements

#### Show "View in Wireshark" button when:
- System has Wireshark capabilities (from step 0)
- `link.capturing === true`
- `link.wireshark === true`

#### Button should:
- Be visible on the link context menu or toolbar
- Open noVNC iframe/modal when clicked

### 3. WebSocket Connection

**Endpoint:**
```
ws://gns3-server:3080/v3/projects/{project_id}/links/{link_id}/capture/wireshark?token={jwt_token}
```

**Authentication:** JWT token via query parameter (same as other GNS3 WebSocket endpoints)

### 4. WebSocket Protocol

#### Server → Client Messages:

**Waiting (session starting):**
```json
{"type": "waiting", "message": "Starting Wireshark..."}
```

**Ready (Wireshark is running):**
```json
{
  "type": "ready",
  "display": ":0",
  "display": ":0"
}
```

**Error:**
```json
{"type": "error", "message": "Failed to start Wireshark"}
```

### 5. noVNC Integration

After receiving `{"type": "ready"}`:

1. Connect to GNS3 Server WebSocket endpoint
2. Use the same WebSocket connection for noVNC RFB protocol
3. Display noVNC in an iframe or modal

### 6. Complete Flow

```
1. User clicks "Start Capture" with Wireshark enabled
   └── POST /capture/start {wireshark: true}

2. User clicks "View in Wireshark"
   └── Connect to WebSocket /capture/wireshark?token=...

3. WebSocket receives:
   └── {type: "waiting", message: "..."}
       └── Show "Starting..." UI

4. WebSocket receives:
   └── {type: "ready", display: ":0"}
       └── Browser uses same WebSocket for VNC protocol
       └── Display Wireshark in browser

5. User closes / stops viewing
   └── WebSocket disconnects
   └── Server stops Wireshark session
```

### 7. noVNC Integration

The browser connects to the same WebSocket endpoint. GNS3 Server proxies the connection to the container's xpra.

```javascript
// Connect to GNS3 Server WebSocket (same endpoint for capture view)
const ws = new WebSocket(
  `ws://gns3-server:3080/v3/projects/${projectId}/links/${linkId}/capture/wireshark?token=${jwtToken}`
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'waiting') {
    // Show "Starting..." UI
  }

  if (msg.type === 'ready') {
    // msg.display contains the X display number
    // WebSocket is now proxied to xpra - use with noVNC
    const rfb = new RFB(ws, 'Wireshark');
    rfb.connect();
  }
};
```

## API Reference

### 1. Check Capabilities

Check if the system supports Web Wireshark.

```http
GET /v3/capabilities/web-wireshark
```

**Request:**
```
No body required
```

**Response (200 OK):**
```json
{
  "available": true,
  "docker": true,
  "wireshark": true,
  "xpra": true,
  "xvfb": true,
  "missing": []
}
```

| Field | Type | Description |
|-------|------|-------------|
| available | boolean | All required components are installed |
| docker | boolean | Docker daemon is accessible |
| wireshark | boolean | Wireshark CLI is installed |
| xpra | boolean | Xpra is installed |
| xvfb | boolean | Xvfb is installed |
| missing | string[] | List of missing component names |

**Error Response (401 Unauthorized):**
```json
{"detail": "Not authenticated"}
```

---

### 2. Start Capture with Wireshark

Start packet capture and enable Wireshark integration.

```http
POST /v3/projects/{project_id}/links/{link_id}/capture/start
```

**Request Body:**
```json
{
  "data_link_type": "DLT_C_HDLC",
  "capture_file_name": "capture_001",
  "wireshark": true
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| data_link_type | string | No | "DLT_EN10MB" | Data link type for capture |
| capture_file_name | string | No | Auto-generated | Name of capture file |
| wireshark | boolean | No | false | Enable Wireshark integration |

**Response (201 Created):**
```json
{
  "link_id": "582524e6-c7be-4c0b-9921-77e25a344752",
  "project_id": "5af0fe00-f39d-4985-8669-7e8c512d729c",
  "capturing": true,
  "wireshark": true,
  "capture_file_name": "capture_001",
  "capture_file_path": "/path/to/projects/5af0fe00/captures/capture_001",
  "link_type": "ethernet",
  "nodes": [...]
}
```

**Error Responses:**
- 401 Unauthorized: Not authenticated
- 404 Not Found: Project or link not found
- 403 Forbidden: Insufficient privileges

---

### 3. Stop Capture

Stop packet capture (automatically disables Wireshark).

```http
POST /v3/projects/{project_id}/links/{link_id}/capture/stop
```

**Request:**
```
No body required
```

**Response (204 No Content):**
```
Empty body
```

---

### 4. WebSocket - View in Wireshark

Open a WebSocket connection to view Wireshark in browser.

```http
ws://gns3-server:3080/v3/projects/{project_id}/links/{link_id}/capture/wireshark?token={jwt_token}
```

**Authentication:** JWT token via query parameter

#### Server → Client Messages:

**Step 1: Waiting (session starting)**
```json
{"type": "waiting", "message": "Starting Wireshark..."}
```

**Step 2: Ready (Wireshark is running)**
```json
{
  "type": "ready",
  "display": ":0"
}
```

| Field | Type | Description |
|-------|------|-------------|
| type | string | Message type: "waiting", "ready", "error" |
| display | string | X display number (e.g., ":0") |
| message | string | Human-readable status message |
| error | string | Error details (only on error type) |

**Step 3: Error (if something fails)**
```json
{
  "type": "error",
  "message": "Wireshark not available: missing wireshark"
}
```

**WebSocket Close Codes:**
- 1008: Link not found or capture not started
- 1011: Internal server error

---

### 5. noVNC Integration

After receiving `{"type": "ready"}`, use noVNC to connect to the xpra WebSocket.

See section 7. noVNC Integration above.

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| ProjectContainerManager | ✅ DONE | Docker API container lifecycle |
| DisplayManager | ✅ DONE | Per-container display allocation |
| WiresharkSessionManager | ✅ DONE | Session state machine + Docker exec |
| WebSocket Handler | ✅ DONE | FastAPI WebSocket with state protocol |
| Dockerfile + start.sh | ✅ DONE | Container image |
| Link API modifications | ✅ DONE | Add wireshark=true to start/stop |
| Frontend integration | 📄 Docs Ready | See "Frontend Integration Guide" section |

## Troubleshooting

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| WebSocket 4001 | JWT invalid | Refresh token |
| WebSocket 4004 | Session not found | Click "View in Wireshark" first |
| "waiting" forever | Docker exec stuck | Check Docker logs |
| "error" message | Session creation failed | Verify container reachable |
| Black screen | Wireshark not started | Check process in container |
| Container not found | Project container not created | Check project is open |
| No ports available | All ports (10000-10099) in use | Reduce concurrent projects |

## Limitations

- **Concurrent projects:** Max 100 projects with active Wireshark sessions (ports 10000-10099)
- **Sessions per project:** Max 51 concurrent Wireshark sessions per project (displays 0-50)

## Future Enhancements

1. **Session Recovery** - Persist session state across GNS3 Server restarts
2. **Multiple Viewers** - Allow multiple browsers to view same session (read-only)
3. **Session Recording** - Save Wireshark interaction for playback
4. **Resource Monitoring** - Track and limit Wireshark resource usage
