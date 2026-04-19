<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.


# Multi-Vendor Network Device Support

## Overview

GNS3-Copilot supports network devices from multiple vendors through Netmiko and Nornir integration. The system includes a custom Netmiko driver for Huawei devices in GNS3 emulation environments and supports dynamic device type detection.

## Supported Vendors

| Vendor | Platform | Device Type | Protocol | Status |
|--------|----------|-------------|----------|--------|
| **Cisco** | `cisco_ios` | `cisco_ios_telnet` | Telnet | ✅ Tested |
| **Huawei** | `huawei` | `gns3_huawei_telnet_ce` | Telnet | ✅ Tested (Custom Driver) |
| **Ruijie (锐捷)** | `ruijie_os` | `gns3_ruijie_telnet` | Telnet | ✅ Tested (Custom Driver) |
| **VPCS** | `vpcs` | `gns3_vpcs_telnet` | Telnet | ✅ Tested (Custom Driver) |

## Custom VPCS Driver (`VPCSTelnet`)

### Problem Statement

VPCS (Virtual PC Simulator) is a lightweight virtual PC simulator used in GNS3 lab environments. Unlike network devices (routers/switches), VPCS devices:

1. **No authentication** - Direct console access without username/password
2. **Simple command interface** - No configuration modes
3. **Simple prompt pattern** - `PC1>`, `PC2>`, etc.

### Solution: Lightweight Custom Driver

```
BaseConnection (Netmiko base class)
    ↓
VPCSTelnet (Custom GNS3 driver)
```

**Why Not Use Standard Telnet Driver?**
- Standard drivers attempt authentication (times out)
- No support for VPCS-specific prompt patterns (`PC\d+>`)
- No need for configuration mode handling

### VPCSTelnet Implementation

#### Location
```
gns3server/agent/gns3_copilot/utils/custom_netmiko/vpcs_telnet.py
```

#### Key Features

**1. No Authentication**
```python
def telnet_login(self, pri_prompt_terminator=r"PC\d+>", ...):
    # Send returns until VPCS prompt detected
    for i in range(max_loops):
        self.write_channel(self.RETURN)
        output = self.read_channel()

        if re.search(pri_prompt_terminator, output):
            return output  # Success - VPCS prompt detected
```

**2. Simple Prompt Recognition**
```
PC1> ip 10.10.0.12/24 10.10.0.254
PC1> ping 10.10.0.254
```

**3. No Configuration Mode**
```python
def check_config_mode(self) -> bool:
    return False  # VPCS has no config mode

def config_mode(self) -> str:
    return ""  # No config mode to enter

def exit_config_mode(self) -> str:
    return ""  # No config mode to exit
```

**4. No Paging**
```python
def disable_paging(self) -> str:
    return ""  # VPCS doesn't use paging
```

### VPCS Tool Usage

The VPCS driver is used by the `execute_vpcs_commands` tool:

```python
from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

tool = VPCSCommands()
result = tool._run(json.dumps({
    "project_id": "<PROJECT_UUID>",
    "device_configs": [
        {
            "device_name": "PC1",
            "commands": [
                "ip 10.10.0.12/24 10.10.0.254",
                "ping 10.10.0.254"
            ]
        }
    ]
}))
```

### VPCS Built-in Template Configuration

**✨ Automatic Tags - No Manual Configuration Required**

VPCS nodes created from the built-in template automatically include the necessary tags:

| Tag | Value | Purpose |
|-----|-------|---------|
| `platform` | `vpcs` | Platform identification |
| `device_type` | `gns3_vpcs_telnet` | Netmiko driver selection |

**Built-in Template Definition:**
```python
# gns3server/services/templates.py
{
    "template_id": uuid.uuid5(uuid.NAMESPACE_X500, "vpcs"),
    "template_type": "vpcs",
    "name": "VPCS",
    "default_name_format": "PC{0}",
    "category": "guest",
    "symbol": "vpcs_guest",
    "builtin": True,
    "tags": ["platform:vpcs", "device_type:gns3_vpcs_telnet"],  # ✅ Auto-applied
}
```

**User Benefits:**
- ✅ **No manual tagging required** - Tags are applied automatically when creating VPCS nodes
- ✅ **Automatic driver selection** - Copilot tools automatically use the correct Netmiko driver
- ✅ **Consistent behavior** - All VPCS nodes from the built-in template work identically
- ✅ **Zero configuration** - Users don't need to understand device_type tags

**How It Works:**
1. User creates a VPCS node from the built-in "VPCS" template
2. Node automatically inherits the tags: `platform:vpcs` and `device_type:gns3_vpcs_telnet`
3. Copilot tools read these tags and select the appropriate VPCS Netmiko driver
4. Commands execute using the VPCS-optimized driver (no authentication, simple prompts)

### Supported VPCS Commands

| Command | Description | Example |
|---------|-------------|---------|
| `ip` | Configure/show IP address | `ip 10.10.0.12/24 10.10.0.254` |
| `ping` | Test connectivity | `ping 10.10.0.254` |
| `arp` | Display ARP table | `arp` |
| `show ip` | Show IP configuration | `show ip` |
| `version` | Show VPCS version | `version` |
| `save` | Save configuration | `save` |
| `load` | Load configuration | `load` |

### Architecture Benefits

**Unified Tool Architecture:**
- ✅ Uses Nornir for connection management (same as network device tools)
- ✅ Uses Netmiko for command execution (consistent with other tools)
- ✅ Follows same patterns as `config_tools_nornir.py` and `display_tools_nornir.py`
- ✅ Simplified codebase - no need for separate telnetlib3 implementation

**Migration from telnetlib3:**
| Aspect | Old (telnetlib3) | New (Netmiko + Nornir) |
|--------|-----------------|-------------------------|
| Library | telnetlib3 | Netmiko |
| Framework | Manual threading | Nornir |
| Code Lines | ~490 lines | ~580 lines (with better structure) |
| Consistency | Unique implementation | Same as other tools |
| Maintenance | Separate code path | Unified architecture |

---

## Custom Huawei Driver (`GNS3HuaweiTelnetCE`)

### Problem Statement

GNS3-emulated Huawei devices connect via console **without requiring authentication**. Standard Netmiko drivers attempt username/password authentication, causing connection timeouts.

**Standard Driver Behavior:**
```
Telnet Connection → Wait for username prompt → Send username → Wait for password → Send password → Access
                    ^ Times out after 20 seconds
```

**GNS3 Huawei Device:**
```
Telnet Connection → Direct access to command line (no login prompts)
                    <HUAWEI>
```

### Solution: Custom Driver Architecture

```
BaseConnection (Netmiko base class)
    ↓
CiscoBaseConnection (Cisco-style base class)
    ↓
HuaweiBase (Huawei device base class) ← Inherits VRP support
    ↓
GNS3HuaweiTelnetCE (Custom GNS3 driver) ← Overrides telnet_login only
```

**Why Inherit from HuaweiBase?**
- ✅ Built-in VRP (Versatile Routing Platform) command handling
- ✅ Huawei-specific configuration mode (`system-view`)
- ✅ Huawei prompt patterns (`<...>`, `[...]`)
- ✅ Huawei paging disable (`screen-length 0 temporary`)
- ✅ Minimal code changes - only override authentication

### GNS3HuaweiTelnetCE Implementation

#### Location
```
gns3server/agent/gns3_copilot/utils/custom_netmiko/huawei_ce.py
```

**Package Structure:**
```
custom_netmiko/
├── __init__.py              # Package initialization, auto-registers all drivers
├── huawei_ce.py             # Huawei CloudEngine custom driver
├── README.md                # Driver development guide
└── tests/                   # Unit tests
    ├── __init__.py
    └── test_huawei_ce.py    # Huawei CE driver tests
```

#### Key Features

1. **Skip Authentication**
   - Directly detect Huawei prompt patterns
   - No username/password prompts
   - Connection ready in < 1 second

2. **VRP Prompt Recognition**
   ```
   User view:    <HUAWEI>
   System view:  [HUAWEI]
   Interface:    [HUAWEI-GigabitEthernet0/0/1]
   ```

3. **Automatic Confirmation Handling**
   - Detects and responds to `[y/n]` prompts
   - Example: `return` command asks "Return to user view? [y/n]:"
   - Automatically sends `y` to confirm

4. **Proper Output Collection**
   - Uses Netmiko's `read_channel_timing()` for reliable output
   - Waits for command completion (2s no new data = done)
   - 30-second absolute timeout prevents hanging

5. **Auto-Commit Before Exit**
   - Automatically sends `commit` command before exiting config mode
   - Prevents "Uncommitted configurations [Y/N/C]" prompt
   - Ensures configuration changes are saved

#### Limitations

**Authentication Requirement:**
- The `gns3_huawei_telnet_ce` driver is designed for GNS3 devices **without authentication**
- If your Huawei device has been configured with a username/password:
  - **Option 1**: Use the standard `huawei_telnet` driver (requires username/password)
  - **Option 2**: Remove authentication from the device for GNS3 testing
- The driver does **not** currently auto-detect authentication requirements

**When to Use Each Driver:**

| Scenario | Use Driver | Requires Credentials? |
|----------|-----------|----------------------|
| GNS3 Huawei (fresh, no auth) | `gns3_huawei_telnet_ce` | ❌ No |
| GNS3 Huawei (configured with username/password) | `huawei_telnet` | ✅ Yes |
| Real Huawei hardware | `huawei_telnet` | ✅ Yes |

#### Method Overrides

**1. `telnet_login` - Skip Authentication**
```python
def telnet_login(self, pri_prompt_terminator=r"<\S+>|>\s*$",
                alt_prompt_terminator=r"\[\S+\]", ...) -> str:
    # Clear buffer
    self.read_channel()

    # Send returns until prompt detected
    for i in range(max_loops):
        self.write_channel(self.RETURN)
        output = self.read_channel()

        # Check for Huawei prompts
        if re.search(pri_prompt_terminator, output):
            return output  # Success!

    return output  # Best effort
```

**2. `send_config_set` - Configuration Commands**
```python
def send_config_set(self, config_commands, **kwargs) -> str:
    # Enter config mode
    output += self.config_mode(config_command="system-view")

    # Send all commands
    for cmd in config_commands:
        self.write_channel(f"{cmd}{self.RETURN}")
        time.sleep(delay_factor * 0.05)

    # Collect output using Netmiko standard method
    output += self.read_channel_timing(read_timeout=30, last_read=2.0)

    # Auto-commit before exit (prevents [Y/N/C] prompt)
    self.write_channel(f"commit{self.RETURN}")
    time.sleep(0.5 * self.global_delay_factor)
    output += self.read_channel()

    # Exit config mode
    output += self.exit_config_mode()

    return output
```

**3. `exit_config_mode` - Handle Confirmation**
```python
def exit_config_mode(self, exit_config="return", pattern=r"<\S+>|>\s*$") -> str:
    self.write_channel(f"return{self.RETURN}")

    # Look for confirmation prompt
    for _ in range(20):
        new_output = self.read_channel()

        if re.search(r"\[y/n\]", new_output):
            self.write_channel(f"y{self.RETURN}")  # Auto-confirm

        if re.search(pattern, new_output):
            return output  # Back to user view

    return output
```

### Device Type Registration

The custom driver must be registered with Netmiko's global mappings:

```python
def register_custom_device_type() -> None:
    import importlib
    sd = importlib.import_module("netmiko.ssh_dispatcher")

    # Register in CLASS_MAPPER (for ConnectHandler)
    sd.CLASS_MAPPER["gns3_huawei_telnet_ce"] = GNS3HuaweiTelnetCE
    sd.CLASS_MAPPER["huawei_ce"] = GNS3HuaweiTelnetCE

    # Register in CLASS_MAPPER_BASE (for base class definitions)
    sd.CLASS_MAPPER_BASE["gns3_huawei_telnet_ce"] = GNS3HuaweiTelnetCE
    sd.CLASS_MAPPER_BASE["huawei_ce"] = GNS3HuaweiTelnetCE

    # CRITICAL: Rebuild static lists
    sd.platforms = list(sd.CLASS_MAPPER.keys())
    sd.platforms.sort()
    sd.telnet_platforms = [x for x in sd.platforms if "telnet" in x]
```

**Important: Static List Problem**
- `ssh_dispatcher.platforms` is computed at module import time
- Modifying `CLASS_MAPPER` doesn't automatically update `platforms`
- Must manually rebuild the list after registration

**Auto-Registration**
```python
# Automatically runs on module import
try:
    register_custom_device_type()
except Exception as e:
    logger.warning(f"Failed to register custom device type: {e}")
```

## Custom Ruijie Driver (`RuijieTelnetEnhanced`)

### Problem Statement

Ruijie (锐捷) network devices exhibit Cisco-like command syntax but have interactive prompts during configuration that can cause standard Netmiko drivers to fail.

**Common Issue - OSPF Router-ID:**
```
Router(config-router)#router-id 10.0.0.1
Change router-id and update OSPF process! [yes/no]:
```

Standard Netmiko's `send_config_set()` waits for a prompt pattern, but the `[yes/no]:` prompt doesn't match the expected config mode pattern, causing:
1. **ReadTimeout**: Netmiko times out waiting for the prompt
2. **Command Failure**: Subsequent commands are not executed
3. **Device Lockup**: Console remains in the waiting state

### Solution: Hybrid Strategy with Interactive Prompt Handling

```
BaseConnection (Netmiko base class)
    ↓
CiscoBaseConnection (Cisco-style base class)
    ↓
RuijieOSBase (Netmiko's Ruijie implementation)
    ↓
RuijieTelnetEnhanced (Custom GNS3 driver) ← Adds interactive prompt handling
```

**Why Hybrid Strategy?**
1. **Preprocessing**: Automatically insert `yes` after known interactive commands
2. **Fast Path**: Batch send for most commands (2-3 seconds for 13 commands)
3. **Fallback**: One-by-one send with real-time detection (reliable but slower)

### RuijieTelnetEnhanced Implementation

#### Location
```
gns3server/agent/gns3_copilot/utils/custom_netmiko/ruijie_telnet.py
```

#### Key Features

**1. Preprocessing - Known Interactive Commands**
```python
INTERACTIVE_PATTERNS = [
    re.compile(r'^router-id\s+', re.IGNORECASE),  # OSPF/EIGRP/BGP router-id
    re.compile(r'^erase\s+', re.IGNORECASE),        # erase startup-config
    re.compile(r'^delete\s+', re.IGNORECASE),       # delete files
    re.compile(r'^format\s+', re.IGNORECASE),       # format filesystem
    re.compile(r'^reload\b', re.IGNORECASE),        # reload/reboot
    re.compile(r'^boot\s+system\s+', re.IGNORECASE), # change boot image
]
```

**2. Hybrid Send Strategy**
```
┌─────────────────────────────────────┐
│ Input Configuration Commands        │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ Step 1: Preprocessing               │
│ - Detect interactive commands       │
│ - Insert 'yes' after them           │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ Step 2: Try Batch Send (Fast)       │
│ - Write all commands rapidly        │
│ - Read output once                  │
│ - last_read=2.0s (Netmiko standard) │
└──────────────┬──────────────────────┘
               ↓
         Success? ──Yes──→ Return output
               │
               No
               ↓
┌─────────────────────────────────────┐
│ Step 3: Fallback (Slow but Reliable)│
│ - Send commands one-by-one          │
│ - Detect prompts after each command │
│ - Send 'yes' when needed            │
│ - last_read=0.5s per command        │
└─────────────────────────────────────┘
```

**3. Batch Send Performance**
- **13 commands** with 1 interactive command
- **Fast path**: ~2-3 seconds (includes device processing time)
- **Fallback**: ~10 seconds (if batch fails)

**4. Real-time Detection (Fallback)**
```python
# After each command
new_output = self.read_channel_timing(read_timeout=10, last_read=0.5)

# Check for [yes/no] prompt
if re.search(r"\[yes/no\]", new_output, re.IGNORECASE):
    self.write_channel(f"yes{self.RETURN}")
    output += self.read_channel_timing(read_timeout=30, last_read=0.5)
```

#### GNS3 Node Tag Configuration

**For Ruijie devices in GNS3:**
```
device_type:gns3_ruijie_telnet
platform:ruijie_os
```

**Example Usage:**
```python
from netmiko import ConnectHandler
from gns3server.agent.gns3_copilot.utils import custom_netmiko

device = {
    "device_type": "gns3_ruijie_telnet",
    "host": "127.0.0.1",
    "port": 5000,
}

with ConnectHandler(**device) as conn:
    # These commands include router-id (interactive)
    config = [
        "router ospf 1",
        "router-id 10.0.0.1",  # Triggers [yes/no] prompt
        "network 192.168.1.0 0.0.0.255 area 0",
    ]
    # Automatically handles the [yes/no] prompt
    output = conn.send_config_set(config)
```

#### Limitations

**Interactive Command Coverage:**
- **Covered**: `router-id`, `erase`, `delete`, `format`, `reload`, `boot system`
- **Not Covered**: Unknown or vendor-specific interactive prompts
- **Fallback**: If batch fails, falls back to one-by-one with real-time detection

**When to Use Each Driver:**

| Scenario | Use Driver |
|----------|------------|
| GNS3 Ruijie (known commands) | `gns3_ruijie_telnet` (batch works) |
| GNS3 Ruijie (unknown commands) | `gns3_ruijie_telnet` (auto-fallback) |
| Real Ruijie hardware | `ruijie_os_telnet` (standard) |

## Dynamic Device Type Detection

### GNS3 Node Tags

Device type and platform are extracted from GNS3 node tags:

```
device_type:gns3_huawei_telnet_ce    → Netmiko device type (precise)
platform:huawei                  → Nornir platform (high-level)
```

**Tag Examples:**

| Vendor | Device Type Tag | Platform Tag | Template Source |
|--------|----------------|--------------|------------------|
| Cisco IOS | `device_type:cisco_ios_telnet` | `platform:cisco_ios` | User appliance |
| Huawei CE | `device_type:gns3_huawei_telnet_ce` | `platform:huawei` | User appliance |
| Ruijie | `device_type:gns3_ruijie_telnet` | `platform:ruijie_os` | User appliance |
| **VPCS** | `device_type:gns3_vpcs_telnet` | `platform:vpcs` | **Built-in ✅** |

**VPCS Built-in Template:**
- VPCS has a **built-in template** with pre-configured tags
- Tags are **automatically applied** when creating VPCS nodes
- No manual configuration required - works out of the box
- Other devices require users to import appliances and configure tags manually

### Nornir Best Practice: Host-Level Connection Configuration

The system uses **Nornir's configuration priority** (host > group > defaults) to handle multi-vendor environments efficiently:

```python
# From get_gns3_device_port.py
hosts_data[device_name] = {
    "port": console_port,
    "platform": platform,  # Reserved for future use (NAPALM, scrapli)
    "groups": ["network_devices"],  # All devices share one group
    "connection_options": {
        "netmiko": {
            "extras": {"device_type": device_type}  # Device-specific driver
        }
    },
}
```

**Why Host-Level `connection_options`?**
- ✅ Each device has its own `device_type` (host-level config)
- ✅ All devices share common settings via group inheritance (`hostname`, `timeout`)
- ✅ No need to dynamically create multiple groups for each device type
- ✅ Cleaner code structure - single generic group for all devices
- ✅ Follows Nornir best practice: "configuration proximity"

**Configuration Priority:**
```
Host Level (connection_options.device_type)
    ↓ OVERRIDES
Group Level (hostname, timeout, username, password)
    ↓ OVERRIDES
Defaults Level (data.location)
```

**Before (Old Approach - Dynamic Groups):**
```python
# Had to create multiple groups dynamically
groups = {
    "cisco_ios_telnet": {"device_type": "cisco_ios_telnet", ...},
    "huawei_telnet": {"device_type": "gns3_huawei_telnet_ce", ...},
    "juniper_junos": {"device_type": "juniper_junos_telnet", ...},
}
# Each host assigned to its vendor-specific group
```

**After (Current Approach - Host-Level Config):**
```python
# Single group for shared settings
groups = {
    "network_devices": {
        "hostname": "127.0.0.1",
        "timeout": 120,
        "username": "",
        "password": "",
    }
}
# Each host has device-specific connection_options
# Host config overrides group config automatically
```

## Architecture Evolution

### Problem: Multi-Vendor Device Support

**Initial Challenge:**
```
Topology: Cisco R1 + Huawei SW1 + Juniper SRX
    ↓
Need: Different Netmiko drivers for each device
    ↓
Question: How to configure Nornir for multiple device types?
```

### Solution Evolution

#### ❌ Approach 1: Single Group with First Device's Type (Initial Implementation)

```python
# PROBLEM: Only uses first device's configuration
def _initialize_nornir(hosts_data):
    first_device = next(iter(hosts_data.values()))
    device_type = first_device["device_type"]  # Only one type!

    return InitNornir(
        inventory={
            "options": {
                "hosts": hosts_data,  # Has multiple device types
                "groups": {
                    "network_devices": {
                        "connection_options": {
                            "netmiko": {"extras": {"device_type": device_type}}
                        }
                    }
                }
            }
        }
    )
```

**Issue:** All devices use the first device's driver!
- Cisco R1 → Uses Huawei driver (if Huawei is first) ❌
- Huawei SW1 → Uses Cisco driver (if Cisco is first) ❌

#### ❌ Approach 2: Dynamic Groups (Intermediate Solution)

```python
# COMPLEX: Create multiple groups dynamically
groups = {}
for host_data in hosts_data.values():
    device_type = host_data["device_type"]
    platform = host_data["platform"]
    group_name = f"{platform}_telnet"  # e.g., "huawei_telnet"

    if group_name not in groups:
        groups[group_name] = {
            "platform": platform,
            "connection_options": {
                "netmiko": {"extras": {"device_type": device_type}}
            }
        }

    host_data["groups"] = [group_name]
```

**Issues:**
- Complex logic to detect and create groups
- Code duplication in multiple files
- Had to delete helper functions (`_get_nornir_groups_config`, `_get_nornir_group`)
- Not following Nornir best practices

#### ✅ Approach 3: Host-Level Configuration (Current - Best Practice)

```python
# SIMPLE: Single group + host-level device_type
hosts_data[device_name] = {
    "port": console_port,
    "platform": platform,  # Reserved for future use
    "groups": ["network_devices"],  # All devices in one group
    "connection_options": {  # Device-specific config
        "netmiko": {
            "extras": {"device_type": device_type}
        }
    }
}

# Single generic group for shared settings
groups = {
    "network_devices": {
        "hostname": "127.0.0.1",
        "timeout": 120,
        "username": "",
        "password": "",
    }
}
```

**Advantages:**
- ✅ Clean, simple code
- ✅ Follows Nornir best practice (host > group > defaults)
- ✅ No dynamic group creation logic
- ✅ Each device's `connection_options` overrides group settings automatically
- ✅ Easy to extend with new device types

### Configuration Priority Demonstration

```python
# Host level (highest priority)
host["connection_options"]["netmiko"]["extras"]["device_type"] = "gns3_huawei_telnet_ce"

    ↓ OVERRIDES

# Group level (middle priority)
group["hostname"] = "127.0.0.1"
group["timeout"] = 120

    ↓ OVERRIDES

# Defaults level (lowest priority)
defaults["data"]["location"] = "gns3"
```

**Result:**
- Each device uses its own `device_type` from host level
- All devices share `hostname`, `timeout` from group level
- All devices share `data.location` from defaults level

## Usage Examples

### Direct Netmiko Usage

**Huawei Device (Custom Driver):**
```python
from netmiko import ConnectHandler
from gns3server.agent.gns3_copilot.utils import custom_netmiko

# Custom driver auto-registers on import
device = {
    "device_type": "gns3_huawei_telnet_ce",
    "host": "127.0.0.1",
    "port": 5000,
    # No username/password needed!
}

with ConnectHandler(**device) as conn:
    # Execute display command
    output = conn.send_command("display version")

    # Execute configuration commands
    config = [
        "interface GE1/0/1",
        "description Uplink-to-Core",
        "undo shutdown"
    ]
    output = conn.send_config_set(config)
```

**Cisco IOS Device (Standard Driver):**
```python
from netmiko import ConnectHandler

device = {
    "device_type": "cisco_ios_telnet",
    "host": "127.0.0.1",
    "port": 5001,
    "username": "cisco",
    "password": "cisco",
}

with ConnectHandler(**device) as conn:
    output = conn.send_command("show version")
    config = ["interface GigabitEthernet0/0", "description Test"]
    output = conn.send_config_set(config)
```

### Nornir Multi-Vendor Automation

```python
from nornir import InitNornir
from gns3server.agent.gns3_copilot.utils import custom_netmiko

# Auto-register custom driver (happens automatically on import)
from gns3server.agent.gns3_copilot.utils.custom_netmiko import huawei_ce
huawei_ce.register_custom_device_type()

# Initialize Nornir with mixed-vendor inventory
# Using host-level connection_options (best practice)
inventory = {
    "plugin": "DictInventory",
    "options": {
        "hosts": {
            "huawei-sw1": {
                "hostname": "127.0.0.1",
                "port": 5001,
                "platform": "huawei",  # Reserved for future use
                "groups": ["network_devices"],
                "connection_options": {
                    "netmiko": {
                        "extras": {"device_type": "gns3_huawei_telnet_ce"}
                    }
                }
            },
            "cisco-r1": {
                "hostname": "127.0.0.1",
                "port": 5002,
                "platform": "cisco_ios",
                "groups": ["network_devices"],
                "connection_options": {
                    "netmiko": {
                        "extras": {"device_type": "cisco_ios_telnet"}
                    }
                }
            }
        },
        "groups": {
            "network_devices": {
                "hostname": "127.0.0.1",  # Shared by all devices
                "timeout": 120,
                "username": "",
                "password": "",
            }
        },
        "defaults": {
            "data": {"location": "gns3"}
        }
    }
}

nr = InitNornir(inventory=inventory)

# Execute commands on all devices (multi-vendor)
result = nr.run(task=send_commands, commands=["display version"])

# Each device gets vendor-specific command handling
# huawei-sw1 uses gns3_huawei_telnet_ce driver
# cisco-r1 uses cisco_ios_telnet driver
```

### GNS3 Copilot Tool Usage

```python
from gns3server.agent.gns3_copilot.tools_v2 import DisplayToolNornir

tool = DisplayToolNornir()
result = tool._run(json.dumps({
    "device_names": ["huawei-sw1", "cisco-r1"],
    "commands": ["display version", "show version"],
    "project_id": "project-uuid"
}))

# Returns:
# {
#   "huawei-sw1": {
#     "display version": "<Huawei output>",
#     "status": "success"
#   },
#   "cisco-r1": {
#     "show version": "<Cisco output>",
#     "status": "success"
#   }
# }
```

## Module Structure

```
gns3server/agent/gns3_copilot/
├── utils/
│   ├── custom_netmiko/            # Custom Netmiko drivers package
│   │   ├── __init__.py             # Package initialization
│   │   ├── huawei_ce.py            # Huawei CloudEngine driver
│   │   ├── ruijie_telnet.py        # Ruijie enhanced driver
│   │   ├── vpcs_telnet.py          # VPCS simulator driver (NEW)
│   │   ├── README.md               # Driver development guide
│   │   └── tests/                  # Unit tests
│   │       ├── __init__.py
│   │       └── test_huawei_ce.py   # Huawei CE driver tests
│   └── get_gns3_device_port.py     # Device port extraction with host-level config
│       ├── _expand_multiline_commands()   # Expand banner commands
│       └── _error_handling()              # device_type missing errors
├── tools_v2/
│   ├── display_tools_nornir.py     # Multi-vendor display commands
│   │   ├── _get_nornir_defaults()  # Returns default Nornir config
│   │   └── _initialize_nornir()    # Single generic group + host-level device_type
│   ├── config_tools_nornir.py      # Multi-vendor config commands
│   │   ├── _get_nornir_defaults()  # Returns default Nornir config
│   │   └── _initialize_nornir()    # Single generic group + host-level device_type
│   │   ├── _expand_multiline_commands()   # Expand banner commands
│   │   └── _error_handling()              # device_type validation
│   └── vpcs_tools_netmiko.py      # VPCS commands using Nornir + Netmiko (NEW)
│       ├── VPCSCommands           # VPCS tool class
│       └── _initialize_nornir()    # VPCS device inventory setup
```

**Key Architectural Changes (2026-03-14):**
- ❌ Removed: `vpcs_tools_telnetlib3.py` - Replaced with Netmiko implementation
- ✅ Added: `vpcs_telnet.py` - Custom VPCS driver for Netmiko
- ✅ Added: `vpcs_tools_netmiko.py` - VPCS tool using Nornir + Netmiko
- ✅ Simplified: Unified tool architecture - all tools use Nornir + Netmiko
- ✅ Updated: Module structure - all tools follow same pattern

**Key Architectural Changes (2026-03-13):**
- ❌ Removed: `_get_nornir_groups_config()` - No longer needed
- ❌ Removed: `_get_nornir_group()` - No longer needed
- ✅ Simplified: `_initialize_nornir()` - Uses single generic group
- ✅ Updated: `get_gns3_device_port.py()` - Returns host-level `connection_options`
- ✅ Added: `ruijie_telnet.py` - Custom Ruijie driver with interactive prompt handling
- ✅ Added: `_expand_multiline_commands()` - Auto-expands banner and multi-line commands
- ✅ Added: `_error_handling()` - Validates device_type tags, returns error if missing

## Unit Testing

### Test Coverage

```python
# test_netmiko_custom.py

class TestGNS3HuaweiTelnetCEDriver(unittest.TestCase):
    def test_device_type_registered(self):
        """Verify gns3_huawei_telnet_ce is in Netmiko CLASS_MAPPER"""
        from netmiko.ssh_dispatcher import CLASS_MAPPER
        self.assertIn("gns3_huawei_telnet_ce", CLASS_MAPPER)

    def test_inheritance_from_huawei_base(self):
        """Verify inherits from HuaweiBase"""
        from netmiko.huawei.huawei import HuaweiBase
        self.assertTrue(issubclass(GNS3HuaweiTelnetCE, HuaweiBase))

    def test_vrp_methods_available(self):
        """Verify VRP-specific methods are available"""
        methods = ["config_mode", "check_config_mode", "exit_config_mode"]
        for method in methods:
            self.assertTrue(hasattr(GNS3HuaweiTelnetCE, method))
```

**Running Tests:**
```bash
source venv/bin/activate
python gns3server/agent/gns3_copilot/utils/custom_netmiko/tests/test_huawei_ce.py
```

**Current Test Status:** ✅ All 9 tests passing

## Platform vs Device Type

### Key Concepts

**Platform (Nornir):**
- High-level vendor identifier
- **Reserved for future use** with plugins like NAPALM, scrapli
- Used for metadata and logging
- Examples: `huawei`, `cisco_ios`
- ⚠️ **Not used by nornir_netmiko** (only `device_type` matters)

**Device Type (Netmiko):**
- Precise driver type for Netmiko connection
- Includes protocol information
- **Actively used** to determine which Netmiko driver class to load
- Examples: `gns3_huawei_telnet_ce`, `cisco_ios_telnet`

### Why Keep `platform` Field?

| Purpose | Plugin | Uses `platform`? |
|---------|--------|------------------|
| Connection driver | nornir_netmiko | ❌ No (uses `device_type`) |
| Driver selection | NAPALM | ✅ Yes |
| Driver selection | scrapli | ✅ Yes |
| Metadata/Logging | General | ✅ Yes (future) |

**Conclusion:** The `platform` field is kept for:
1. **Future plugin support** (NAPALM, scrapli)
2. **Debugging and logging** (vendor identification)
3. **Data completeness** (industry standard practice)

### Mapping

| Platform | Device Type | Netmiko Usage | Notes |
|----------|-------------|---------------|-------|
| `huawei` | `gns3_huawei_telnet_ce` | ✅ Active | Custom driver for GNS3 |
| `cisco_ios` | `cisco_ios_telnet` | ✅ Active | Standard Netmiko driver |

**Important:** For nornir_netmiko, only `device_type` in `connection_options` matters. The `platform` field is informational only.

## Related Documentation

- [Custom Netmiko README](../../../../../gns3server/agent/gns3_copilot/utils/custom_netmiko/README.md) - Driver development guide
- [Node Control Tools](./node-control-tools.md) - Device lifecycle management
- [Command Security](./command-security.md) - Command filtering and validation
- [Chat API](./chat-api.md) - Session management and SSE

## References

- [Netmiko Documentation](https://ktbyers.github.io/netmiko/)
- [Netmiko PLATFORMS.md](https://github.com/ktbyers/netmiko/blob/master/PLATFORMS.md)
- [Nornir Documentation](https://nornir.readthedocs.io/)

---

_Implementation Date: 2026-03-12_

_Last Updated: 2026-03-14 (Added VPCS driver and unified tool architecture)_

_Status: ✅ Implemented - Custom drivers for Huawei, Ruijie, and VPCS; multi-vendor support with Cisco IOS, Huawei, Ruijie, and VPCS tested_

_Architecture: Nornir best practice - host-level connection_options with single generic group_

_Unit Tests: ✅ 9/9 passing_

_Changelog:_
- **2026-03-14**: Added VPCS support and unified tool architecture
  - Implemented `VPCSTelnet` custom Netmiko driver for VPCS simulator
  - Replaced `vpcs_tools_telnetlib3.py` with `vpcs_tools_netmiko.py`
  - Unified all tools to use Nornir + Netmiko architecture
  - Removed dependency on telnetlib3 for VPCS devices
  - Improved code consistency and maintainability
- **2026-03-13 (Evening)**: Added Ruijie enhanced driver and interactive command handling
  - Implemented `RuijieTelnetEnhanced` with hybrid batch/fallback strategy
  - Added automatic `yes` insertion for known interactive commands (`router-id`, `erase`, etc.)
  - Achieves ~2-3 seconds for 13 commands (vs 10+ seconds for one-by-one)
  - Auto-fallback to real-time detection for unknown interactive prompts
  - Registered `gns3_ruijie_telnet` device type
- **2026-03-13 (Afternoon)**: Enhanced configuration safety and command handling
  - Added AAA/password configuration prohibition in system prompts
  - Implemented multi-line command expansion (`_expand_multiline_commands()`)
  - Added `device_type` tag validation with error feedback
  - Prevents execution of commands that could lock users out of devices
  - Properly handles banner and other multi-line configuration commands
- **2026-03-13 (Morning)**: Refactored to use host-level `connection_options` instead of dynamic groups
  - Removed `_get_nornir_groups_config()` and `_get_nornir_group()` helper functions
  - Simplified `_initialize_nornir()` to use single generic group
  - Updated `get_gns3_device_port.py()` to return host-level configuration
  - Reserved `platform` field for future NAPALM/scrapli plugin support
- **2026-03-12**: Initial implementation with custom Huawei driver
