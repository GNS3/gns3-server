# Web Wireshark Integration

## Overview

Integrate Wireshark packet capture functionality into GNS3 Web UI, allowing users to view real-time capture data directly in the browser via noVNC.

## Installation

```bash
# Pull Docker image (standalone)
docker pull ghcr.io/gns3/web-wireshark:latest
```

**Module location:** `gns3server/agent/web_wireshark/`

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
│  │  agent/web_wireshark/                                    │   │
│  │  - WiresharkManager: main coordinator                    │   │
│  │  - DisplayManager: tracks displays (:0-:50)              │   │
│  │  - ProjectContainerManager: container lifecycle          │   │
│  │  - WiresharkSession: session state + Docker exec         │   │
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
│  │    - token.txt: User's JWT for capture/stream API       │   │
│  │  - Wireshark uses token to call GNS3 Server API         │   │
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
- **Immediate session creation** - Wireshark session starts when capture begins (wireshark=true)
- **Docker API direct management** - No Ansible or SSH required
- **Browser only connects to GNS3 Server** - WebSocket proxy handles forwarding
- **Secure token handling** - User's JWT token used in container for capture/stream API
- **Real-time notifications** - Progress updates via project WebSocket

## Container Lifecycle

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Project opens ──▶ Container starts ──▶ Container running              │
│  Project closes ──▶ Container stops                                       │
│                                                                          │
│  Within Container:                                                       │
│  Capture start (wireshark=true) ──▶ Session starting ──▶ Session ready  │
│  Capture stop ──▶ Session stopped ──▶ Session cleanup                   │
└──────────────────────────────────────────────────────────────────────────┘
```

## Session State Machine

```
[idle] ──▶ [starting] ──▶ [ready] ──▶ [stopped] ──▶ [idle]
            │              │              │
            ▼              ▼              ▼
        Capture start    Docker exec    User views
        (wireshark=true) (5-10s)       Wireshark

[idle] ──▶ [error]  (if Docker operation fails)
```

## Data Flow

### 1. Project Opens
```
Project opened → Docker API creates container → Container starts with xpra
```

### 2. Start Capture with Wireshark
```
POST /v3/projects/{project_id}/links/{link_id}/capture/start
  Body: { "wireshark": true }
  │
  ▼
GNS3 Server:
  │
  ├─▶ Step 1: Start packet capture
  │   └─▶ project.emit_notification("wireshark.capturing", {"status": "started"})
  │
  ├─▶ Step 2: Create/check Wireshark container
  │   └─▶ project.emit_notification("wireshark.container", {"status": "ready"})
  │
  ├─▶ Step 3: Start Wireshark session
  │   ├─▶ Allocate display :N
  │   ├─▶ Docker exec: create user, write JWT token, start wireshark
  │   └─▶ project.emit_notification("wireshark.session", {"status": "starting"})
  │
  └─▶ Step 4: WebSocket endpoint ready
      ├─▶ Generate WebSocket URL
      └─▶ project.emit_notification("wireshark.session", {"status": "ready", "ws_url": "..."})

Response: {capturing: true, wireshark: true}
```

### 3. Frontend Receives Notifications
```
Browser (via project WebSocket):
  │
  ├─▶ {"type": "wireshark.capturing", "status": "started"}
  │   └─▶ Update UI: "Capture started..."
  │
  ├─▶ {"type": "wireshark.container", "status": "ready"}
  │   └─▶ Update UI: "Container ready..."
  │
  ├─▶ {"type": "wireshark.session", "status": "starting"}
  │   └─▶ Update UI: "Starting Wireshark..."
  │
  └─▶ {"type": "wireshark.session", "status": "ready", "ws_url": "ws://..."}
      └─▶ Connect noVNC to ws_url
          └─▶ Display Wireshark in browser
```

### 4. Stop Capture
```
POST /v3/projects/{project_id}/links/{link_id}/capture/stop
  │
  ▼
GNS3 Server:
  ├─▶ Stop packet capture
  ├─▶ Stop Wireshark session (Docker exec)
  ├─▶ Release display
  └─▶ project.emit_notification("wireshark.session", {"status": "stopped"})

Note: Container stays running for project
```

### 5. Project Close
```
Project closes:
  ├─▶ Stop all Wireshark sessions
  ├─▶ docker stop + rm container
  └─▶ All resources cleaned up
```

## Key Components

### WiresharkManager (agent/web_wireshark/manager.py)
- Main coordinator for Web Wireshark functionality
- Singleton instance accessed via `WiresharkManager.instance()`
- Coordinates container and session management

### ProjectContainerManager
- Creates/destroys containers via Docker API
- One container per project
- Tracks container state and IP
- Container lifecycle tied to project open/close

### DisplayManager
- Manages X display allocation per container (:0 to :50)
- Each Wireshark session uses one display
- Tracks used/available displays per container

### WiresharkSession
- Represents a single Wireshark session (one per link)
- Session state: idle → starting → ready → stopped → error
- Creates/closes sessions via Docker exec
- Coordinates with DisplayManager for display allocation
- Emits project notifications for status updates

### noVNC WebSocket Handler
- Proxies browser to container's xpra WebSocket
- Validates JWT token and session ownership
- Handles connection lifecycle

## Security

| Concern | Mitigation |
|---------|------------|
| JWT token in container | User's JWT stored in /tmp/sessions/link-{uuid}/token.txt (mode 0600) |
| Token visible in `ps aux` | Token passed via file, not CLI arguments |
| Container accessing GNS3 API | Container uses user's JWT token with same permissions as user |
| Browser accessing container | All access via GNS3 Server WebSocket proxy |
| Unauthorized WebSocket | JWT validation + link ownership check |
| Resource abuse | cgroups limit memory (2GB) and processes (50) |
| Token lifecycle | Token expires when capture stops / session ends |

### Trust Model
```
Browser ──▶ GNS3 Server (JWT validated)
                    │
                    ├─▶ Wireshark Container (has user's JWT token)
                    │       └─▶ GNS3 Server API (capture/stream)
                    │
                    └─▶ Browser (noVNC WebSocket)

All traffic flows through GNS3 Server proxy
Container uses user's JWT to access capture data (same permissions as user)
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
├── tmp/sessions/link-{uuid}/
│   └── token.txt                    # User's JWT (0600)
├── usr/bin/wireshark                # Uses token to call capture/stream API
├── usr/bin/xpra
└── usr/bin/xvfb-run
```

## Local Development & Testing

### Build Container Locally
```bash
cd gns3server/agent/web_wireshark/
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

### 2. Listen for Project WebSocket Notifications

The frontend receives real-time updates via the project WebSocket:

```javascript
// Connect to project notifications WebSocket
const ws = new WebSocket(
  `ws://gns3-server:3080/v3/projects/${projectId}/notifications/ws?token=${jwtToken}`
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  // Wireshark progress notifications
  if (msg.type === 'wireshark.capturing') {
    // msg.status: "started"
    updateStatus("Capture started...");
  }

  if (msg.type === 'wireshark.container') {
    // msg.status: "ready"
    updateStatus("Container ready...");
  }

  if (msg.type === 'wireshark.session') {
    if (msg.status === 'starting') {
      updateStatus("Starting Wireshark...");
    } else if (msg.status === 'ready') {
      // msg.ws_url: "ws://gns3-server:3080/..."
      connectNoVNC(msg.ws_url);
    } else if (msg.status === 'stopped') {
      updateStatus("Wireshark stopped");
      closeNoVNC();
    } else if (msg.status === 'error') {
      // msg.error: error message
      showError(msg.error);
    }
  }
};
```

### 3. noVNC Integration

When `wireshark.session.status === "ready"`, connect to the provided WebSocket:

```javascript
function connectNoVNC(wsUrl) {
  const rfb = new RFB({
    target: document.getElementById('vnc-container'),
    url: wsUrl,
    credentials: { password: '' } // No password required
  });

  rfb.addEventListener('connect', () => {
    console.log('Connected to Wireshark');
  });

  rfb.addEventListener('disconnect', () => {
    console.log('Disconnected from Wireshark');
  });
}
```

### 4. Complete Flow

```
1. User clicks "Start Capture" with Wireshark enabled
   └── POST /capture/start {wireshark: true}

2. Frontend receives project WebSocket notifications:
   ├─ "wireshark.capturing" → "Capture started..."
   ├─ "wireshark.container" → "Container ready..."
   ├─ "wireshark.session" (starting) → "Starting Wireshark..."
   └─ "wireshark.session" (ready) → Connect noVNC to ws_url

3. Wireshark displays in browser via noVNC

4. User clicks "Stop Capture"
   └── POST /capture/stop
   └─ "wireshark.session" (stopped) → Close noVNC
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
  "wireshark_session_id": "ws-session-uuid",
  "capture_file_name": "capture_001",
  "capture_file_path": "/path/to/projects/5af0fe00/captures/capture_001",
  "link_type": "ethernet",
  "nodes": [...]
}
```

**Note:** The actual Wireshark session progress is sent via project WebSocket notifications. See "Frontend Integration Guide" section.

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

### 4. Project WebSocket Notifications

The frontend receives real-time Wireshark session updates via the project WebSocket.

#### Notification: wireshark.capturing
```json
{
  "type": "wireshark.capturing",
  "status": "started",
  "link_id": "582524e6-c7be-4c0b-9921-77e25a344752"
}
```

#### Notification: wireshark.container
```json
{
  "type": "wireshark.container",
  "status": "ready",
  "container_id": "gns3-ws-5af0fe00-f39d-4985-8669-7e8c512d729c"
}
```

#### Notification: wireshark.session (starting)
```json
{
  "type": "wireshark.session",
  "status": "starting",
  "link_id": "582524e6-c7be-4c0b-9921-77e25a344752",
  "session_id": "ws-session-uuid"
}
```

#### Notification: wireshark.session (ready)
```json
{
  "type": "wireshark.session",
  "status": "ready",
  "link_id": "582524e6-c7be-4c0b-9921-77e25a344752",
  "session_id": "ws-session-uuid",
  "ws_url": "ws://gns3-server:3080/v3/projects/{project_id}/links/{link_id}/wireshark/ws/{session_id}",
  "display": ":0"
}
```

#### Notification: wireshark.session (stopped)
```json
{
  "type": "wireshark.session",
  "status": "stopped",
  "link_id": "582524e6-c7be-4c0b-9921-77e25a344752",
  "session_id": "ws-session-uuid"
}
```

#### Notification: wireshark.session (error)
```json
{
  "type": "wireshark.session",
  "status": "error",
  "link_id": "582524e6-c7be-4c0b-9921-77e25a344752",
  "error": "Failed to start Wireshark: Docker container not accessible"
}
```

---

### 5. WebSocket - noVNC Connection

When `wireshark.session.status === "ready"`, connect to the provided WebSocket URL:

```http
ws://gns3-server:3080/v3/projects/{project_id}/links/{link_id}/wireshark/ws/{session_id}?token={jwt_token}
```

**Authentication:** JWT token via query parameter

This WebSocket connection is proxied to the container's xpra server for noVNC RFB protocol.

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| agent/web_wireshark module | 🔲 TODO | Create module structure |
| WiresharkManager | 🔲 TODO | Main coordinator |
| ProjectContainerManager | 🔲 TODO | Docker API container lifecycle |
| DisplayManager | 🔲 TODO | Per-container display allocation |
| WiresharkSession | 🔲 TODO | Session state + Docker exec |
| Link API modifications | 🔲 TODO | Add wireshark parameter handling |
| Project WebSocket notifications | 🔲 TODO | Emit progress notifications |
| noVNC WebSocket endpoint | 🔲 TODO | Proxy to xpra |
| Dockerfile + start.sh | 🔲 TODO | Container image |
| Frontend integration | 🔲 TODO | Implement notification handling |

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

---

## Implementation Plan

### Phase 1: Foundation (Module Structure)

Create the `gns3server/agent/web_wireshark/` module structure:

```
gns3server/agent/web_wireshark/
├── __init__.py
├── manager.py           # WiresharkManager (singleton coordinator)
├── container_manager.py  # ProjectContainerManager
├── display_manager.py    # DisplayManager
├── session.py            # WiresharkSession
└── docker/
    ├── Dockerfile        # Wireshark container image
    └── start.sh          # Container entry point
```

**Tasks:**
1. Create module structure with `__init__.py`
2. Create Dockerfile for Wireshark container
3. Create start.sh script
4. Build and test container image locally

---

### Phase 2: Core Managers

#### 2.1 ProjectContainerManager (`container_manager.py`)

```python
class ProjectContainerManager:
    """Manages Docker containers for Wireshark sessions"""

    async def create_container(self, project_id: str) -> str:
        """Create a new Wireshark container for the project"""

    async def get_container(self, project_id: str) -> dict:
        """Get container info by project ID"""

    async def delete_container(self, project_id: str):
        """Stop and remove the project's Wireshark container"""

    def container_exists(self, project_id: str) -> bool:
        """Check if container exists"""
```

**Tasks:**
- Implement Docker API integration
- Container naming: `gns3-ws-{project_id}`
- Port allocation: 10000-10099
- Container lifecycle management

#### 2.2 DisplayManager (`display_manager.py`)

```python
class DisplayManager:
    """Manages X display allocation per container"""

    def allocate_display(self, container_id: str) -> str:
        """Allocate an available display (e.g., :0)"""

    def release_display(self, container_id: str, display: str):
        """Release a previously allocated display"""

    def get_available_displays(self, container_id: str) -> List[str]:
        """Get list of available displays"""
```

**Tasks:**
- Track displays :0 to :50 per container
- Thread-safe allocation
- Automatic cleanup on container removal

#### 2.3 WiresharkSession (`session.py`)

```python
class WiresharkSession:
    """Represents a single Wireshark session for a link"""

    async def start(self, link_id: str, jwt_token: str, capture_url: str):
        """Start Wireshark session in container"""

    async def stop(self):
        """Stop Wireshark session and cleanup"""

    def get_state(self) -> str:
        """Get current session state: idle/starting/ready/stopped/error"""

    def get_websocket_url(self) -> str:
        """Get WebSocket URL for noVNC connection"""
```

**Tasks:**
- Session state management
- Docker exec for user creation and Wireshark startup
- JWT token file creation
- Display allocation coordination
- Notification emission via project

---

### Phase 3: Main Coordinator

#### 3.1 WiresharkManager (`manager.py`)

```python
class WiresharkManager:
    """Main coordinator for Web Wireshark functionality"""

    @staticmethod
    def instance() -> 'WiresharkManager':
        """Get singleton instance"""

    async def start_capture_session(
        self,
        project,
        link_id: str,
        jwt_token: str,
        capture_url: str
    ) -> WiresharkSession:
        """Start Wireshark session for a link capture"""

    async def stop_capture_session(self, project, link_id: str):
        """Stop Wireshark session for a link"""

    def get_session(self, link_id: str) -> Optional[WiresharkSession]:
        """Get existing session by link ID"""

    async def cleanup_project(self, project_id: str):
        """Cleanup all sessions and container for a project"""
```

**Tasks:**
- Singleton pattern implementation
- Coordinate ContainerManager, DisplayManager, and Session
- Session lifecycle management
- Error handling and recovery

---

### Phase 4: API Integration

#### 4.1 Modify Link.start_capture()

**File:** `gns3server/controller/link.py`

```python
async def start_capture(
    self,
    data_link_type="DLT_EN10MB",
    capture_file_name=None,
    wireshark=False  # NEW PARAMETER
):
    """Start capture on the link"""

    self._capturing = True
    self._capture_file_name = capture_file_name

    if wireshark:
        from gns3server.agent.web_wireshark import WiresharkManager
        manager = WiresharkManager.instance()
        # Start Wireshark session with user's JWT token
        await manager.start_capture_session(
            self._project,
            self.id,
            self._project._controller._current_user_jwt,  # Need to pass JWT
            self.pcap_streaming_url()
        )

    self._project.emit_notification("link.updated", self.asdict())
```

**Tasks:**
- Add `wireshark` parameter to `start_capture()`
- Add `wireshark_session_id` to link state
- Integrate with WiresharkManager
- Handle JWT token passing

#### 4.2 Modify Link.stop_capture()

**File:** `gns3server/controller/link.py`

```python
async def stop_capture(self):
    """Stop capture on the link"""

    if self._wireshark_session_id:
        from gns3server.agent.web_wireshark import WiresharkManager
        manager = WiresharkManager.instance()
        await manager.stop_capture_session(self._project, self.id)

    self._capturing = False
    self._project.emit_notification("link.updated", self.asdict())
```

**Tasks:**
- Stop Wireshark session when capture stops
- Cleanup session state

#### 4.3 Project Lifecycle Integration

**File:** `gns3server/controller/project.py`

```python
async def open(self):
    """Open project"""
    # ... existing code ...

    # Create Wireshark container for project
    from gns3server.agent.web_wireshark import WiresharkManager
    manager = WiresharkManager.instance()
    await manager._container_manager.create_container(self.id)

async def close(self):
    """Close project"""
    # Cleanup Wireshark sessions and container
    from gns3server.agent.web_wireshark import WiresharkManager
    manager = WiresharkManager.instance()
    await manager.cleanup_project(self.id)

    # ... existing code ...
```

**Tasks:**
- Create container on project open
- Cleanup on project close

---

### Phase 5: WebSocket Endpoint

#### 5.1 noVNC WebSocket Route

**File:** `gns3server/api/routes/controller/links.py`

```python
@router.websocket(
    "/{link_id}/wireshark/ws/{session_id}"
)
async def wireshark_websocket(
    websocket: WebSocket,
    link_id: str,
    session_id: str,
    token: str,
    link: Link = Depends(dep_link)
):
    """WebSocket endpoint for noVNC connection to Wireshark"""

    # Validate JWT token
    # Validate session ownership
    # Proxy WebSocket to container's xpra server
```

**Tasks:**
- WebSocket route creation
- JWT validation
- Session ownership check
- WebSocket proxy to container xpra
- Connection lifecycle management

---

### Phase 6: Testing & Documentation

#### 6.1 Unit Tests

**Files:**
- `tests/agent/web_wireshark/test_manager.py`
- `tests/agent/web_wireshark/test_container_manager.py`
- `tests/agent/web_wireshark/test_display_manager.py`
- `tests/agent/web_wireshark/test_session.py`

**Tasks:**
- Mock Docker API
- Test container lifecycle
- Test display allocation
- Test session state machine

#### 6.2 Integration Tests

**Tasks:**
- End-to-end capture flow
- WebSocket connection
- Container cleanup
- Error scenarios

#### 6.3 Documentation Updates

**Tasks:**
- Update API documentation
- Add configuration options
- Update troubleshooting guide

---

### Implementation Order (Bottom-Up)

```
1. Dockerfile + start.sh (Container)
2. ProjectContainerManager (Docker API)
3. DisplayManager (Resource allocation)
4. WiresharkSession (Session logic)
5. WiresharkManager (Coordination)
6. Link API integration (Controller)
7. WebSocket endpoint (API)
8. Tests & Docs
```

### Dependencies

- Docker daemon access (`/var/run/docker.sock`)
- Docker Python SDK (`docker` package)
- WebSocket proxy support
- Project WebSocket notification system

### Estimated Complexity

| Phase | Complexity | Time Estimate |
|-------|-----------|---------------|
| Phase 1: Foundation | Low | 1-2 days |
| Phase 2: Core Managers | Medium | 3-5 days |
| Phase 3: Main Coordinator | Medium | 2-3 days |
| Phase 4: API Integration | Medium | 2-3 days |
| Phase 5: WebSocket | High | 3-4 days |
| Phase 6: Testing & Docs | Low | 2-3 days |
| **Total** | | **13-20 days** |
