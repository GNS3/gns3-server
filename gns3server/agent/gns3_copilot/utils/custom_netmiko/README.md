# Custom Netmiko Drivers

Custom Netmiko drivers for GNS3-emulated network devices.

## Overview

This package contains Netmiko drivers optimized for GNS3 emulation environments where devices may have non-standard authentication or behavior patterns.

## Directory Structure

```
custom_netmiko/
├── __init__.py              # Package initialization, auto-registers all drivers
├── huawei_ce.py             # Huawei CloudEngine custom driver (GNS3HuaweiTelnetCE)
├── ruijie_telnet.py         # Ruijie OS custom driver (RuijieTelnetEnhanced)
├── README.md                # This file
├── scripts/                 # Utility scripts
│   └── list_netmiko_telnet_devices.py
└── tests/                   # Unit tests
    ├── __init__.py
    └── test_huawei_ce.py    # Huawei CE driver tests
```

## Supported Drivers

### Huawei (`huawei_ce.py`)

**Driver Name:** `GNS3HuaweiTelnetCE`

**Device Types:**
- `gns3_huawei_telnet_ce` - Primary type (GNS3 custom driver)
- `huawei_telnet` - Standard Netmiko type (for devices with authentication)

**Features:**
- Skip authentication (for GNS3 devices without username/password)
- VRP prompt recognition (`<HUAWEI>`, `[HUAWEI]`)
- Auto-commit before exit (prevents [Y/N/C] prompts)
- Proper output collection using `read_channel_timing()`

**Limitations:**
- Does not support username/password authentication
- If your device requires authentication, use standard `huawei_telnet` driver

## Usage

### Direct Usage

```python
from netmiko import ConnectHandler
from gns3server.agent.gns3_copilot.utils import custom_netmiko

device = {
    "device_type": "gns3_huawei_telnet_ce",
    "host": "127.0.0.1",
    "port": 5000,
}

with ConnectHandler(**device) as conn:
    output = conn.send_command("display version")
    config = ["interface GE1/0/1", "description Test"]
    output = conn.send_config_set(config)
```

### In GNS3 Copilot Tools

The drivers are auto-registered when the tools are imported:

```python
from gns3server.agent.gns3_copilot.tools_v2 import DisplayToolNornir

tool = DisplayToolNornir()
result = tool._run(json.dumps({
    "device_names": ["huawei-sw1"],
    "commands": ["display version"],
    "project_id": "project-uuid"
}))
```

## Running Tests

```bash
# Run all tests
source venv/bin/activate
python -m unittest discover -s gns3server/agent/gns3_copilot/utils/custom_netmiko/tests

# Run Huawei CE tests only
python gns3server/agent/gns3_copilot/utils/custom_netmiko/tests/test_huawei_ce.py
```

## Adding New Drivers

### 1. Create Driver File

Create a new file in `custom_netmiko/` (e.g., `cisco.py`):

```python
# cisco.py
from netmiko.cisco.cisco_ios import CiscoIosTelnet

class CustomCiscoDriver(CiscoIosTelnet):
    """Custom Cisco driver for GNS3."""

    def telnet_login(self, ...):
        # Override login logic
        pass

def register_custom_device_type() -> None:
    """Register this driver with Netmiko."""
    import importlib
    sd = importlib.import_module("netmiko.ssh_dispatcher")

    sd.CLASS_MAPPER["cisco_custom"] = CustomCiscoDriver
    sd.CLASS_MAPPER_BASE["cisco_custom"] = CustomCiscoDriver

    # Rebuild static lists
    sd.platforms = list(sd.CLASS_MAPPER.keys())
    sd.platforms.sort()

# Auto-register on import
try:
    register_custom_device_type()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"Failed to register: {e}")
```

### 2. Update `__init__.py`

Add import to `__init__.py`:

```python
try:
    from . import cisco  # noqa: F401
except Exception as e:
    logger.warning(f"Failed to import Cisco driver: {e}", exc_info=True)

__all__ = ["huawei_ce", "cisco"]
```

### 3. Create Tests

Create `tests/test_cisco.py`:

```python
import unittest
from gns3server.agent.gns3_copilot.utils.custom_netmiko import cisco

class TestCustomCiscoDriver(unittest.TestCase):
    def test_device_type_registered(self):
        from netmiko.ssh_dispatcher import CLASS_MAPPER
        self.assertIn("cisco_custom", CLASS_MAPPER)

if __name__ == "__main__":
    unittest.main()
```

## Troubleshooting

### Driver Not Found Error

```
ValueError: Unsupported 'device_type'
```

**Solution:** Ensure the custom_netmiko package is imported before using the device:

```python
from gns3server.agent.gns3_copilot.utils import custom_netmiko
# Now use the device
```

### Import Errors

If you get import errors, check:
1. Virtual environment is activated
2. Python path includes project root
3. Dependencies are installed (`pip install netmiko nornir nornir-netmiko`)

## Related Documentation

- [Multi-Vendor Device Support](../../../docs/gns3-copilot/implemented/multi-vendor-device-support.md)
- [Netmiko Documentation](https://ktbyers.github.io/netmiko/)

---

_Last updated: 2026-03-12_
