# Telnet Server Race Condition Stress Test

## Overview

This stress test reproduces the `OSError: [Errno 107] Transport endpoint is not connected` bug that occurs when clients rapidly connect and disconnect while the telnet server is broadcasting data to multiple clients.

## Background

The bug is a race condition in `gns3server/utils/asyncio/telnet_server.py`:

1. Multiple clients connect to the same telnet console port
2. One client (typically an automated script) quickly connects, sends commands, and disconnects
3. While the client is disconnecting, the telnet server is iterating through connections to broadcast data
4. When the server tries to call `getpeername()` on the disconnected client's socket, it throws `OSError`
5. This exception was not caught, causing it to propagate to the asyncio event loop

## Test Design

### Client Types

1. **Rapid-Fire Clients** (trigger the bug)
   - Quickly connect → send commands → immediately disconnect
   - Simulate automated scripts
   - Use immediate (abrupt) TCP close without graceful shutdown
   - Very short delays (1-10ms)

2. **Long-Lived Clients** (should not be affected)
   - Stay connected for the entire test duration
   - Periodically send commands
   - Simulate web console users
   - Verify they don't experience connection issues

### Race Condition Trigger

```
Timeline:
t1: Rapid client connects
t2: Sends commands
t3: Starts disconnecting (TCP FIN sent)
t4: Server hasn't read EOF yet
t5: Server iterates connections to broadcast
t6: Calls getpeername() on rapid client → OSError!
```

## Usage

### Prerequisites

1. Start a GNS3 node with telnet console enabled (e.g., VPCS)
2. Note the console port (e.g., 2000)
3. Make sure you can connect to it: `telnet 127.0.0.1 2000`

### Basic Test

```bash
# Quick test with default settings
python tests/stress/telnet_race_condition_test.py --port 2000
```

### Heavy Load Test

```bash
# 50 rapid clients, each doing 100 connect/disconnect cycles
python tests/stress/telnet_race_condition_test.py \
    --port 2000 \
    --rapid-clients 50 \
    --iterations 100
```

### Extended Duration Test

```bash
# Run for 2 minutes with multiple long-lived clients
python tests/stress/telnet_race_condition_test.py \
    --port 2000 \
    --rapid-clients 20 \
    --long-lived 5 \
    --iterations 200 \
    --duration 120
```

### Verbose Logging

```bash
# See detailed connection/disconnection logs
python tests/stress/telnet_race_condition_test.py \
    --port 2000 \
    --verbose
```

## Expected Results

### Before Fix

**GNS3 Server Logs:**
```
2026-03-14 23:32:43 ERROR asyncio:1879 Unhandled exception in client_connected_cb
OSError: [Errno 107] Transport endpoint is not connected
```

**Symptoms:**
- ❌ Error logs appear
- ❌ Long-lived clients may miss broadcast data
- ❌ Possible resource leaks
- ❌ Node state may become inconsistent

### After Fix

**GNS3 Server Logs:**
```
2026-03-14 23:35:12 DEBUG gns3server.utils.asyncio.telnet_server:310
Error sending data to client None: [Errno 107] Transport endpoint is not connected,
closing and removing from connection table.
```

**Symptoms:**
- ✅ Only DEBUG level logs (not ERROR)
- ✅ Long-lived clients unaffected
- ✅ Proper resource cleanup
- ✅ Node state remains consistent

## Test Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--host` | 127.0.0.1 | Telnet server host |
| `--port` | 2000 | Telnet server port |
| `--rapid-clients` | 10 | Number of rapid connect/disconnect clients |
| `--long-lived` | 2 | Number of long-lived clients |
| `--iterations` | 50 | Connect/disconnect cycles per rapid client |
| `--duration` | 30.0 | Test duration in seconds |
| `--verbose` | False | Enable debug logging |

## Tips for Reproducing the Bug

1. **Use multiple concurrent clients**: The bug is more likely with 10+ rapid clients
2. **Very fast disconnections**: The test uses 1-10ms delays
3. **Immediate TCP close**: Uses `writer.close()` without `wait_closed()`
4. **Monitor GNS3 logs**: Watch for `OSError: [Errno 107]`
5. **Long test duration**: Run for 60+ seconds to accumulate events

## Verification Checklist

Run the test and verify:

- [ ] Before fix: ERROR logs appear in GNS3 server
- [ ] After fix: Only DEBUG logs appear
- [ ] Long-lived clients stay connected throughout test
- [ ] No resource leaks (check with `lsof` or netstat)
- [ ] Node remains operational after test

## Example Session

```bash
# Terminal 1: Start GNS3 server and watch logs
gns3server --log-level debug
# Watch for: OSError or "Error sending data to client"

# Terminal 2: Run stress test
cd /home/yueguobin/myCode/GNS3/gns3-server
python tests/stress/telnet_race_condition_test.py --port 2000 --rapid-clients 20

# Expected output:
# ======================================================================
# Telnet Server Race Condition Stress Test
# ======================================================================
# Target: 127.0.0.1:2000
# Rapid clients: 20 (each 50 iterations)
# Long-lived clients: 2 (duration: 30.0s)
# ...
# Rapid clients completed: 1000 success, 0 failures
# ======================================================================
```

## Troubleshooting

### "Connection refused"

- Make sure GNS3 node is started
- Check the console port number
- Verify telnet is working: `telnet 127.0.0.1 PORT`

### Bug not reproducing

- Increase `--rapid-clients` (try 50+)
- Increase `--iterations` (try 200+)
- Make sure GNS3 server log level is DEBUG
- Verify you're testing unpatched code

### Test hangs

- Check if node is still running
- Try reducing `--duration`
- Check network connectivity

## Related Files

- Bug: `gns3server/utils/asyncio/telnet_server.py:305`
- Fix commit: (to be added)
- Documentation: `docs/bugs/telnet-server-connection-race-condition.md`
