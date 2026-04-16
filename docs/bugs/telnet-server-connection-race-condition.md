<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# Telnet Server Connection Race Condition Bug

## Bug Report

**Date**: 2026-03-14
**Severity**: High
**Status**: Open
**Component**: Telnet Server (`gns3server/utils/asyncio/telnet_server.py`)

## Error Logs

```
2026-03-14 15:21:31 ERROR asyncio:1879 Unhandled exception in client_connected_cb
transport: <_SelectorSocketTransport fd=67 read=polling write=<idle, bufsize=0>>
Traceback (most recent call last):
  File "/home/yueguobin/myCode/GNS3/gns3-server/gns3server/utils/asyncio/telnet_server.py", line 215, in run
    await self._process(network_reader, network_writer, connection)
  File "/home/yueguobin/myCode/GNS3/gns3-server/gns3server/utils/asyncio/telnet_server.py", line 305, in _process
    client_info = connection_key.get_extra_info("socket").getpeername()
  File "/usr/lib64/python3.13/asyncio/trsock.py", line 77, in getpeername
    return self._sock.getpeername()
           ~~~~~~~~~~~~~~~~~~~~~~^^
OSError: [Errno 107] Transport endpoint is not connected
```

## Root Cause Analysis

### Architecture

The GNS3 Telnet server architecture supports multiple concurrent client connections to a single node console:

```
┌──────────────────────────────────────────────────────────┐
│  Node (VPCS/Docker/Router/Switch, etc.)                  │
│  - Independent process                                   │
│  - Normal operation, processing business logic           │
└────────────────────┬─────────────────────────────────────┘
                     │ stdout (device output)
                     │
        ┌────────────▼─────────────────────────────────────┐
        │   AsyncioTelnetServer (Telnet Proxy Server)      │
        │   - Reads output from Node                        │
        │   - Broadcasts to all connected clients           │
        │   - ← ← Bug occurs at this layer ← ←             │
        └────────────┬─────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬──────────────────┐
        │            │            │                  │
    Web Console   Auto Script   Client 1           Client 2
   (long-lived)  (quick disco)  (normal)           (normal)
```

### The Race Condition

The bug occurs in the broadcast logic when a client disconnects while the server is iterating through connections:

**Timeline**:
```
t1: Clients A, B, C connect to the same Telnet port
t2: Device has output (e.g., log message)
t3: Client A receives data and script immediately disconnects (FIN sent)
t4: Server hasn't read EOF yet (event loop hasn't checked this connection)
t5: Server iterates through connections to broadcast data
t6: When iterating to Client A, getpeername() is called → OSError!
```

### Code Location

**File**: `gns3server/utils/asyncio/telnet_server.py`
**Line**: 305

**Problematic Code**:
```python
# Line 304-305
for connection_key in list(self._connections.keys()):
    client_info = connection_key.get_extra_info("socket").getpeername()  # ← OSError here
    connection = self._connections[connection_key]

    try:
        connection.writer.write(data)
        await asyncio.wait_for(connection.writer.drain(), timeout=10)
    except:
        log.debug(f"Timeout while sending data to client: {client_info}, closing and removing from connection table.")
        connection.close()
        del self._connections[connection_key]
```

### The Core Issue

The `getpeername()` call is **outside** the try-except block, so any OSError from it is not caught.

Additionally, the top-level exception handler at line 216 only catches `ConnectionError`:

```python
# Line 212-227
try:
    await self._write_intro(network_writer, echo=self._echo, binary=self._binary, naws=self._naws)
    await connection.connected()
    await self._process(network_reader, network_writer, connection)
except ConnectionError:  # ← Only catches ConnectionError
    async with self._lock:
        network_writer.close()
        if self._reader_process == network_reader:
            self._reader_process = None
        if self._current_read is not None:
            self._current_read.cancel()

    await connection.disconnected()
    del self._connections[network_writer]
```

**Python Exception Hierarchy**:
```
BaseException
 └─ Exception
    ├─ ConnectionError  ← Only this is caught
    │  ├─ ConnectionResetError
    │  ├─ BrokenPipeError
    │  └─ ...
    └─ OSError  ← Actually thrown! (not a subclass of ConnectionError)
       └─ [Errno 107] Transport endpoint is not connected
```

Since `OSError` is **not** a subclass of `ConnectionError`, it propagates uncaught to the asyncio event loop.

## Impact Assessment

### Immediate Effects

| Impact | Severity | Description |
|--------|----------|-------------|
| Connection interrupted | 🔴 High | The connection triggering the exception is terminated |
| Resource leak | 🟠 Medium | socket/connection not properly cleaned up |
| Other clients affected | 🟡 Low | Other clients on same port may miss broadcast data |
| Service stability | 🟡 Low | Long-running may accumulate zombie connections |

### User-Reported Symptoms

After this error occurs, users report:

1. **Cannot open the affected node** - Clicking on the node fails
2. **Cannot close the node** - Close button doesn't work
3. **"Node not found" errors** - Operations on the node return 404
4. **Refresh fixes it temporarily** - Reloading the page restores functionality

### Why This Happens

When the uncaught `OSError` occurs, the cleanup code at lines 217-227 **never executes**:

```python
except ConnectionError:
    async with self._lock:
        network_writer.close()           # ✗ Not executed
        if self._reader_process == network_reader:
            self._reader_process = None  # ✗ Not executed
        if self._current_read is not None:
            self._current_read.cancel()  # ✗ Not executed
    await connection.disconnected()      # ✗ Not executed
    del self._connections[network_writer]  # ✗ Not executed
```

This leads to:
- **Resource leaks**: socket and writer not closed, file descriptors leaked
- **State inconsistency**: `_connections` dictionary retains disconnected connections
- **Potential deadlocks**: Locks may not be released if exception occurs while holding them
- **Subsequent operation failures**: Future operations may access zombie connections

### Effect on Node Process

**The Node process itself is NOT affected**:
- Node continues running normally
- Node's stdout has already been read by the proxy
- The bug occurs during the broadcast phase, after data has been read

The issue is in the **Telnet Proxy layer**, not the node itself.

## Trigger Conditions

This error is more likely to occur with:

| Scenario | Probability | Reason |
|----------|-------------|--------|
| **Automated scripts** | 🔴 High | Fast connect → execute → disconnect, small time window |
| **Manual operation** | 🟡 Medium | Can occur (e.g., closing terminal, network fluctuation) |
| **Normal usage** | 🟢 Low | Human operations slower, server usually detects EOF first |

### Typical Scenario

1. User opens Web Console (long-lived connection)
2. Automated script connects → executes command → quickly disconnects
3. While script disconnects, device has output that needs broadcasting
4. During connection iteration, script connection already closed
5. `getpeername()` call fails with OSError

## Related Issues

A secondary issue was found in the error handler:

**File**: `gns3server/api/server.py`
**Line**: 162

```python
@app.exception_handler(ControllerNotFoundError)
async def controller_not_found_error_handler(request: Request, exc: ControllerNotFoundError):
    log.error(f"Controller not found error in {request.url.path} ({request.method}): {exc}")
    #                                                               ^^^^^^^^^^^^^^^
    return JSONResponse(...)
```

**Problem**: `request.method` only exists in HTTP requests, not WebSocket connections.

When a WebSocket request triggers this exception handler:
```
ControllerNotFoundError: Node ID xxx doesn't exist
                  ↓
Attempt to log error
                  ↓
AttributeError: 'WebSocket' object has no attribute 'method'
```

This masks the original error with an attribute error.

## Proposed Fix

### Primary Fix (Telnet Server)

Move `getpeername()` inside the try block and catch OSError:

```python
# Lines 303-314
for connection_key in list(self._connections.keys()):
    connection = self._connections[connection_key]
    client_info = None

    try:
        client_info = connection_key.get_extra_info("socket").getpeername()
        connection.writer.write(data)
        await asyncio.wait_for(connection.writer.drain(), timeout=10)
    except (OSError, ConnectionError, asyncio.TimeoutError) as e:
        log.debug(f"Error sending data to client {client_info}: {e}, closing and removing from connection table.")
        connection.close()
        del self._connections[connection_key]
```

### Secondary Fix (Top-level Exception Handler)

Catch OSError in the main handler to ensure cleanup:

```python
# Lines 212-227
try:
    await self._write_intro(network_writer, echo=self._echo, binary=self._binary, naws=self._naws)
    await connection.connected()
    await self._process(network_reader, network_writer, connection)
except (ConnectionError, OSError):  # ← Add OSError
    async with self._lock:
        network_writer.close()
        if self._reader_process == network_reader:
            self._reader_process = None
        if self._current_read is not None:
            self._current_read.cancel()

    await connection.disconnected()
    del self._connections[network_writer]
```

### Tertiary Fix (API Error Handler)

Fix the WebSocket error handler:

```python
@app.exception_handler(ControllerNotFoundError)
async def controller_not_found_error_handler(request: Request, exc: ControllerNotFoundError):
    method = getattr(request, 'method', 'WebSocket')
    log.error(f"Controller not found error in {request.url.path} ({method}): {exc}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": str(exc)},
    )
```

## Reproduction Steps

**To be documented** after testing.

Potential reproduction scenario:
1. Start a GNS3 node with console enabled (e.g., VPCS)
2. Open web console to keep a long-lived connection
3. Run automated script that:
   - Connects to the same console port
   - Executes a command
   - Immediately disconnects
4. While script is disconnecting, trigger device output
5. Observe the error in logs

## References

- **Files**:
  - `gns3server/utils/asyncio/telnet_server.py:305` (primary issue)
  - `gns3server/utils/asyncio/telnet_server.py:216` (exception handler)
  - `gns3server/api/server.py:162` (secondary issue)

- **Related Commits**:
  - Recent telnet-related work on feature branch

- **Error Patterns**:
  - Race condition in connection management
  - Incomplete exception handling in asyncio code
