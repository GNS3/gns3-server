<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# VNC WebSocket Console

## Overview

GNS3 server supports WebSocket-based VNC console access, enabling browser-based graphical console connections to QEMU and Docker VMs without requiring standalone VNC client applications.

This implementation uses GNS3's API layer as a transparent WebSocket-to-TCP proxy, forwarding binary VNC protocol data between the browser and the VM's VNC server.

## Architecture

### Connection Flow

```
┌─────────┐     WebSocket      ┌─────────────┐     HTTP/WS     ┌──────────┐
│ Browser │ ◄─────────────────► │   GNS3      │ ◄──────────────► │  GNS3    │
│ noVNC   │   (wss://port)      │  Controller │   (JWT + RBAC)   │ Compute  │
└─────────┘                     └─────────────┘                  └─────┬────┘
                                                                         │
                                                                         │ TCP
                                                                         │
                                                                    ┌────▼────┐
                                                                    │  QEMU   │
                                                                    │  VNC    │
                                                                    │ :5900   │
                                                                    └─────────┘
```

### Components

1. **Browser (noVNC)**
   - HTML5 VNC client running in the browser
   - Connects via WebSocket using `binary` subprotocol
   - Handles RFB protocol (Remote Frame Buffer) for VNC

2. **GNS3 Controller API**
   - WebSocket endpoint: `/v3/projects/{project_id}/nodes/{node_id}/console/vnc`
   - Authentication: JWT token via query parameter
   - Authorization: RBAC privilege check (`Node.Console`)
   - Forwards WebSocket connections to compute node

3. **GNS3 Compute API**
   - WebSocket endpoint: `/v3/compute/projects/{project_id}/qemu/nodes/{node_id}/console/vnc`
   - Authentication: HTTP Basic Auth
   - Transparent bidirectional binary forwarding

4. **Node (QEMU/Docker)**
   - VNC server listening on configured port (default: 5900+)
   - RFB protocol for remote display

## API Endpoints

### Controller WebSocket Endpoint

**URL**: `ws://{controller_host}:{port}/v3/projects/{project_id}/nodes/{node_id}/console/vnc?token={jwt_token}`

**Authentication**:
- JWT token via query parameter
- User must have `Node.Console` privilege

**WebSocket Subprotocols**:
- Accepts: `binary`
- Used by noVNC for binary data transfer

**Request Example**:
```javascript
const token = "eyJ0eXAiOiJKV1QiLCJhbGc...";
const wsUrl = `ws://localhost:3080/v3/projects/${projectId}/nodes/${nodeId}/console/vnc?token=${token}`;

const ws = new WebSocket(wsUrl, 'binary');
ws.binaryType = 'arraybuffer';
```

### Compute WebSocket Endpoint

**URL**: `ws://{compute_host}:{port}/v3/compute/projects/{project_id}/{node_type}/nodes/{node_id}/console/vnc`

**Authentication**:
- HTTP Basic Auth (controller credentials)
- Configured via `settings.Server.compute_username` and `settings.Server.compute_password`

**Response**:
- Bidirectional binary WebSocket connection
- Transparent VNC protocol forwarding

## Supported Node Types

### QEMU VMs

**Console Type Configuration**:
```json
{
  "console_type": "vnc",
  "console": 5900,
  "console_resolution": "1024x768"
}
```

**QEMU Parameters**:
```bash
-vnc :0  # VNC on display 0 (port = 5900 + display)
```

**Implementation**:
- File: `gns3server/api/routes/compute/qemu_nodes.py`
- Endpoint: `/{node_id}/console/vnc`
- Method: `start_vnc_websocket_console(websocket)`

### Docker Containers

**Console Type Configuration**:
```json
{
  "console_type": "vnc",
  "console": 5900,
  "console_resolution": "1024x768",
  "console_http_port": 8080,
  "console_http_path": "/"
}
```

**Implementation**:
- File: `gns3server/api/routes/compute/docker_nodes.py`
- Endpoint: `/{node_id}/console/vnc`
- Method: `start_vnc_websocket_console(websocket)`

## WebSocket Data Forwarding

### Implementation Details

**Location**: `gns3server/compute/base_node.py:544-612`

```python
async def start_vnc_websocket_console(self, websocket):
    """Connect to VNC console using WebSocket."""

    # 1. Validation
    if self.status != "started":
        await websocket.close(code=1000)
        raise NodeError(f"Node {self.name} is not started")
    if self._console_type != "vnc":
        await websocket.close(code=1000)
        raise NodeError(f"Node {self.name} console type is not vnc")

    # 2. Connect to VNC server
    vnc_reader, vnc_writer = await asyncio.open_connection(
        self._manager.port_manager.console_host,
        self.console
    )

    # 3. Bidirectional forwarding
    async def ws_forward(vnc_writer):
        # Browser → VNC: Forward WebSocket data to VNC server
        while True:
            data = await websocket.receive_bytes()
            if data:
                vnc_writer.write(data)
                await vnc_writer.drain()

    async def vnc_forward(vnc_reader):
        # VNC → Browser: Forward VNC data to WebSocket
        while not vnc_reader.at_eof():
            data = await vnc_reader.read(4096)
            if data:
                await websocket.send_bytes(data)

    # 4. Run both forwarding tasks
    aws = [
        asyncio.create_task(ws_forward(vnc_writer)),
        asyncio.create_task(vnc_forward(vnc_reader))
    ]

    done, pending = await asyncio.wait(aws, return_when=asyncio.FIRST_COMPLETED)

    # 5. Cleanup
    for task in pending:
        task.cancel()
    vnc_writer.close()
    await vnc_writer.wait_closed()
```

### Data Flow

```
Browser (noVNC)                    GNS3 Compute                  QEMU VNC
     │                                  │                            │
     │  WebSocket Frame (Binary)        │                            │
     ├─────────────────────────────────►│                            │
     │  receive_bytes()                 │                            │
     │                                  │  TCP Socket                │
     │                                  ├───────────────────────────►│
     │                                  │  write(data)               │
     │                                  │                            │
     │                                  │  TCP Socket                │
     │                                  │◄──────────────────────────┤
     │  WebSocket Frame (Binary)        │  read(4096)                │
     │◄─────────────────────────────────┤                            │
     │  send_bytes(data)                │                            │
```

## Frontend Integration

### noVNC Integration

**Location**: `gns3-web-ui/src/assets/vnc-console/`

**Files**:
- `index.html` - VNC console page
- `vnc-controller.js` - VNC connection controller
- `novnc/` - noVNC library files

**Connection Example**:
```javascript
const sc = new RFB(document.getElementById('vnc-canvas'), {
  target: vncWsUrl,  // ws://controller:port/v3/projects/.../console/vnc?token=...
  credentials: { password: vncPassword }
});

sc.addEventListener('connect', () => {
  console.log('VNC connected');
});

sc.addEventListener('disconnect', (e) => {
  console.log('VNC disconnected:', e);
});
```

### Console Service

**Location**: `gns3-web-ui/src/app/services/vnc-console.service.ts`

**Methods**:
- `buildVncWebSocketUrl()` - Construct WebSocket URL
- `openVncConsole()` - Open console in new window
- `buildVncConsolePageUrl()` - Build standalone page URL

## Authentication & Authorization

### Controller Layer

1. **Authentication**:
   - JWT token validation via `get_current_active_user_from_websocket()`
   - Token passed as query parameter: `?token={jwt}`

2. **Authorization**:
   - RBAC privilege check: `Node.Console`
   - Per-node access control

3. **WebSocket Subprotocol**:
   - Client requests: `binary`
   - Server accepts: `binary` (if requested)

### Compute Layer

1. **Authentication**:
   - HTTP Basic Auth
   - Credentials from controller config
   - Username: `settings.Server.compute_username`
   - Password: `settings.Server.compute_password`

2. **Node Validation**:
   - Check node exists
   - Check node is started
   - Check console type is `vnc`

## Configuration

### Server Settings

**Controller Configuration** (`gns3-server.conf`):
```ini
[Server]
host = 0.0.0.0
port = 3080
```

**Compute Configuration** (same file):
```ini
[Server]
compute_username = gns3
compute_password = gns3
```

### Node Settings

**QEMU VM Example**:
```json
{
  "name": "vm-1",
  "node_type": "qemu",
  "console_type": "vnc",
  "console": 5900,
  "console_resolution": "1280x720",
  "properties": {
    "qemu_path": "/usr/bin/qemu-system-x86_64"
  }
}
```

**Docker Container Example**:
```json
{
  "name": "container-1",
  "node_type": "docker",
  "console_type": "vnc",
  "console": 5900,
  "console_resolution": "1024x768",
  "console_http_port": 8080
}
```

## Troubleshooting

### Common Issues

**1. "Node is not started"**
- **Symptom**: WebSocket closes immediately
- **Solution**: Start the VM before opening console
- **API Check**: `GET /v3/projects/{project_id}/nodes/{node_id}` → verify `status == "started"`

**2. "Console type is not vnc"**
- **Symptom**: WebSocket closes with error
- **Solution**: Set node console_type to "vnc"
- **API Update**: `PUT /v3/projects/{project_id}/nodes/{node_id}` with `{"console_type": "vnc"}`

**3. "Cannot connect to VNC server"**
- **Symptom**: Connection timeout
- **Possible Causes**:
  - VNC server not listening
  - Port conflict
  - Firewall blocking connection
- **Verification**:
  ```bash
  # Check if VNC is listening
  netstat -tlnp | grep 5900

  # Check QEMU process
  ps aux | grep qemu
  ```

**4. WebSocket Subprotocol Negotiation Failed**
- **Symptom**: Connection rejected during handshake
- **Solution**: Ensure noVNC sends `binary` subprotocol
- **Browser Console Check**:
  ```javascript
  console.log(ws.protocol);  // Should be "binary"
  ```

**5. Authentication Errors**
- **Symptom**: HTTP 401/403 responses
- **Controller**: Check JWT token is valid and not expired
- **Compute**: Verify compute username/password in config

### Debug Logging

**Enable Detailed Logging**:
```ini
[gns3server]
debug = true
```

**Check Controller Logs**:
```bash
# Look for WebSocket connection messages
grep "VNC console WebSocket" /var/log/gns3/gns3.log
```

**Check Compute Logs**:
```bash
# Look for VNC forwarding messages
grep "Connected to VNC server" /var/log/gns3/gns3.log
```

**Browser Console**:
```javascript
// Enable noVNC debugging
RFB.messages.log = function(msg) { console.log(msg); };
```

## Performance Considerations

### Bandwidth

- **Typical Usage**: 1-5 Mbps per active VNC session
- **Full HD (1920x1080)**: Up to 10 Mbps with rapid screen changes
- **Optimization**: Use lower resolution for slower connections

### Latency

- **Target**: < 50ms for local connections
- **Factors**:
  - Network latency
  - WebSocket frame processing overhead
  - VNC encoding efficiency
- **Mitigation**:
  - Use QXL driver for QEMU VMs
  - Enable VNC password authentication (reduces overhead)
  - Adjust console resolution

### Concurrent Connections

- **Multiple Clients**: Each VNC console supports one WebSocket connection
- **Multi-viewer**: Not supported (VNC protocol limitation)
- **Shared Sessions**: Use SPICE for multi-client support

## Security

### Authentication

1. **Controller → Client**
   - JWT token with expiration
   - RBAC authorization
   - Privilege: `Node.Console`

2. **Controller → Compute**
   - HTTP Basic Auth over TLS (recommended)
   - Separate compute credentials

3. **VNC Server**
   - Optional VNC password (QEMU only)
   - Configured via node properties

### Network Security

**Recommendations**:
1. Use HTTPS/WSS for production deployments
2. Firewall compute API ports
3. Use short-lived JWT tokens
4. Enable VNC password for sensitive VMs

**Example**:
```bash
# Controller with TLS
gns3server --ssl --cert /path/to/cert.pem --key /path/to/key.pem

# VNC with password
qemu-system-x86_64 -vnc :0,password
```

### WebSocket Security

**Subprotocol Validation**:
- Only `binary` subprotocol is accepted
- Prevents protocol downgrade attacks

**Origin Validation**:
- Browser enforces same-origin policy
- Configure CORS if using separate domains

## Limitations

1. **Single Client per VNC Port**
   - VNC protocol supports one client at a time
   - New connections disconnect existing clients

2. **No Audio Redirection**
   - VNC doesn't support audio
   - Use SPICE for audio support

3. **No USB Redirection**
   - VNC doesn't support device redirection
   - Use SPICE for USB support

4. **Performance**
   - Higher CPU usage than native VNC clients
   - Binary forwarding adds processing overhead

## Comparison with SPICE

| Feature | VNC WebSocket | SPICE WebSocket |
|---------|---------------|-----------------|
| **Browser Support** | ✅ Excellent | ✅ Good (with spice-html5) |
| **Audio Redirection** | ❌ No | ✅ Yes |
| **USB Redirection** | ❌ No | ✅ Yes |
| **Clipboard Sharing** | ⚠️ Limited | ✅ Full |
| **Multi-monitor** | ✅ Yes | ✅ Yes |
| **Performance** | ⚠️ Moderate | ✅ Better |
| **Guest Agent** | ❌ No | ✅ Yes (spice-vdagent) |
| **Stability** | ✅ Very Stable | ⚠️ Moderate |
| **Implementation** | ✅ Complete | ❌ Removed (dependencies) |

## Future Enhancements

Planned improvements:

1. **WebSocket Compression**
   - Enable per-message compression
   - Reduce bandwidth usage

2. **Connection Pooling**
   - Reuse WebSocket connections
   - Reduce connection overhead

3. **Recording Support**
   - Record VNC sessions
   - Playback functionality

4. **Multi-viewer Mode**
   - Read-only shared viewing
   - Teacher/student scenarios

## References

- [RFB Protocol 3.8](https://tools.ietf.org/html/rfc6143) - VNC Protocol Specification
- [noVNC Documentation](https://github.com/novnc/noVNC) - HTML5 VNC Client
- [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/) - WebSocket Implementation
- [GNS3 Documentation](https://docs.gns3.com/) - General GNS3 Documentation

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-17 | Initial VNC WebSocket documentation |
| 0.9 | 2026-03-15 | Added VNC WebSocket support to QEMU and Docker |
