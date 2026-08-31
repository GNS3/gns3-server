---
name: gns3-appliance-loading
description: GNS3 appliance file loading mechanism and storage locations
metadata:
  type: reference
---

GNS3 loads appliance (.gns3a) files from two locations with specific priority order:

1. **Builtin appliances directory**: `~/.local/share/GNS3/appliances/`
   - Stores automatically downloaded devices from GNS3 registry
   - Maintained and updated by the system automatically

2. **Custom appliances directory**: `~/GNS3/appliances/`
   - Stores user-customized or modified appliance files
   - Manually managed by users

**Loading priority**: System loads builtin appliances first, then custom appliances. If both directories contain devices with the same `device_id`, the custom appliance overwrites the builtin one. This design allows users to customize devices without having their modifications overwritten by automatic registry updates.

**Implementation**: See `gns3server/controller/appliance_manager.py` in the `load_appliances()` method (lines 314-351).
