<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.


# Command Security Configuration

## Overview

GNS3-Copilot includes multiple security layers to prevent execution of commands that may cause issues in the lab environment:

- **Command Filtering**: Prevents commands that may timeout or lock up the console
- **Configuration Safety**: Prohibits dangerous configuration changes (AAA, passwords, etc.)
- **Multi-line Command Handling**: Properly processes commands with embedded newlines (banner, etc.)

This helps:

- **Prevent tool timeouts**: Commands like `traceroute` may run longer than the tool timeout
- **Maintain console availability**: Long-running commands can leave the device console unavailable for subsequent commands
- **Prevent device lockout**: AAA/password changes can lock users out of devices
- **Ensure reliable execution**: Filtering problematic commands ensures the remaining commands can execute properly

## Implementation Status

**Status**: ✅ **Implemented and Verified**

The command filtering system is fully implemented and has been tested in a live GNS3 environment with actual network devices. Key features:

- ✅ Simple text-based configuration file
- ✅ Substring matching (case-insensitive)
- ✅ Non-blocking filtering (allowed commands execute normally)
- ✅ Detailed blocking feedback in tool results
- ✅ Multi-device support
- ✅ Verified with real Cisco IOS devices

See the [Implementation Verification](#implementation-verification) section for actual test results.

## Problem Context

### Why Filter Commands?

When GNS3-Copilot tools execute commands on network devices using Nornir/Netmiko, there is a timeout limit (typically 30-60 seconds). If a command exceeds this timeout:

1. The tool stops waiting and returns a timeout error
2. The device console may still be executing the command
3. Subsequent commands sent to the device fail or produce incorrect results
4. The user may need to manually interrupt the command on the device console

### Example Scenario

```
Time    Agent Action                    Device Console Status
t0      Execute: traceroute 8.8.8.8     [Command starts]
t1      ...waiting...                   [Tracing...]
t2      ...waiting...                   [Tracing...]
t30     Timeout! Proceed to next tool   [Still tracing!]
t31     Execute: show ip route           [Ignored or corrupted]
t32     ❌ Command fails                [Console still busy]
```

## Current Implementation

### 1. Command Filtering System

#### Forbidden Commands List

Commands are listed in a simple text file at:
```
gns3server/agent/gns3_copilot/config/forbidden_commands.txt
```

**Format:**
- One command pattern per line
- Simple substring matching (case-insensitive)
- Empty lines and lines starting with `#` are ignored
- Match is performed on the beginning of each command

**Example:**
```
# Network diagnostic commands that may timeout
traceroute
tracepath
tracert

# Debug commands that may destabilize devices
debug

# Test commands that may affect device stability
test
```

### Filter Behavior

1. **Input Commands**: `["show version", "traceroute 8.8.8.8", "show ip int brief"]`
2. **Filtering**: `traceroute 8.8.8.8` is removed (matches `traceroute`)
3. **Executed**: `["show version", "show ip int brief"]`
4. **Result**: Returns successful output with blocked command information

### Result Format

When commands are filtered, the result includes additional fields:

```json
{
    "device_name": "R-1",
    "status": "partial_success",
    "output": "R-1#show version\nCisco IOS Software...\nR-1#show ip int brief\nInterface...",
    "diagnostic_commands": ["show version", "show ip int brief"],
    "blocked_commands": ["traceroute 8.8.8.8"],
    "blocked_info": {
        "traceroute 8.8.8.8": "Command 'traceroute 8.8.8.8' is not allowed because it matches the forbidden pattern 'traceroute'. This command may run longer than the tool timeout or leave the device console unavailable for subsequent commands."
    }
}
```

**Status values:**
- `"success"`: All commands executed successfully
- `"partial_success"`: Some commands were blocked, but remaining commands executed successfully
- `"failed"`: Command execution failed (device not found, connection error, etc.)

## Module Structure

### Command Filter Module

**File:** `gns3server/agent/gns3_copilot/utils/command_filter.py`

**Functions:**
- `filter_forbidden_commands(commands: list[str]) -> tuple[list[str], dict[str, str]]`
  - Returns allowed commands and blocked command information
- `is_command_forbidden(command: str) -> bool`
  - Check if a single command is forbidden
- `get_forbidden_commands() -> list[str]`
  - Get the current list of forbidden patterns
- `reload_forbidden_commands() -> None`
  - Reload the forbidden commands list (useful after editing the file)

### Integration Points

The filter is integrated into:
- **Display Tools** (`display_tools_nornir.py`): `ExecuteMultipleDeviceCommands`
- **Configuration Tools** (`config_tools_nornir.py`): `ExecuteMultipleDeviceConfigCommands`

Both tools use the same filtering logic and return format.

## Configuration

### Default Forbidden Commands

If the configuration file is not found, these defaults are used:
- `traceroute`
- `tracepath`
- `tracert`
- `ping -f`
- `debug`
- `test`

### Customizing the List

To add or remove forbidden commands:

1. Edit the configuration file:
   ```bash
   nano gns3server/agent/gns3_copilot/config/forbidden_commands.txt
   ```

2. Add your command patterns (one per line):
   ```
   # My custom blocked commands
   my_dangerous_command
   another_pattern
   ```

3. Restart GNS3 server to apply changes

### Reloading Without Restart

To reload the forbidden commands list without restarting the server:

```python
from gns3server.agent.gns3_copilot.utils.command_filter import reload_forbidden_commands
reload_forbidden_commands()
```

## Usage Examples

### Example 1: All Commands Allowed

**Input:**
```json
{
    "project_id": "abc-123-def",
    "device_configs": [
        {
            "device_name": "R-1",
            "commands": ["show version", "show ip route"]
        }
    ]
}
```

**Output:**
```json
{
    "device_name": "R-1",
    "status": "success",
    "output": "...",
    "diagnostic_commands": ["show version", "show ip route"]
}
```

### Example 2: Some Commands Blocked

**Input:**
```json
{
    "project_id": "abc-123-def",
    "device_configs": [
        {
            "device_name": "R-1",
            "commands": ["show version", "traceroute 8.8.8.8", "show ip route"]
        }
    ]
}
```

**Output:**
```json
{
    "device_name": "R-1",
    "status": "partial_success",
    "output": "...",
    "diagnostic_commands": ["show version", "show ip route"],
    "blocked_commands": ["traceroute 8.8.8.8"],
    "blocked_info": {
        "traceroute 8.8.8.8": "Command 'traceroute 8.8.8.8' is not allowed because it matches the forbidden pattern 'traceroute'. This command may run longer than the tool timeout or leave the device console unavailable for subsequent commands."
    }
}
```

### Example 3: All Commands Blocked

**Input:**
```json
{
    "project_id": "abc-123-def",
    "device_configs": [
        {
            "device_name": "R-1",
            "commands": ["traceroute 8.8.8.8", "debug ip routing"]
        }
    ]
}
```

**Output:**
```json
{
    "device_name": "R-1",
    "status": "success",
    "output": "",
    "diagnostic_commands": [],
    "blocked_commands": ["traceroute 8.8.8.8", "debug ip routing"],
    "blocked_info": {
        "traceroute 8.8.8.8": "Command 'traceroute 8.8.8.8' is not allowed because it matches the forbidden pattern 'traceroute'. This command may run longer than the tool timeout or leave the device console unavailable for subsequent commands.",
        "debug ip routing": "Command 'debug ip routing' is not allowed because it matches the forbidden pattern 'debug'. This command may run longer than the tool timeout or leave the device console unavailable for subsequent commands."
    }
}
```

## Implementation Verification

### Real-World Test Results

The command filtering system has been tested in a live GNS3 environment with actual network devices. Below are actual execution results:

**Test Scenario:**
- Devices: IOU-L2-1, IOU-L2-2 (Cisco IOS Layer 3 switches)
- Commands: Mixed allowed and forbidden commands
- Forbidden pattern: `traceroute`

**Actual Output:**
```json
{
  "device_name": "IOU-L2-1",
  "status": "partial_success",
  "diagnostic_commands": [
    "show ip route",
    "show ip interface brief",
    "ping 10.0.0.1",
    "ping 10.0.0.2",
    "ping 10.0.0.4"
  ],
  "blocked_commands": ["traceroute 10.0.0.2"],
  "blocked_info": {
    "traceroute 10.0.0.2": "Command 'traceroute 10.0.0.2' is not allowed because it matches the forbidden pattern 'traceroute'. This command may run longer than the tool timeout or leave the device console unavailable for subsequent commands."
  }
}
```

**Key Observations:**
1. ✅ `traceroute` command was successfully filtered
2. ✅ All other commands (`show`, `ping`) executed normally
3. ✅ Status correctly set to `partial_success`
4. ✅ Both `diagnostic_commands` (executed) and `blocked_commands` (filtered) are clearly listed
5. ✅ Detailed blocking reason provided in `blocked_info`
6. ✅ Tool execution continued without timeout or console lockup issues

### Functionality Verification Matrix

| Feature | Status | Notes |
|---------|--------|-------|
| Command filtering (substring match) | ✅ Verified | `traceroute` correctly matched and blocked |
| Partial execution | ✅ Verified | Other commands executed successfully |
| Return format consistency | ✅ Verified | Contains all expected fields |
| Multi-device support | ✅ Verified | Each device filtered independently |
| Error messages | ✅ Verified | Clear, informative blocking reasons |
| Status field accuracy | ✅ Verified | `partial_success` set correctly |
| Non-blocking behavior | ✅ Verified | No tool timeouts or console issues |

### Benefits Confirmed

1. **Timeout Prevention**: The `traceroute` command that could have taken 30+ seconds was filtered, preventing tool timeout
2. **Console Availability**: Since `traceroute` was not executed, the device console remained available for subsequent commands
3. **Clear Feedback**: The LLM receives clear information about which commands were blocked and why
4. **Partial Execution**: Useful commands (`show`, `ping`) still executed, providing valuable diagnostic information

## Future Enhancements (TODO)

### Planned Improvements

1. **Regex Support**: Allow more sophisticated pattern matching
   ```python
   # Current: simple substring match
   "traceroute"

   # Future: regex patterns
   "^traceroute\\s+"
   "ping\\s+.*\\s+-f"
   ```

2. **User Override File**: Allow per-project or user-specific overrides
   ```
   /etc/gns3-server/forbidden_commands_override.txt
   <project_dir>/forbidden_commands_override.txt
   ```

3. **Web UI Configuration**: Manage forbidden commands through GNS3 web interface

4. **Audit Logging**: Log blocked commands for security analysis

5. **Per-Command Timeouts**: Configure timeouts for specific commands instead of blocking
   ```python
   "command_timeouts": {
       "traceroute.*": 120,
       "debug.*": 5
   }
   ```

6. **Interrupt Mechanism**: Send Ctrl+C to interrupt long-running commands instead of blocking
   ```python
   def execute_with_timeout(cmd, timeout=30):
       try:
           return device.execute(cmd, timeout=timeout)
       except Timeout:
           device.send_break()  # Ctrl+C
           return f"Command interrupted after {timeout}s"
   ```

7. **Command State Tracking**: Track device console state to ensure availability
   ```python
   device_state = {
       "console_available": True,
       "current_command": None,
       "last_prompt_seen": timestamp
   }
   ```

### Advanced Features (Long-term)

- **Per-Device Filtering**: Different rules for different device types
- **Time-Based Restrictions**: Block certain commands during specific hours
- **Severity Levels**: Classify commands by severity (warn, block, allow)
- **ML-Based Detection**: Learn which commands cause problems and auto-block them

## Troubleshooting

### Commands Are Being Blocked Unexpectedly

**Problem:** A command you want to use is being blocked.

**Solution:**
1. Check the blocked command list in the result output
2. Identify which pattern is matching your command
3. Edit `forbidden_commands.txt` to remove or modify the pattern
4. Restart GNS3 server

### Forbidden Commands File Not Found

**Problem:** The system logs "Forbidden commands file not found. Using default list."

**Solution:**
1. Verify the file exists at the expected location
2. Check file permissions (should be readable by the GNS3 server process)
3. Ensure the file is not empty

### Changes Not Taking Effect

**Problem:** You edited the file but commands are still being blocked.

**Solution:**
1. Restart the GNS3 server (required to reload the configuration)
2. Or use the `reload_forbidden_commands()` function if available in your context

## Security Considerations

### 1. Why These Commands Are Blocked (Command Filtering)

| Command | Reason |
|---------|--------|
| `traceroute` | Can run for 30+ seconds, exceeds typical tool timeout |
| `tracepath` | Similar to traceroute, long execution time |
| `tracert` | Windows traceroute, same timeout issues |
| `ping -f` | Flood ping can overwhelm lab devices |
| `debug` | Debug commands can produce overwhelming output and destabilize devices |
| `test` | Test commands may affect device stability |

### 2. Configuration Safety (Prohibited Commands)

In addition to timeout-based filtering, GNS3-Copilot prohibits execution of sensitive configuration commands that could lock users out of devices or cause security issues. These restrictions are enforced at the **AI agent level** through system prompts.

**Prohibited Configuration Categories:**

| Category | Commands | Reason |
|----------|----------|--------|
| **AAA Configuration** | `aaa new-model`, `radius-server`, `tacacs-server` | May lock users out; requires manual configuration |
| **Login Passwords** | `enable secret`, `password`, `username ... password` | Can lock users out; security risk |
| **Console/VTY Authentication** | `line console 0`, `line vty 0 4`, `login local` | May block console access |
| **Password Encryption** | `service password-encryption` | Security-sensitive; manual setup required |
| **Access Control Lists** | `access-list ... deny ip any any` (on mgmt interfaces) | Can block management access |
| **Dangerous System Operations** | `reload`, `erase startup-config`, `format` | Destructive operations |

**Implementation:**
- **System Prompt**: Restrictions are defined in `lab_automation_assistant_prompt.py`
- **Behavior**: When AI detects these commands, it provides configuration guidance instead of execution
- **Example Response**:
  ```
  "I cannot execute AAA/password commands directly as they may lock you out.
   Here's how to configure them manually..."
  ```

**User Override:**
Users can manually execute these commands through:
1. Direct device console access
2. GNS3 device console
3. Manual SSH/Telnet connection

### 3. Multi-line Command Handling

**Problem:** Some configuration commands contain embedded newlines (e.g., `banner motd`), which cause Netmiko to fail when processed as single strings.

**Solution:** The system automatically expands multi-line commands before execution.

**Example:**
```python
# Input (single string with newlines)
["banner motd #\nWelcome\nUnauthorized access prohibited\n#"]

# After expansion
["banner motd #", "Welcome", "Unauthorized access prohibited", "#"]
```

**Implementation:**
- **Location**: `config_tools_nornir.py:_expand_multiline_commands()`
- **Detection**: Checks for `\n` newline character in commands
- **Processing**: Splits by `\n` and filters empty lines
- **Logging**: Records expansion for debugging

**Supported Commands:**
- `banner motd`, `banner login`, `banner exec`
- Multi-line ACLs
- Route-maps with continue statements
- Any command with embedded newlines

### Best Practices

1. **Education Environment**: Use the default filtering for safety
2. **Personal Lab**: Consider which commands you actually need
3. **Production-like Environment**: Keep restrictions enabled
4. **Always Understand**: Before allowing a command, understand why it was blocked

## Related Documentation

- [Tool Implementation](../gns3-copilot/tools_v2/README.md)
- [GNS3-Copilot Documentation](../README.md)
- [Contributing Guide](../../CONTRIBUTING.md)

## Feedback and Issues

If you:
- Find commands that should be blocked by default
- Need to allow commands for legitimate use cases
- Have suggestions for improving the filtering system

Please submit an issue: https://github.com/yueguobin/gns3-copilot/issues


