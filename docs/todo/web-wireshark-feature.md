# Web Wireshark Integration

## Overview

Integrate Wireshark packet capture functionality into GNS3 Web UI, allowing users to view real-time capture data directly in the browser via noVNC.

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
│  │  - DisplayManager: tracks displays per container (:0-:10)│   │
│  │  - Session state: pending → starting → ready → error    │   │
│  │  - ProjectContainerManager: project container lifecycle│   │
│  │  - AnsibleRunner: triggers playbooks for container/session│  │
│  └──────────────────────────────────────────────────────────┘   │
│                              │ WebSocket                        │
│                              ▼                                  │
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
│  │  - Session dir: /tmp/sessions/link-{uuid}/              │   │
│  │    - token: JWT for capture/stream API                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Linux User Isolation (one user per link_id)            │   │
│  │                                                           │   │
│  │  link-{uuid-1} ──▶ Xvfb :0 ──▶ wireshark              │   │
│  │  link-{uuid-2} ──▶ Xvfb :1 ──▶ wireshark              │   │
│  │  link-{uuid-3} ──▶ Xvfb :2 ──▶ wireshark              │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  cgroups Resource Limits (per user)                     │   │
│  │  - Memory: 2GB  |  Processes: 50  |  CPU Shares: 10%   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP (token via file, not CLI)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        GNS3 Server                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Capture File Storage (Project-level persistence)       │   │
│  │  /path/to/projects/{project_id}/project-files/captures/ │   │
│  │      └── {link_capture_file}.pcap                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│              GET /v3/links/{link_id}/capture/stream            │
│              (Authorization: Bearer {user_jwt})                 │
└─────────────────────────────────────────────────────────────────┘
```

## Design Principles

- **Project-level container isolation** - One container per project, lifecycle bound to project
- **On-demand Wireshark sessions** - Session created only when user clicks "View in Wireshark"
- **No independent wireshark API** - Reuse existing capture API endpoints
- **Ansible-driven container and session management** - Container lifecycle and Wireshark sessions handled by Ansible playbooks
- **Browser only connects to GNS3 Server** - WebSocket proxy handles forwarding to Wireshark container
- **HTTP-based data delivery** - Wireshark fetches pcap stream via HTTP using token file (not CLI args)
- **State-driven session lifecycle** - Frontend receives real-time session state via WebSocket
- **Secure token handling** - JWT token stored in session file, not process arguments
- **Unified authentication** - GNS3 Server's JWT is the only auth mechanism; xpra trusts the proxy gateway
- **Container is stateless** - Container only provides GUI display, data persists in project directory

## Container Lifecycle

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    Project-Level Container Lifecycle                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [project.opened] ──▶ [container.start] ──▶ [container.running]         │
│                                                          │               │
│  [project.closed] ──▶ [container.stop] ──▶ [container.stopped]         │
│                                                                          │
│  Wireshark Sessions within Container:                                    │
│  [session.requested] ──▶ [session.starting] ──▶ [session.ready]         │
│                                                                │         │
│  [session.closed] or [project.closed] ──▶ [session.cleanup]             │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Session Lifecycle

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           Session State Machine                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [idle] ──▶ [pending] ──▶ [starting] ──▶ [ready] ──▶ [closing] ──▶ [idle]
│                │                │                │                │
│                │                │                │                │
│                ▼                ▼                ▼                ▼
│            User clicks     Ansible runs     User views      Stop capture
│            View Wireshark  (5-10s)          Wireshark       or timeout
│                                                                          │
│  [idle] ──▶ [error]  (if Ansible fails)                                │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

State Persistence:
- Session state is ephemeral (lost on GNS3 Server restart)
- On restart, user must request Wireshark view again
- Container state persists (survives session restarts within same project)
- Capture data is persistent in project directory (survives all restarts)
```

## Data Flow

### 1. Project Opens (Container Created)

```
Project opened in GNS3
   │
   └─▶ WiresharkSessionManager detects project open
       │
       ▼
   Ansible: docker run wireshark-container-{project_id}
       │
       ▼
   Container starts with xpra running
   Container is now ready to serve Wireshark sessions
```

### 2. Start Capture

```
User clicks "Start Capture" in GNS3 Web UI (with Wireshark enabled)
   │
   └─▶ POST /v3/links/{link_id}/capture/start
       Header: Authorization: Bearer {user_jwt}
       Body: { "wireshark": true }
       │
       ▼
   GNS3 Server:
   a. Starts packet capture (existing behavior, data saved to project directory)
   b. Response includes wireshark_ws endpoint
```

### 3. View in Wireshark (On-Demand Session Creation)

```
User clicks "View in Wireshark" (demands Wireshark view)
   │
   └─▶ WebSocket /v3/links/{link_id}/capture/wireshark
       Header: Authorization: Bearer {user_jwt}
       │
       ▼
   GNS3 Server:
   WiresharkSessionManager:
      - Checks if container for project exists
      - If not, creates container via Ansible (already started with project)
      - Allocates display :N (via DisplayManager, per-container range :0-:10)
      - Creates session state: pending
      - Triggers Ansible playbook (async) to create wireshark session
       │
       ▼
   Response (immediate via WebSocket):
   {
     "type": "waiting",
     "message": "Starting Wireshark..."
   }
       │
       ▼
   Ansible executes in container (5-10 seconds):
   - Creates Linux user link-{uuid}
   - Creates session dir /tmp/sessions/link-{uuid}/
   - Writes JWT token to /tmp/sessions/link-{uuid}/token (mode 0600)
   - Starts xpra session (if not already running on that display)
   - Starts wireshark consuming capture/stream API (token read from file)
   - Updates session state to: ready
       │
       ▼
   WebSocket sends:
   {
     "type": "ready",
     "display": ":0",
     "xpra_ws": "ws://wireshark-container:10000"
   }
```

### 4. Frontend WebSocket Connection

```
Frontend connects to WebSocket AFTER receiving "ready" message:
   ws://gns3-server:3080/v3/links/{link_id}/capture/wireshark
   Header: Authorization: Bearer {user_jwt}

   │
   ├─▶ GNS3 Server validates JWT token
   │
   ├─▶ Check session state:
   │      - [pending/starting]: send {"type": "waiting", "message": "Starting..."}
   │      - [ready]: send {"type": "ready", "display": ":0", "xpra_ws": "..."}
   │      - [error]: send {"type": "error", "message": "..."}
   │
   └─▶ If session is [ready]:
       - Proxy WebSocket to Wireshark Container xpra :10000
       - No xpra authentication required (GNS3 Server is trusted gateway)
       - noVNC iframe connects to xpra WebSocket via proxy
```

### 5. Stop Wireshark View

```
User clicks "Stop Wireshark View" (closes Wireshark window)
   │
   └─▶ POST /v3/links/{link_id}/capture/wireshark/stop
       │
       ▼
   GNS3 Server:
   WiresharkSessionManager:
      - Triggers Ansible playbook (async) to cleanup session
      - Releases display back to DisplayManager
      - Sets session state: closing → idle
      - Container stays running (ready for other links in same project)
```

### 6. Project Closes (Container Destroyed)

```
Project closed in GNS3
   │
   └─▶ WiresharkSessionManager detects project close
       │
       ▼
   For each active Wireshark session in this project:
      - Ansible: cleanup session (user, processes, cgroups)
       │
       ▼
   Ansible: docker stop + docker rm wireshark-container-{project_id}
       │
       ▼
   All sessions cleaned up, container destroyed
   Capture data remains in project directory (persistent)
```

### 7. Abnormal Disconnect

```
User closes browser (noVNC WebSocket disconnects)
   │
   ▼
WebSocket handler detects disconnect (finally block)
   │
   ├─▶ If link.capturing == true:
   │      - Session stays alive (capture continues, data saved)
   │      - Display remains allocated
   │      - User can reconnect via new WebSocket connection
   │
   └─▶ If link.capturing == false:
          - Trigger cleanup immediately
          - Release display

Heartbeat mechanism:
   - WebSocket proxy sends ping every 10 seconds
   - If no pong within 30 seconds, treat as disconnected
   - On timeout: cleanup if not capturing, otherwise keep session
```

## DisplayManager

Manages X display allocation within a single container.

```python
# gns3server/compute/display_manager.py

import asyncio
import logging

log = logging.getLogger(__name__)


class DisplayManager:
    """
    Manages X display number allocation for Wireshark sessions.

    Each container has its own DisplayManager with range :0 to :10.
    Displays must be released when the session ends.
    """

    def __init__(self, start: int = 0, max_displays: int = 10):
        self._start = start
        self._max = start + max_displays
        self._allocated: dict[int, str] = {}  # display -> link_id
        self._lock = asyncio.Lock()

    async def allocate(self, link_id: str) -> str:
        """
        Allocate a display number for a link.

        :param link_id: The link ID requesting a display
        :returns: Display string (e.g., ":0")
        :raises RuntimeError: If no displays available
        """
        async with self._lock:
            for display in range(self._start, self._max):
                if display not in self._allocated:
                    self._allocated[display] = link_id
                    display_str = f":{display}"
                    log.info(f"Allocated display {display_str} for link {link_id}")
                    return display_str

            raise RuntimeError(f"No available displays in range :{self._start}-:{self._max - 1}")

    async def release(self, display: str) -> None:
        """
        Release a display number.

        :param display: Display string (e.g., ":0")
        """
        if not display or len(display) < 2:
            return

        display_num = int(display[1:])
        async with self._lock:
            if display_num in self._allocated:
                link_id = self._allocated.pop(display_num)
                log.info(f"Released display {display} from link {link_id}")

    async def get_display_link_id(self, display: str) -> str | None:
        """
        Get the link ID using a specific display.

        :param display: Display string (e.g., ":0")
        :returns: Link ID or None if not found
        """
        if not display or len(display) < 2:
            return None
        display_num = int(display[1:])
        async with self._lock:
            return self._allocated.get(display_num)

    def get_allocated_count(self) -> int:
        """Return the number of currently allocated displays."""
        return len(self._allocated)
```

## ProjectContainerManager

Manages Wireshark container lifecycle per project.

```python
# gns3server/compute/project_container_manager.py

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class ProjectContainer:
    """Represents a project's Wireshark container."""
    project_id: str
    container_id: str
    container_ip: str
    display_manager: 'DisplayManager'
    state: str = "running"  # starting, running, stopping, stopped


class ProjectContainerManager:
    """
    Manages Wireshark containers on a per-project basis.

    Responsibilities:
    - Create container when project opens
    - Destroy container when project closes
    - Track container state and IP
    - Provide DisplayManager per container
    """

    def __init__(self, container_image: str = "gns3/wireshark-server:latest"):
        self._containers: dict[str, ProjectContainer] = {}  # project_id -> container
        self._container_image = container_image
        self._lock = asyncio.Lock()
        self._ansible_inventory = "/etc/ansible/hosts"
        self._ansible_playbooks_dir = "/etc/ansible/playbooks"

    async def on_project_opened(self, project_id: str) -> ProjectContainer:
        """
        Called when a project is opened.
        Creates a Wireshark container for the project.
        """
        async with self._lock:
            if project_id in self._containers:
                return self._containers[project_id]

            container = await self._create_container(project_id)
            self._containers[project_id] = container
            log.info(f"Created Wireshark container for project {project_id}")
            return container

    async def on_project_closed(self, project_id: str) -> None:
        """
        Called when a project is closed.
        Destroys the project's Wireshark container.
        """
        async with self._lock:
            if project_id not in self._containers:
                return

            container = self._containers.pop(project_id)
            await self._destroy_container(container)
            log.info(f"Destroyed Wireshark container for project {project_id}")

    async def get_container(self, project_id: str) -> Optional[ProjectContainer]:
        """Get container for a project, None if not running."""
        return self._containers.get(project_id)

    async def _create_container(self, project_id: str) -> ProjectContainer:
        """Create a new Wireshark container via Ansible."""
        # Run Ansible playbook to create and start container
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                [
                    "ansible-playbook",
                    f"{self._ansible_playbooks_dir}/wireshark_container_create.yml",
                    "-e", json.dumps({"project_id": project_id}),
                    "-i", self._ansible_inventory,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            ),
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create container: {result.stderr}")

        # Get container IP
        container_ip = await self._get_container_ip(project_id)

        return ProjectContainer(
            project_id=project_id,
            container_id=f"gns3-ws-{project_id}",
            container_ip=container_ip,
            display_manager=DisplayManager(start=0, max_displays=10),
            state="running"
        )

    async def _destroy_container(self, container: ProjectContainer) -> None:
        """Destroy container via Ansible."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                [
                    "ansible-playbook",
                    f"{self._ansible_playbooks_dir}/wireshark_container_delete.yml",
                    "-e", json.dumps({"project_id": container.project_id}),
                    "-i", self._ansible_inventory,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            ),
        )

    async def _get_container_ip(self, project_id: str) -> str:
        """Get container IP via Ansible."""
        # Implementation to query container IP
        pass
```

## WiresharkSessionManager

Manages Wireshark session lifecycle on the GNS3 Server side.

```python
# gns3server/compute/wireshark_session_manager.py

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)


class SessionState(Enum):
    IDLE = "idle"
    PENDING = "pending"
    STARTING = "starting"
    READY = "ready"
    CLOSING = "closing"
    ERROR = "error"


@dataclass
class WiresharkSession:
    """Represents a Wireshark viewing session for a link."""

    link_id: str
    project_id: str
    display: str
    state: SessionState = SessionState.PENDING
    error_message: str = ""
    ansible_task: Optional[asyncio.Task] = None
    created_at: float = field(default_factory=asyncio.get_event_loop().time)


class WiresharkSessionManager:
    """
    Manages Wireshark sessions for packet capture links.

    Responsibilities:
    - Coordinate with ProjectContainerManager for container lifecycle
    - Allocate displays via ProjectContainer's DisplayManager
    - Trigger Ansible playbooks for session create/cleanup
    - Track session state
    - Provide WebSocket handler with session info
    """

    def __init__(self, container_host: str = "wireshark-container"):
        self._sessions: dict[str, WiresharkSession] = {}  # link_id -> session
        self._project_containers: ProjectContainerManager = ProjectContainerManager()
        self._container_host = container_host
        self._lock = asyncio.Lock()
        self._ansible_inventory = "/etc/ansible/hosts"
        self._ansible_playbooks_dir = "/etc/ansible/playbooks"

    async def on_project_opened(self, project_id: str) -> None:
        """Called when a project opens. Creates Wireshark container."""
        await self._project_containers.on_project_opened(project_id)

    async def on_project_closed(self, project_id: str) -> None:
        """Called when a project closes. Destroys Wireshark container."""
        # Cleanup all sessions for this project
        sessions_to_close = [
            link_id for link_id, session in self._sessions.items()
            if session.project_id == project_id
        ]
        for link_id in sessions_to_close:
            await self.close_session(link_id)

        await self._project_containers.on_project_closed(project_id)

    async def create_session(self, link_id: str, project_id: str, user_token: str) -> WiresharkSession:
        """
        Create a new Wireshark session.

        :param link_id: The link ID to create session for
        :param project_id: The project ID
        :param user_token: JWT token for capture/stream access
        :returns: WiresharkSession object
        """
        async with self._lock:
            # Check if session already exists
            if link_id in self._sessions:
                session = self._sessions[link_id]
                if session.state in (SessionState.PENDING, SessionState.STARTING):
                    return session
                elif session.state == SessionState.READY:
                    return session

            # Get or create container for project
            container = await self._project_containers.get_container(project_id)
            if not container:
                # Project container doesn't exist, create it
                container = await self._project_containers.on_project_opened(project_id)

            # Allocate display from container's DisplayManager
            display = await container.display_manager.allocate(link_id)

            # Create session
            session = WiresharkSession(
                link_id=link_id,
                project_id=project_id,
                display=display,
                state=SessionState.PENDING,
            )
            self._sessions[link_id] = session

            # Async Ansible playbook to create session in container
            session.ansible_task = asyncio.create_task(
                self._run_create_playbook(link_id, project_id, user_token, display)
            )

            asyncio.create_task(self._poll_session_ready(link_id))

            return session

    async def _run_create_playbook(
        self, link_id: str, project_id: str, user_token: str, display: str
    ) -> None:
        """Run Ansible playbook to create Wireshark session (async)."""
        try:
            session = self._sessions.get(link_id)
            if not session:
                return

            session.state = SessionState.STARTING

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [
                        "ansible-playbook",
                        f"{self._ansible_playbooks_dir}/wireshark_session_create.yml",
                        "-e", json.dumps({
                            "link_id": link_id,
                            "project_id": project_id,
                            "user_token": user_token,
                            "display": display,
                        }),
                        "-i", self._ansible_inventory,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                ),
            )

            if result.returncode != 0:
                log.error(f"Ansible create failed: {result.stderr}")
                if link_id in self._sessions:
                    self._sessions[link_id].state = SessionState.ERROR
                    self._sessions[link_id].error_message = f"Create failed: {result.stderr}"
            else:
                log.info(f"Wireshark session created for link {link_id}")

        except asyncio.TimeoutError:
            log.error(f"Ansible playbook timed out for link {link_id}")
            if link_id in self._sessions:
                self._sessions[link_id].state = SessionState.ERROR
                self._sessions[link_id].error_message = "Create timed out"
        except Exception as e:
            log.error(f"Error running Ansible playbook: {e}")
            if link_id in self._sessions:
                self._sessions[link_id].state = SessionState.ERROR
                self._sessions[link_id].error_message = str(e)

    async def _poll_session_ready(self, link_id: str, timeout: float = 30) -> None:
        """Poll for session ready state."""
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < timeout:
            if link_id not in self._sessions:
                return

            session = self._sessions[link_id]
            if session.state == SessionState.READY or session.state == SessionState.ERROR:
                return

            if session.state == SessionState.STARTING and session.ansible_task:
                if session.ansible_task.done():
                    if session.state != SessionState.ERROR:
                        if await self._check_xpra_running(link_id, session.display):
                            session.state = SessionState.READY
                        else:
                            session.state = SessionState.ERROR
                            session.error_message = "Session creation failed"
                    return

            await asyncio.sleep(0.5)

        if link_id in self._sessions:
            self._sessions[link_id].state = SessionState.ERROR
            self._sessions[link_id].error_message = "Session creation timed out"

    async def _check_xpra_running(self, link_id: str, display: str) -> bool:
        """Check if xpra session is running via Ansible status playbook."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [
                        "ansible-playbook",
                        f"{self._ansible_playbooks_dir}/wireshark_session_status.yml",
                        "-e", json.dumps({"link_id": link_id, "display": display}),
                        "-i", self._ansible_inventory,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                ),
            )
            if result.returncode == 0:
                return "status: running" in result.stdout
        except Exception:
            pass
        return False

    async def close_session(self, link_id: str) -> None:
        """Close a Wireshark session."""
        async with self._lock:
            if link_id not in self._sessions:
                return

            session = self._sessions[link_id]
            session.state = SessionState.CLOSING

        asyncio.create_task(
            self._run_cleanup_playbook(link_id, session.project_id, session.display)
        )

    async def _run_cleanup_playbook(self, link_id: str, project_id: str, display: str) -> None:
        """Run Ansible playbook to cleanup Wireshark session (async)."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [
                        "ansible-playbook",
                        f"{self._ansible_playbooks_dir}/wireshark_session_cleanup.yml",
                        "-e", json.dumps({"link_id": link_id, "display": display}),
                        "-i", self._ansible_inventory,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                ),
            )

            if result.returncode != 0:
                log.warning(f"Ansible cleanup failed for {link_id}: {result.stderr}")

        except Exception as e:
            log.error(f"Error running cleanup playbook: {e}")
        finally:
            # Release display
            container = await self._project_containers.get_container(project_id)
            if container:
                await container.display_manager.release(display)

            # Remove session
            async with self._lock:
                if link_id in self._sessions:
                    del self._sessions[link_id]

    async def get_session(self, link_id: str) -> Optional[WiresharkSession]:
        """Get session by link ID."""
        return self._sessions.get(link_id)

    async def get_session_state(self, link_id: str) -> SessionState:
        """Get session state for a link."""
        session = self._sessions.get(link_id)
        return session.state if session else SessionState.IDLE

    def get_xpra_ws_url(self, session: WiresharkSession) -> str:
        """Get the xpra WebSocket URL for a session."""
        container = self._project_containers.get_container(session.project_id)
        if container:
            return f"ws://{container.container_ip}:10000"
        return f"ws://{self._container_host}:10000"
```

## WebSocket Handler

Handles browser WebSocket connections with state-based messaging.

```python
# gns3server/api/routes/controller/links.py (additions)

import asyncio
import json
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from uuid import UUID

# Wireshark session manager instance
wireshark_session_manager = WiresharkSessionManager()


@router.websocket("/v3/links/{link_id}/capture/wireshark")
async def wireshark_websocket(websocket: WebSocket, link_id: UUID):
    """
    WebSocket endpoint for Wireshark viewing.

    Protocol:
    1. Client connects with JWT token in header
    2. Server validates token and link ownership
    3. Server creates Wireshark session (on-demand)
    4. Server sends state message:
       - {"type": "waiting", "message": "Starting Wireshark..."}
       - {"type": "ready", "display": ":0", "xpra_ws": "ws://..."}
       - {"type": "error", "message": "..."}
    5. Once ready, bidirectional proxy to xpra WebSocket
    6. Heartbeat: ping every 10s, disconnect if no pong in 30s
    """
    # 1. Validate JWT token
    token = websocket.headers.get("Authorization", "").replace("Bearer ", "")
    if not await validate_jwt_token(token, str(link_id)):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # 2. Get link and project info
    link = await get_link_by_id(str(link_id))
    if not link:
        await websocket.close(code=4004, reason="Link not found")
        return

    project_id = link.project.id

    # 3. Create or get session (on-demand)
    session = await wireshark_session_manager.create_session(
        str(link_id),
        project_id,
        token
    )

    # 4. Send current state
    if session.state == SessionState.PENDING or session.state == SessionState.STARTING:
        await websocket.send_json({
            "type": "waiting",
            "message": "Starting Wireshark, please wait..."
        })
    elif session.state == SessionState.ERROR:
        await websocket.send_json({
            "type": "error",
            "message": session.error_message
        })
        await websocket.close(code=4002, reason=session.error_message)
        return

    # 5. Wait for ready (if not already)
    if session.state != SessionState.READY:
        for _ in range(30):  # 30 * 0.5s = 15s
            await asyncio.sleep(0.5)
            session = await wireshark_session_manager.get_session(str(link_id))
            if not session:
                await websocket.close(code=4004, reason="Session not found")
                return
            if session.state == SessionState.READY:
                break
            elif session.state == SessionState.ERROR:
                await websocket.send_json({
                    "type": "error",
                    "message": session.error_message
                })
                await websocket.close(code=4002, reason=session.error_message)
                return
        else:
            await websocket.close(code=4003, reason="Session ready timeout")
            return

    # 6. Send ready message
    await websocket.send_json({
        "type": "ready",
        "display": session.display,
        "xpra_ws": wireshark_session_manager.get_xpra_ws_url(session)
    })

    # 7. Start heartbeat
    heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket))

    # 8. Proxy to xpra
    try:
        xpra_ws_url = wireshark_session_manager.get_xpra_ws_url(session)
        async with websockets.connect(xpra_ws_url) as xpra_ws:
            proxy_task = asyncio.create_task(_proxy_loop(websocket, xpra_ws))

            done, pending = await asyncio.wait(
                [proxy_task, heartbeat_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except websockets.WebSocketException as e:
        log.error(f"xpra WebSocket error: {e}")
    finally:
        # Check if link is still capturing
        link = await get_link_by_id(str(link_id))
        if link and not link.capturing:
            await wireshark_session_manager.close_session(str(link_id))


async def _heartbeat_loop(websocket: WebSocket, interval: float = 10, timeout: float = 30):
    """Send pings and disconnect if no pong."""
    try:
        while True:
            await asyncio.sleep(interval)
            try:
                await websocket.ping()
                await asyncio.wait_for(websocket.wait_for_pong(), timeout=timeout)
            except asyncio.TimeoutError:
                log.warning("WebSocket heartbeat timeout")
                break
            except Exception:
                break
    except asyncio.CancelledError:
        pass


async def _proxy_loop(browser_ws: WebSocket, xpra_ws, buffer_size: int = 8192):
    """Bidirectional proxy between browser and xpra."""
    async def forward_from_browser():
        try:
            while True:
                data = await browser_ws.receive_bytes()
                await xpra_ws.send(data)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    async def forward_to_browser():
        try:
            while True:
                data = await xpra_ws.recv()
                if isinstance(data, str):
                    await browser_ws.send_text(data)
                else:
                    await browser_ws.send_bytes(data)
        except websockets.WebSocketException:
            pass
        except Exception:
            pass

    await asyncio.gather(
        forward_from_browser(),
        forward_to_browser(),
    )
```

## Capture Stream Consumption

Wireshark fetches pcap data from GNS3 Server's stream API using token from file (not CLI).

```bash
# Inside Wireshark container, executed as link-{uuid} user
# Token is read from file, not passed as command line argument

su - link-${LINK_ID} -c 'DISPLAY=${DISPLAY} wireshark \
  -i <(curl -N -H "Authorization: Bearer $(cat /tmp/sessions/link-${LINK_ID}/token)" \
    http://gns3-server:3080/v3/links/${LINK_ID}/capture/stream) &'
```

**Security improvement over original design:**

| Aspect | Original (Insecure) | Updated (Secure) |
|--------|---------------------|------------------|
| Token location | CLI argument | Session file `/tmp/sessions/link-{uuid}/token` |
| Token visibility | `ps aux` shows token | Token only readable by user process |
| Shell history | Token in history | No token in history |
| Cleanup | May leave traces | File deleted on session cleanup |

## API (Extended Existing Capture API)

### Start Capture with Wireshark

```http
POST /v3/links/{link_id}/capture/start

Request:
{
  "wireshark": true   // Optional, enable wireshark view
}

Response (Link object + new fields):
{
  "link_id": "xxx",
  "capturing": true,
  "wireshark_ws": "ws://gns3-server:3080/v3/links/{link_id}/capture/wireshark"
}
```

### Stop Capture

```http
POST /v3/links/{link_id}/capture/stop

Request:
{
  "wireshark": true   // Optional, cleanup wireshark session
}

Response: 204 No Content
```

### Wireshark WebSocket Protocol

```http
ws://gns3-server:3080/v3/links/{link_id}/capture/wireshark
Authorization: Bearer {jwt_token}
```

**Server-to-Client Messages:**

```json
// Waiting for session ready
{"type": "waiting", "message": "Starting Wireshark, please wait..."}

// Session is ready
{"type": "ready", "display": ":0", "xpra_ws": "ws://wireshark-container:10000"}

// Session creation failed
{"type": "error", "message": "Failed to start Wireshark: Ansible error"}
```

**Client Usage (JavaScript):**

```javascript
const ws = new WebSocket(
  `ws://gns3-server:3080/v3/links/${linkId}/capture/wireshark`,
  [],
  { headers: { Authorization: `Bearer ${jwtToken}` } }
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'waiting') {
    showWaitingUI(msg.message);
  } else if (msg.type === 'ready') {
    // Connect noVNC to xpra via GNS3 Server proxy (no password needed)
    connectNoVNC(msg.xpra_ws);
  } else if (msg.type === 'error') {
    showErrorUI(msg.message);
    ws.close();
  }
};

function connectNoVNC(xpraWsUrl) {
  // xpra HTML client connects via GNS3 Server WebSocket proxy
  // GNS3 Server has already authenticated the user via JWT
  const rfb = new RFB(document.getElementById('vnc-canvas'), xpraWsUrl);
}
```

## Ansible Playbooks

### Playbook 1: Create Wireshark Container (Project-Level)

**File:** `wireshark_container_create.yml`

**Variables passed to Ansible:**

| Variable | Description |
|----------|-------------|
| `project_id` | Project UUID |

```yaml
---
- name: Create Wireshark Container for Project
  hosts: wireshark_hosts
  gather_facts: no
  vars:
    container_name: "gns3-ws-{{ project_id }}"
  tasks:
    - name: Check if container already exists
      shell: docker ps -a --format '{{.Names}}' | grep -x "{{ container_name }}"
      register: container_exists
      ignore_errors: yes

    - name: Create and start container
      shell: |
        docker run -d \
          --name {{ container_name }} \
          --hostname wireshark-{{ project_id[:8] }} \
          --memory=4g \
          --cpus=2 \
          gns3/wireshark-server:latest \
          /start.sh
      when: container_exists.stdout == ""

    - name: Wait for container to be ready
      wait_for:
        port: 10000
        timeout: 30
      when: container_exists.stdout == ""
```

### Playbook 2: Delete Wireshark Container (Project-Level)

**File:** `wireshark_container_delete.yml`

```yaml
---
- name: Delete Wireshark Container for Project
  hosts: wireshark_hosts
  gather_facts: no
  vars:
    container_name: "gns3-ws-{{ project_id }}"
  tasks:
    - name: Stop and remove container
      shell: docker rm -f {{ container_name }} || true
```

### Playbook 3: Create Wireshark Session (Link-Level)

**File:** `wireshark_session_create.yml`

**Variables passed to Ansible:**

| Variable | Description |
|----------|-------------|
| `link_id` | Link UUID |
| `project_id` | Project UUID |
| `user_token` | User's JWT token for capture/stream access |
| `display` | Assigned X display number (e.g., :0) |

```yaml
---
- name: Create Wireshark Session for Link
  hosts: wireshark_hosts
  gather_facts: no
  vars:
    gns3_server: "{{ gns3_server_url | default('http://gns3-server:3080') }}"
    session_dir: "/tmp/sessions/link-{{ link_id }}"
    container_name: "gns3-ws-{{ project_id }}"
  tasks:
    - name: Create session directory
      shell: docker exec {{ container_name }} mkdir -p {{ session_dir }} && \
                       docker exec {{ container_name }} chmod 1777 {{ session_dir }}

    - name: Write JWT token to file (secure, not CLI)
      shell: |
        docker exec {{ container_name }} tee {{ session_dir }}/token > /dev/null <<< "{{ user_token }}"
        docker exec {{ container_name }} chmod 0600 {{ session_dir }}/token

    - name: Create Linux user for link
      shell: docker exec {{ container_name }} useradd -r -s /usr/sbin/nologin link-{{ link_id }} || true

    - name: Create cgroup for resource limits
      shell: |
        docker exec {{ container_name }} sh -c '
          mkdir -p /sys/fs/cgroup/memory/link-{{ link_id }} || true
          mkdir -p /sys/fs/cgroup/pids/link-{{ link_id }} || true
          echo 2147483648 > /sys/fs/cgroup/memory/link-{{ link_id }}/memory.limit_in_bytes || true
          echo 50 > /sys/fs/cgroup/pids/link-{{ link_id }}/pids.max || true
        '

    - name: Start xpra session (no local auth - GNS3 Server is trusted gateway)
      shell: |
        docker exec -d {{ container_name }} bash -c '
          su - link-{{ link_id }} -s /bin/bash -c "DISPLAY={{ display }} xpra start {{ display }}
            --html=on
            --bind-tcp=0.0.0.0:10000
            --auth=allow
            --socket-permissions=0700
            --dpi=96" || true
        '

    - name: Wait for xpra to be ready
      wait_for:
        port: 10000
        timeout: 10

    - name: Start wireshark (token read from file, not CLI)
      shell: |
        docker exec -d {{ container_name }} bash -c '
          TOKEN_FILE={{ session_dir }}/token
          su - link-{{ link_id }} -s /bin/bash -c "DISPLAY={{ display }} bash -c \x27
            while [ ! -f $TOKEN_FILE ]; do sleep 0.5; done
            wireshark -i <(curl -N -H \"Authorization: Bearer \$(cat $TOKEN_FILE)\" \
              {{ gns3_server }}/v3/links/{{ link_id }}/capture/stream) \
              -o \"gui.window_title:Link:{{ link_id}}\" &
          \x27"
        '
```

### Playbook 4: Cleanup Wireshark Session (Link-Level)

**File:** `wireshark_session_cleanup.yml`

```yaml
---
- name: Cleanup Wireshark Session
  hosts: wireshark_hosts
  gather_facts: no
  vars:
    session_dir: "/tmp/sessions/link-{{ link_id }}"
    container_name: "gns3-ws-{{ project_id }}"
  tasks:
    - name: Stop wireshark process
      shell: docker exec {{ container_name }} pkill -9 -u "link-{{ link_id }}" wireshark || true

    - name: Stop xpra session
      shell: docker exec {{ container_name }} su - link-{{ link_id }} -s /bin/bash -c "DISPLAY={{ display }} xpra stop {{ display }}" || true

    - name: Cleanup cgroups
      shell: |
        docker exec {{ container_name }} sh -c '
          rmdir /sys/fs/cgroup/memory/link-{{ link_id }} 2>/dev/null || true
          rmdir /sys/fs/cgroup/pids/link-{{ link_id }} 2>/dev/null || true
        '

    - name: Remove Linux user
      shell: docker exec {{ container_name }} userdel "link-{{ link_id }}" || true

    - name: Remove session directory (includes token file)
      shell: docker exec {{ container_name }} rm -rf {{ session_dir }}
```

### Playbook 5: Check Session Status

**File:** `wireshark_session_status.yml`

```yaml
---
- name: Check Wireshark Session Status
  hosts: wireshark_hosts
  gather_facts: no
  vars:
    session_dir: "/tmp/sessions/link-{{ link_id }}"
    container_name: "gns3-ws-{{ project_id }}"
  tasks:
    - name: Check if user exists
      shell: docker exec {{ container_name }} id "link-{{ link_id }}" 2>/dev/null && echo "exists" || echo "not_found"
      register: user_check

    - name: Check if xpra session is running
      shell: docker exec {{ container_name }} ps aux | grep -v grep | grep "xpra.*{{ display }}" | grep "link-{{ link_id }}" || true
      register: xpra_check

    - name: Check if wireshark is running
      shell: docker exec {{ container_name }} ps aux | grep -v grep | grep "wireshark" | grep "link-{{ link_id }}" || true
      register: wireshark_check

    - name: Check if session directory exists
      shell: docker exec {{ container_name }} test -d {{ session_dir }} && echo "exists" || echo "not_found"
      register: session_dir_check

    - name: Set session status
      set_fact:
        session_status:
          link_id: "{{ link_id }}"
          display: "{{ display }}"
          user_exists: "{{ 'exists' in user_check.stdout }}"
          xpra_running: "{{ xpra_check.stdout != '' }}"
          wireshark_running: "{{ wireshark_check.stdout != '' }}"
          session_dir_exists: "{{ 'exists' in session_dir_check.stdout }}"
          status: "{{ 'running' if ('exists' in user_check.stdout and wireshark_check.stdout != '') else 'stopped' }}"
```

### Inventory Example

```ini
[wireshark_hosts]
wireshark-01 ansible_host=192.168.1.100 ansible_user=root

[wireshark_hosts:vars]
gns3_server_url=http://192.168.1.50:3080
```

### Execution Examples

```bash
# Create container for project
ansible-playbook wireshark_container_create.yml \
  -e "project_id=76ead2b0-fd00-407c-b5db-abc83445886e"

# Delete container for project
ansible-playbook wireshark_container_delete.yml \
  -e "project_id=76ead2b0-fd00-407c-b5db-abc83445886e"

# Create session for link
ansible-playbook wireshark_session_create.yml \
  -e "link_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "project_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "user_token=eyJhbGc..." \
  -e "display=:0"

# Cleanup session
ansible-playbook wireshark_session_cleanup.yml \
  -e "link_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "project_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "display=:0"

# Check status
ansible-playbook wireshark_session_status.yml \
  -e "link_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "project_id=76ead2b0-fd00-407c-b5db-abc83445886e" \
  -e "display=:0"
```

## Component Responsibilities

| Component | Role |
|-----------|------|
| GNS3 Server | Capture data provider (persistent storage), WebSocket proxy, session manager |
| ProjectContainerManager | Container lifecycle (create/delete per project) |
| WiresharkSessionManager | Session lifecycle (create/cleanup per link) |
| DisplayManager | Tracks X display numbers per container (:0-:10) |
| `capture/stream` API | Streams pcap data via HTTP to authorized consumers |
| WebSocket Proxy | Forwards browser connection to Wireshark container |
| Ansible | Handles container and session operations on hosts |
| Wireshark Container | Project-level container, hosts multiple Wireshark sessions via xpra |
| xpra | Manages multiple X sessions, provides WebSocket/VNC |
| noVNC | Bridges xpra X session to browser (via proxy) |
| Linux User (per link_id) | Isolates processes, files, resources per session |
| cgroups | Enforces resource limits per user |
| Session Files | Stores JWT token and xpra password securely (not in CLI) |

## Security

| Concern | Mitigation |
|---------|------------|
| JWT token in CLI | Token stored in session file, mode 0600, read by Wireshark process |
| Token in shell history | Token written to file instead of using shell history |
| Token visible in `ps aux` | Token file only readable by `link-{uuid}` user |
| Browser directly accessing container | All access via GNS3 Server WebSocket proxy |
| Unauthorized WebSocket connection | JWT validation + link ownership check |
| Resource abuse by Wireshark | cgroups limit memory (2GB) and processes (50) per user |
| xpra unauthorized access | `--auth=allow` trusts connections from GNS3 Server (network isolated) |
| Token expiration | Token passed at session create time; Wireshark uses it until session ends |
| Container isolation | One container per project provides project-level isolation |

### Trust Model

```
┌─────────────────────────────────────────────────────────────────┐
│                        Trust Boundary                           │
│                                                                  │
│  ┌─────────────┐     JWT validated      ┌──────────────────┐    │
│  │   Browser   │ ─────────────────────► │   GNS3 Server   │    │
│  │             │      at this point      │  (WebSocket)    │    │
│  └─────────────┘                        └────────┬─────────┘    │
│                                                   │               │
│  Browser has NO direct access to container.       │ GNS3 Server  │
│  All traffic flows through GNS3 Server proxy.     │ is trusted   │
│                                                   │               │
│                                                   ▼               │
│                                          ┌──────────────────┐   │
│                                          │ Wireshark        │   │
│                                          │ Container        │   │
│                                          │ (project-level)  │   │
│                                          └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

xpra uses --auth=allow, meaning:
- GNS3 Server is the only entity that can reach xpra port
- GNS3 Server has already authenticated the user via JWT
- Container network should be firewalled to only allow GNS3 Server
```

## Session Lifecycle Detail

| Event | Action | State Transition |
|-------|--------|------------------|
| Project opens | Ansible creates container | container: stopped → running |
| User clicks View Wireshark | Allocate display, trigger Ansible create | session: idle → pending |
| Ansible starts running | xpra and wireshark processes starting | pending → starting |
| Ansible completes successfully | Session ready for viewing | starting → ready |
| Ansible fails | Session error | starting → error |
| User connects noVNC | WebSocket proxy to xpra | (no state change) |
| User disconnects noVNC | Session keeps running if still capturing | (no state change) |
| User clicks Stop Wireshark View | Trigger Ansible cleanup | any → closing |
| Cleanup completes | Release display, remove session | closing → idle |
| Project closes | Ansible destroys container, cleanup all sessions | container: running → stopped |
| GNS3 Server restarts | Container survives (project still open) | container stays running |
| Container restart | Container recreated when project next accessed | container: stopped → running |

## Capture Storage

- GNS3 Server saves capture to project directory (existing behavior)
  - Path: `/path/to/projects/{project_id}/project-files/captures/`
- Wireshark consumes real-time stream from `capture/stream` API
- Users can download full capture file anytime via existing download API
- **Wireshark container does NOT persist capture data (stateless viewer)**
- Capture files persist independently of container lifecycle

## Wireshark Container

### Dockerfile

```dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    wireshark \
    xpra \
    xvfb \
    curl \
    openssh-server \
    python3 \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# SSH configuration for Ansible access
RUN mkdir /var/run/sshd

# Create sessions directory
RUN mkdir -p /tmp/sessions && chmod 1777 /tmp/sessions

# Container startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Expose ports
EXPOSE 10000 22

CMD ["/start.sh"]
```

### start.sh

```bash
#!/bin/bash
# /start.sh - Container entrypoint

# Start SSH for Ansible access
service ssh start

# Start xpra in daemon mode
xpra start :0 --html=on --bind-tcp=0.0.0.0:10000 --auth=allow --daemonize

# Keep container running
tail -f /dev/null
```

### Container Components

| Component | Purpose |
|-----------|---------|
| wireshark | GUI rendering of pcap stream from GNS3 Server |
| xpra | Multi-user X session management, WebSocket support |
| xvfb | Virtual framebuffer for headless X |
| curl | HTTP client to fetch pcap stream |
| openssh-server | Ansible remote execution |

### Running Containers

```bash
# Containers are created/destroyed by Ansible
# Example docker run (executed by Ansible):
docker run -d \
  --name gns3-ws-{project_id} \
  --hostname wireshark-{project_id[:8]} \
  --memory=4g \
  --cpus=2 \
  gns3/wireshark-server:latest \
  /start.sh
```

### Container Internal Structure

```
/
├── tmp/
│   └── sessions/
│       └── link-{uuid}/
│           └── token          # JWT token for capture/stream API (0600)
├── sys/fs/cgroup/             # cgroups mounts
└── usr/bin/
    ├── wireshark
    ├── xpra
    └── xvfb-run
```

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| ProjectContainerManager | TODO | Container lifecycle management |
| DisplayManager | TODO | Per-container display allocation (:0-:10) |
| WiresharkSessionManager | TODO | Session state machine + Ansible runner |
| WebSocket Handler | TODO | FastAPI WebSocket with state protocol |
| Ansible Playbooks | TODO | Container and session playbooks |
| Dockerfile + start.sh | TODO | Container image with startup script |
| Link API modifications | TODO | Add wireshark=true to start/stop |
| Frontend integration | TODO | Connect to WebSocket, show noVNC |

## Troubleshooting

| Issue | Diagnosis | Solution |
|-------|-----------|----------|
| WebSocket closes with 4001 | JWT token invalid | Refresh token, check link ownership |
| WebSocket closes with 4004 | Session not found | Click "View in Wireshark" first |
| Message type is "waiting" forever | Ansible not completing | Check Ansible logs |
| Message type is "error" | Session creation failed | Check error message, verify container reachable |
| noVNC connects but shows black screen | Wireshark not started | Check wireshark process via status playbook |
| xpra connection refused | Container not running | Check project is open |
| Capture not showing in Wireshark | Token expired or API issue | Token validity tied to session lifetime |
| Container not found | Project container not created | Check project is open |

## Future Enhancements

1. **AWX/Tower Integration** - Replace subprocess calls with AWX API for better orchestration
2. **Session Recovery** - Persist session state to survive GNS3 Server restarts
3. **Multiple Viewers** - Allow multiple browsers to view same Wireshark session (read-only mode)
4. **Session Recording** - Save Wireshark interaction for playback
5. **Container Image Variants** - Different images for different project types (security, basic, etc.)
