<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This document is a roadmap/planning document. The described features have not been implemented yet.


# Server Settings REST API — Roadmap

## Problem

Currently, `gns3_server.conf` can only be modified by directly editing the file on disk. There is no REST API endpoint to read or write server configuration, which prevents the Web UI from offering a settings page for server parameters.

## Proposed API

```
GET  /v3/settings  →  Return all current server settings
PUT  /v3/settings  →  Update and persist server settings
```

### Implementation Plan

**1. Add `save_config()` to `Config` class** (`gns3server/config.py`)

The `Config` class currently only reads configuration (via `read_config()` / `reload()`). A `save_config()` method is needed to serialize the in-memory `ServerConfig` pydantic model back to INI format and write it to disk.

Serialization details:
- `bool` → `"True"` / `"False"` (configparser convention)
- `SecretStr` → `get_secret_value()`
- `Enum` → `.value`
- `List[str]` → semi-colon for `additional_images_paths`, comma for `allowed_interfaces`
- `None` → skip

**2. Add a settings getter/setter** to `Config` to allow programmatic updates to the in-memory settings.

**3. New route file** (`gns3server/api/routes/controller/settings.py`):

- `GET /v3/settings` — returns the full `ServerConfig` as JSON (pydantic automatically masks `SecretStr` fields as `"********"`)
- `PUT /v3/settings` — accepts `ServerConfig`, merges existing secrets when placeholder values (`"********"`) are submitted, calls `save_config()`, and triggers runtime config update callbacks

Both endpoints require `get_current_active_user` for authentication.

**4. Register the new router** in `gns3server/api/routes/controller/__init__.py` under the `/settings` prefix.

### Security

- All settings endpoints require admin authentication (`get_current_active_user`)
- `SecretStr` fields (`compute_password`, `default_admin_password`, `jwt_secret_key`) are masked in responses
- On write, unchanged secrets are preserved via placeholder detection

### Related Files

| File | Role |
|------|------|
| `gns3server/config.py` | Config singleton with `read_config()` / `reload()` |
| `gns3server/schemas/config.py` | `ServerConfig` pydantic model with all 9 sub-models |
| `gns3server/api/routes/controller/__init__.py` | Controller router mounting |
| `gns3server/controller/__init__.py` | `Controller._update_config()` for runtime credential sync |

## Status

- [ ] gns3server/config.py: add `save_config()` method
- [ ] gns3server/config.py: add settings getter/setter
- [ ] gns3server/api/routes/controller/settings.py: new route file with GET and PUT endpoints
- [ ] gns3server/api/routes/controller/__init__.py: register settings router under `/settings`
- [ ] gns3server/api/routes/controller/controller.py: add notification emission on config change
